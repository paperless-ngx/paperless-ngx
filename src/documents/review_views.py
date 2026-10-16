import re
import time
import uuid
from typing import Any
from typing import cast

from django.contrib.auth.models import User
from django.db import OperationalError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import APIException
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.models import Document
from documents.models import DocumentReview
from documents.models import DocumentReviewEvent
from documents.permissions import has_perms_owner_aware
from documents.permissions import permitted_document_ids
from documents.review import lock_documents
from documents.review_serializers import DocumentReviewSerializer
from documents.review_serializers import ReviewMutationSerializer
from documents.review_serializers import ReviewOptionsSerializer
from documents.review_serializers import ReviewQueueSerializer
from documents.versioning import get_root_document


class ReviewConflict(APIException):
    status_code = 409
    default_detail = "Review changed. Reload it before trying again."


def can_access(user: Any, document: Document, action: str = "view") -> bool:
    return (
        user.is_active
        and user.has_perm(f"documents.{action}_document")
        and has_perms_owner_aware(
            user,
            f"{action}_document",
            get_root_document(document, include_deleted=True),
        )
    )


def visible_document(user: Any, pk: int) -> Document:
    document = Document.global_objects.filter(pk=pk).first()
    if document is None or not can_access(user, document):
        raise Http404
    return document


def review_history(review: DocumentReview, revision: int) -> list[dict[str, Any]]:
    return (
        [
            {
                "action": event.action,
                "actor": event.actor,
                "revision": event.revision,
                "at": event.at.isoformat().replace("+00:00", "Z"),
                "request_id": str(event.request_id) if event.request_id else None,
                "comment": event.comment,
            }
            for event in DocumentReviewEvent.global_objects.filter(
                review=review,
                revision__lte=revision,
            ).order_by("revision")
        ]
        if review
        else []
    )


def review_response(
    document: Document,
    review: DocumentReview | None = None,
) -> dict[str, Any]:
    if review is None:
        review = DocumentReview.global_objects.filter(document=document).first()
    return {
        "document": document.pk,
        "state": review.state if review else "unreviewed",
        "revision": review.revision if review else 0,
        "reviewer": review.reviewer_id if review else None,
        "submitted_by": review.submitted_by_id if review else None,
        "history": review_history(review, review.revision if review else 0),
    }


def validate_payload(data: Any) -> tuple[str, uuid.UUID, str]:
    if not isinstance(data, dict):
        raise ValidationError("Expected an object.")
    action = data.get("action")
    if not isinstance(action, str) or action not in {
        "submit",
        "approve",
        "reject",
        "reopen",
    }:
        raise ValidationError({"action": "Unknown review action."})
    required = {"action", "expected_revision", "request_id"}
    if action == "submit":
        required.add("reviewer")
    if action == "reject":
        required.add("comment")
    if set(data) != required:
        raise ValidationError("Missing required fields or unknown fields.")
    revision = data["expected_revision"]
    if type(revision) is not int or revision < 0:
        raise ValidationError({"expected_revision": "Expected a nonnegative integer."})
    request_id = data["request_id"]
    if not isinstance(request_id, str):
        raise ValidationError({"request_id": "Expected a UUID string."})
    try:
        key = uuid.UUID(request_id)
    except ValueError as error:
        raise ValidationError({"request_id": "Expected a UUID string."}) from error
    if action == "submit":
        reviewer = data["reviewer"]
        if type(reviewer) is not int or not 0 < reviewer <= 2147483647:
            raise ValidationError({"reviewer": "Invalid reviewer."})
    comment = data.get("comment", "")
    if not isinstance(comment, str) or (
        action == "reject" and not 1 <= len(comment.strip()) <= 2000
    ):
        raise ValidationError({"comment": "Enter between 1 and 2000 characters."})
    return action, key, comment.strip()


class DocumentReviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=DocumentReviewSerializer)
    def get(self, request: Request, pk: int) -> Response:
        document = visible_document(request.user, pk)
        return Response(review_response(document))

    @extend_schema(
        request=ReviewMutationSerializer,
        responses={
            200: DocumentReviewSerializer,
            400: None,
            403: None,
            404: None,
            409: None,
        },
        description="Strict action payload; reviewer only for submit, comment only for reject.",
    )
    def post(self, request: Request, pk: int) -> Response:
        # SQLite's shared-cache test databases may report SQLITE_LOCKED immediately.
        # Retry the entire transaction; other databases use their ordinary row lock.
        for attempt in range(8):
            try:
                document = visible_document(request.user, pk)
                action, key, comment = validate_payload(request.data)
                if not can_access(request.user, document, "change"):
                    raise PermissionDenied
                return self.mutate(request, pk, action, key, comment)
            except OperationalError as error:
                if "locked" not in str(error).lower() or attempt == 7:
                    raise
                time.sleep(0.01 * (attempt + 1))
        raise ReviewConflict

    def mutate(
        self,
        request: Request,
        pk: int,
        action: str,
        key: uuid.UUID,
        comment: str,
    ) -> Response:
        data = cast("dict[str, Any]", request.data)
        with transaction.atomic():
            lock_documents([pk])
            document = visible_document(request.user, pk)
            if not can_access(request.user, document, "change"):
                raise PermissionDenied
            if document.deleted_at is not None:
                raise ReviewConflict("Documents in trash cannot be reviewed.")
            review = DocumentReview.objects.filter(document=document).first()
            cached = (
                DocumentReviewEvent.objects.filter(
                    review=review,
                    actor=request.user.pk,
                    request_id=key,
                ).first()
                if review
                else None
            )
            if action in {"approve", "reject"}:
                assigned = (
                    cached.response
                    if cached and cached.action in {"approve", "reject"}
                    else {
                        "reviewer": review.reviewer_id if review else None,
                        "submitted_by": review.submitted_by_id if review else None,
                    }
                )
                if (
                    assigned["reviewer"] != request.user.pk
                    or assigned["submitted_by"] == request.user.pk
                ):
                    raise PermissionDenied("Only the assigned reviewer may decide.")
            if cached:
                if cached.payload != request.data:
                    raise ReviewConflict(
                        "This request ID was used with a different payload.",
                    )
                return Response(
                    {
                        **cached.response,
                        "history": review_history(review, cached.revision),
                    },
                )
            if action == "submit":
                reviewer = User.objects.filter(
                    pk=data["reviewer"],
                    is_active=True,
                ).first()
                if (
                    reviewer is None
                    or reviewer.pk == request.user.pk
                    or not can_access(reviewer, document)
                    or not can_access(reviewer, document, "change")
                ):
                    raise ValidationError({"reviewer": "Invalid reviewer."})
            revision = review.revision if review else 0
            state = review.state if review else "unreviewed"
            if revision != data["expected_revision"]:
                raise ReviewConflict
            transitions = {
                "submit": ({"unreviewed"}, "pending"),
                "approve": ({"pending"}, "approved"),
                "reject": ({"pending"}, "rejected"),
                "reopen": ({"approved", "rejected"}, "unreviewed"),
            }
            sources, target = transitions[action]
            if state not in sources:
                raise ReviewConflict("Invalid review transition.")
            if review is None:
                review = DocumentReview(document=document)
            review.state = target
            review.revision = revision + 1
            if action == "submit":
                review.reviewer = reviewer
                review.submitted_by = request.user
            elif action == "reopen":
                review.reviewer = None
                review.submitted_by = None
            review.save()
            event = DocumentReviewEvent.objects.create(
                review=review,
                action=action,
                actor=request.user.pk,
                revision=review.revision,
                request_id=key,
                comment=comment,
                payload=dict(request.data),
            )
            response = review_response(document, review)
            # History is immutable: reconstruct the original prefix on retries,
            # rather than storing a quadratic number of event copies.
            event.response = {
                name: value for name, value in response.items() if name != "history"
            }
            event.save(update_fields=["response"])
            return Response(response)


def allowed_actions(
    user: Any,
    document: Document,
    review: DocumentReview | None,
) -> list[str]:
    if document.deleted_at is not None or not can_access(user, document, "change"):
        return []
    if review is None or review.state == "unreviewed":
        return ["submit"]
    if review.state in {"approved", "rejected"}:
        return ["reopen"]
    if review.reviewer_id == user.pk and review.submitted_by_id != user.pk:
        return ["approve", "reject"]
    return []


class DocumentReviewersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=ReviewOptionsSerializer,
        parameters=[
            OpenApiParameter(
                "search",
                str,
                description="Eligible usernames containing this text.",
            ),
        ],
    )
    def get(self, request: Request, pk: int) -> Response:
        document = visible_document(request.user, pk)
        review = DocumentReview.global_objects.filter(document=document).first()
        actions = allowed_actions(request.user, document, review)
        candidates = []
        if "submit" in actions:
            user_id = request.user.pk
            if user_id is None:
                raise PermissionDenied
            users = User.objects.filter(is_active=True).exclude(pk=user_id)
            search = request.query_params.get("search", "")
            users = users.filter(username__icontains=search).order_by("username", "id")
            # Limit the eligible options returned, without exposing inaccessible users.
            for user in users.iterator(chunk_size=100):
                if can_access(user, document) and can_access(user, document, "change"):
                    candidates.append({"id": user.pk, "username": user.username})
                    if len(candidates) == 50:
                        break
        return Response({"allowed_actions": actions, "results": candidates})


class ReviewQueueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=ReviewQueueSerializer,
        parameters=[
            OpenApiParameter("state", str, enum=DocumentReview.State.values),
            OpenApiParameter("reviewer", int, description="Positive reviewer ID."),
            OpenApiParameter(
                "page",
                int,
                description="Positive page number; defaults to 1.",
            ),
            OpenApiParameter("page_size", int, description="1-100; defaults to 20."),
        ],
    )
    def get(self, request: Request) -> Response:
        if not request.user.is_active or not request.user.has_perm(
            "documents.view_document",
        ):
            raise PermissionDenied
        params = request.query_params
        if set(params) - {"state", "reviewer", "page", "page_size"} or any(
            len(params.getlist(key)) != 1 for key in params
        ):
            raise ValidationError("Invalid queue filters.")
        state = params.get("state")
        if state is not None and state not in DocumentReview.State.values:
            raise ValidationError({"state": "Invalid review state."})
        numbers = {}
        for name, default, maximum in [
            ("page", "1", 2147483647),
            ("page_size", "20", 100),
            ("reviewer", None, 2147483647),
        ]:
            value = params.get(name, default)
            if value is not None:
                if (
                    not re.fullmatch(r"[0-9]{1,10}", value)
                    or not 1 <= int(value) <= maximum
                ):
                    raise ValidationError({name: "Invalid positive integer."})
                numbers[name] = int(value)
        visible = permitted_document_ids(request.user)
        reviews = (
            DocumentReview.objects.filter(revision__gt=0)
            .filter(
                Q(document__root_document__isnull=True, document_id__in=visible)
                | Q(
                    document__root_document_id__in=visible,
                    document__root_document__deleted_at__isnull=True,
                ),
            )
            .order_by("document_id")
        )
        if state is not None:
            reviews = reviews.filter(state=state)
        if "reviewer" in numbers:
            reviews = reviews.filter(reviewer_id=numbers["reviewer"])
        count = reviews.count()
        start = (numbers["page"] - 1) * numbers["page_size"]
        return Response(
            {
                "count": count,
                "results": [
                    {
                        "document": row.document_id,
                        "state": row.state,
                        "reviewer": row.reviewer_id,
                        "revision": row.revision,
                        "title": row.document.title,
                    }
                    for row in reviews.select_related("document")[
                        start : start + numbers["page_size"]
                    ]
                ],
            },
        )
