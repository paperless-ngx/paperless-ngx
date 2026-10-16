from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar
from typing import cast

from django.contrib.auth.models import User
from django.db import models
from django.db import transaction
from django.utils import timezone

if TYPE_CHECKING:
    from documents.models import Document

    ReviewAwareQuerySetBase = models.QuerySet[Document]
else:
    ReviewAwareQuerySetBase = object

C = TypeVar("C", bound=Callable[..., Any])
review_actor: ContextVar[int | None] = ContextVar("review_actor", default=None)
ignore_invalidation = ContextVar("ignore_review_invalidation", default=False)
CONTENT_FIELDS = {
    "content",
    "checksum",
    "archive_checksum",
    "root_document_id",
    "version_index",
}


@contextmanager
def review_actor_context(actor: User | int | None) -> Iterator[None]:
    token = review_actor.set(actor.pk if isinstance(actor, User) else actor)
    try:
        yield
    finally:
        review_actor.reset(token)


def document_update_context(method: C) -> C:
    @wraps(method)
    def wrapped(self: Any, request: Any, *args: Any, **kwargs: Any) -> Any:
        with review_actor_context(request.user), transaction.atomic():
            if "pk" in kwargs:
                lock_documents([int(kwargs["pk"])])
            return method(self, request, *args, **kwargs)

    return cast("C", wrapped)


def version_merge_context(method: C) -> C:
    @wraps(method)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        with review_actor_context(kwargs.get("user")), transaction.atomic():
            doc_ids = args[0] if args else kwargs["doc_ids"]
            lock_documents([*doc_ids, kwargs["root_document_id"]])
            return method(*args, **kwargs)

    return cast("C", wrapped)


@contextmanager
def review_lifecycle_context(document: "Document") -> Iterator[None]:
    with transaction.atomic():
        lock_documents([document.pk, document.root_document_id])
        token = ignore_invalidation.set(
            ignore_invalidation.get() or document.root_document_id is None,
        )
        try:
            yield
            if document.root_document_id is not None:
                invalidate_reviews([document.root_document_id])
        finally:
            ignore_invalidation.reset(token)


def lock_documents(ids: Iterable[int | None], using: str = "default") -> None:
    from documents.models import Document

    # A write, rather than SELECT FOR UPDATE alone, also serializes SQLite writers.
    for pk in sorted(set(pk for pk in ids if pk is not None)):
        models.QuerySet.update(
            Document.global_objects.using(using).filter(pk=pk),
            modified=models.F("modified"),
        )


def invalidate_reviews(
    ids: Iterable[int | None],
    *,
    actor: User | int | None = None,
    using: str = "default",
) -> None:
    from documents.models import DocumentReview
    from documents.models import DocumentReviewEvent

    if ignore_invalidation.get():
        return

    for review in DocumentReview.objects.using(using).filter(
        document_id__in=set(ids),
        document__deleted_at__isnull=True,
        state__in=[DocumentReview.State.PENDING, DocumentReview.State.APPROVED],
    ):
        review.state = DocumentReview.State.UNREVIEWED
        review.reviewer = None
        review.submitted_by = None
        review.revision += 1
        review.save(update_fields=["state", "reviewer", "submitted_by", "revision"])
        DocumentReviewEvent.objects.using(using).create(
            review=review,
            action="invalidate",
            actor=review_actor.get() if actor is None else actor,
            revision=review.revision,
            at=timezone.now(),
        )


def save_document(
    document: "Document",
    save: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    from documents.models import Document

    fields = kwargs.get("update_fields")
    if fields is not None and not CONTENT_FIELDS.intersection(
        "root_document_id" if field == "root_document" else field for field in fields
    ):
        return save(*args, **kwargs)
    using = kwargs.get("using") or document._state.db or "default"
    old_root = (
        Document.global_objects.using(using)
        .filter(pk=document.pk)
        .values_list("root_document_id", flat=True)
        .first()
        if document.pk
        else None
    )
    with transaction.atomic(using=using):
        lock_documents([document.pk, old_root, document.root_document_id], using)
        before = (
            Document.global_objects.using(using)
            .filter(pk=document.pk)
            .values(*CONTENT_FIELDS)
            .first()
            if document.pk
            else None
        )
        result = save(*args, **kwargs)
        after = (
            Document.global_objects.using(using)
            .filter(pk=document.pk)
            .values(*CONTENT_FIELDS)
            .get()
        )
        if before is None:
            affected = [document.root_document_id] if document.root_document_id else []
        elif before != after:
            affected = [
                document.pk,
                before["root_document_id"],
                after["root_document_id"],
            ]
        else:
            affected = []
        invalidate_reviews(
            [pk for pk in affected if pk is not None],
            actor=getattr(document, "_review_actor_id", None),
            using=using,
        )
        return result


class ReviewAwareQuerySetMixin(ReviewAwareQuerySetBase):
    def update(self, **kwargs: Any) -> int:
        from documents.models import Document

        if not CONTENT_FIELDS.intersection(
            "root_document_id" if field == "root_document" else field
            for field in kwargs
        ):
            return super().update(**kwargs)
        # Existing bulk version/reprocessing writers must share the same lock as review.
        # Snapshot only each bounded batch, not an installation's entire OCR content.
        total = 0
        with transaction.atomic(using=self.db):
            last_pk = 0
            while True:
                batch = list(
                    self.filter(pk__gt=last_pk)
                    .order_by("pk")
                    .values_list("pk", "root_document_id")[:200],
                )
                if not batch:
                    break
                ids = [pk for pk, _ in batch]
                roots = [root for _, root in batch if root is not None]
                new_root = kwargs.get("root_document_id", kwargs.get("root_document"))
                if isinstance(new_root, (int, Document)):
                    roots.append(getattr(new_root, "pk", new_root))
                lock_documents(ids + roots, self.db)
                before = {
                    row["pk"]: row
                    for row in Document.global_objects.using(self.db)
                    .filter(pk__in=ids)
                    .values("pk", *CONTENT_FIELDS)
                }
                total += super(
                    ReviewAwareQuerySetMixin,
                    self.filter(pk__in=ids),
                ).update(**kwargs)
                affected = set()
                for row in (
                    Document.global_objects.using(self.db)
                    .filter(pk__in=ids)
                    .values("pk", *CONTENT_FIELDS)
                ):
                    old = before[row["pk"]]
                    if row != old:
                        affected.update(
                            [
                                row["pk"],
                                old["root_document_id"],
                                row["root_document_id"],
                            ],
                        )
                lock_documents(affected, self.db)
                invalidate_reviews(
                    [pk for pk in affected if pk is not None],
                    using=self.db,
                )
                last_pk = ids[-1]
        return total
