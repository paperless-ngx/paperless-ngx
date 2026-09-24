import itertools
import logging
import os
import tempfile
from collections.abc import Callable
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from time import mktime
from typing import TYPE_CHECKING
from typing import Any

import pathvalidate
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count
from django.db.models import IntegerField
from django.db.models import Max
from django.db.models import OuterRef
from django.db.models import Prefetch
from django.db.models import Q
from django.db.models import QuerySet
from django.db.models import Subquery
from django.db.models.functions import Coalesce
from django.http import FileResponse
from django.http import Http404
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.http import HttpResponseServerError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_control
from django.views.decorators.http import condition
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_serializer
from drf_spectacular.utils import extend_schema_view
from drf_spectacular.utils import inline_serializer
from langdetect import detect
from rest_framework import parsers
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from documents.caching import get_llm_suggestion_cache
from documents.caching import get_metadata_cache
from documents.caching import get_suggestion_cache
from documents.caching import refresh_llm_suggestions_cache
from documents.caching import refresh_metadata_cache
from documents.caching import refresh_suggestions_cache
from documents.caching import set_llm_suggestions_cache
from documents.caching import set_metadata_cache
from documents.caching import set_suggestions_cache
from documents.classifier import load_classifier
from documents.conditionals import metadata_etag
from documents.conditionals import metadata_last_modified
from documents.conditionals import preview_etag
from documents.conditionals import preview_last_modified
from documents.conditionals import suggestions_etag
from documents.conditionals import suggestions_last_modified
from documents.conditionals import thumbnail_etag
from documents.conditionals import thumbnail_last_modified
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.filters import DocumentFilterSet
from documents.filters import DocumentsOrderingFilter
from documents.filters import EffectiveContentFilter
from documents.filters import PermittedObjectsFilter
from documents.filters import TitleContentFilter
from documents.mail import EmailAttachment
from documents.mail import send_email
from documents.matching import match_correspondents
from documents.matching import match_document_types
from documents.matching import match_storage_paths
from documents.matching import match_tags
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import PaperlessTask
from documents.models import ShareLink
from documents.models import StoragePath
from documents.models import Tag
from documents.permissions import PaperlessNotePermissions
from documents.permissions import PaperlessObjectPermissions
from documents.permissions import ViewDocumentsPermissions
from documents.permissions import annotate_document_count_by_ids
from documents.permissions import has_perms_owner_aware
from documents.permissions import permitted_document_ids
from documents.plugins.date_parsing import get_date_parser
from documents.search import SearchHit
from documents.serialisers.base import NotesSerializer
from documents.serialisers.documents import DocumentSerializer
from documents.serialisers.documents import DocumentVersionLabelSerializer
from documents.serialisers.documents import DocumentVersionSerializer
from documents.serialisers.documents import SearchResultSerializer
from documents.serialisers.sharing import EmailSerializer
from documents.serialisers.sharing import ShareLinkSerializer
from documents.signals import document_updated
from documents.tasks import consume_file
from documents.utils import get_boolean
from documents.versioning import VersionResolutionError
from documents.versioning import annotate_effective_content
from documents.versioning import get_latest_version_for_root
from documents.versioning import get_request_version_param
from documents.versioning import get_root_document
from documents.versioning import latest_version_content_prefetch
from documents.versioning import resolve_requested_version_for_root
from documents.versioning import versions_newest_first
from paperless.config import AIConfig
from paperless.parsers.registry import get_parser_registry
from paperless.views import StandardPagination
from paperless_ai.ai_classifier import get_ai_document_classification
from paperless_ai.ai_classifier import get_llm_output_language
from paperless_ai.exceptions import LLMProviderError
from paperless_ai.exceptions import LLMTimeoutError
from paperless_ai.matching import extract_unmatched_names
from paperless_ai.matching import match_correspondents_by_name
from paperless_ai.matching import match_document_types_by_name
from paperless_ai.matching import match_storage_paths_by_name
from paperless_ai.matching import match_tags_by_name
from paperless_ai.matching import resolve_correspondent_ids
from paperless_ai.matching import resolve_document_type_ids
from paperless_ai.matching import resolve_storage_path_ids
from paperless_ai.matching import resolve_tag_ids

from .base import _TANTIVY_SEARCH_PARAM_NAMES
from .base import BulkPermissionMixin
from .base import PassUserMixin
from .base import ResolvedRequestDocs
from .base import SearchParams
from .base import SearchResultPage
from .base import _get_more_like_id
from .base import _get_tantivy_query_and_mode
from .base import serve_file

if settings.AUDIT_LOG_ENABLED:
    from auditlog.models import LogEntry

if TYPE_CHECKING:
    from paperless_ai.base_model import TaxonomyChoiceDict


logger = logging.getLogger("paperless.api")


# Crossover point for intersect_and_order: below this count use a targeted
# IN-clause query; at or above this count fall back to a full-table scan +
# Python set intersection.  The IN-clause is faster for small result sets but
# degrades on SQLite with thousands of parameters.  PostgreSQL handles large IN
# clauses efficiently, so this threshold mainly protects SQLite users.
_TANTIVY_INTERSECT_THRESHOLD = 5_000


@extend_schema_serializer(
    component_name="EmailDocumentRequest",
    exclude_fields=("documents",),
)
class EmailDocumentDetailSchema(EmailSerializer):
    pass


@extend_schema_view(
    retrieve=extend_schema(
        description="Retrieve a single document",
        responses={
            200: DocumentSerializer(all_fields=True),
            400: None,
        },
        parameters=[
            OpenApiParameter(
                name="full_perms",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="fields",
                type=OpenApiTypes.STR,
                many=True,
                location=OpenApiParameter.QUERY,
            ),
        ],
    ),
    download=extend_schema(
        description="Download the document",
        parameters=[
            OpenApiParameter(
                name="original",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="follow_formatting",
                description="Whether or not to use the filename on disk",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: OpenApiTypes.BINARY},
    ),
    history=extend_schema(
        description="View the document history",
        responses={
            200: inline_serializer(
                name="LogEntry",
                many=True,
                fields={
                    "id": serializers.IntegerField(),
                    "timestamp": serializers.DateTimeField(),
                    "action": serializers.CharField(),
                    "changes": serializers.DictField(),
                    "actor": inline_serializer(
                        name="Actor",
                        fields={
                            "id": serializers.IntegerField(),
                            "username": serializers.CharField(),
                        },
                    ),
                },
            ),
            400: None,
            403: None,
            404: None,
        },
    ),
    metadata=extend_schema(
        description="View the document metadata",
        responses={
            200: inline_serializer(
                name="Metadata",
                fields={
                    "original_checksum": serializers.CharField(),
                    "original_size": serializers.IntegerField(),
                    "original_mime_type": serializers.CharField(),
                    "media_filename": serializers.CharField(),
                    "has_archive_version": serializers.BooleanField(),
                    "original_metadata": serializers.ListField(
                        child=inline_serializer(
                            name="OriginalMetadataEntry",
                            fields={
                                "namespace": serializers.CharField(),
                                "prefix": serializers.CharField(),
                                "key": serializers.CharField(),
                                "value": serializers.CharField(),
                            },
                        ),
                    ),
                    "archive_checksum": serializers.CharField(
                        allow_null=True,
                        required=False,
                    ),
                    "archive_media_filename": serializers.CharField(
                        allow_null=True,
                        required=False,
                    ),
                    "original_filename": serializers.CharField(),
                    "archive_size": serializers.IntegerField(
                        allow_null=True,
                        required=False,
                    ),
                    "archive_metadata": serializers.ListField(
                        child=inline_serializer(
                            name="ArchiveMetadataEntry",
                            fields={
                                "namespace": serializers.CharField(),
                                "prefix": serializers.CharField(),
                                "key": serializers.CharField(),
                                "value": serializers.CharField(),
                            },
                        ),
                        allow_null=True,
                        required=False,
                    ),
                    "lang": serializers.CharField(),
                },
            ),
            HTTPStatus.BAD_REQUEST: None,
            HTTPStatus.FORBIDDEN: None,
            HTTPStatus.NOT_FOUND: None,
        },
    ),
    notes=extend_schema(
        description="View, add, or delete notes for the document",
        methods=["GET", "POST", "DELETE"],
        request=inline_serializer(
            name="NoteCreateRequest",
            fields={
                "note": serializers.CharField(),
            },
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Note ID to delete (used only for DELETE requests)",
            ),
        ],
        responses={
            200: NotesSerializer(many=True),
            400: None,
            403: None,
            404: None,
        },
    ),
    suggestions=extend_schema(
        description="View suggestions for the document",
        responses={
            200: inline_serializer(
                name="Suggestions",
                fields={
                    "correspondents": serializers.ListField(
                        child=serializers.IntegerField(),
                    ),
                    "tags": serializers.ListField(child=serializers.IntegerField()),
                    "document_types": serializers.ListField(
                        child=serializers.IntegerField(),
                    ),
                    "storage_paths": serializers.ListField(
                        child=serializers.IntegerField(),
                    ),
                    "dates": serializers.ListField(child=serializers.CharField()),
                },
            ),
            400: None,
            403: None,
            404: None,
        },
    ),
    ai_suggestions=extend_schema(
        description="View AI suggestions for the document",
        responses={
            200: inline_serializer(
                name="AISuggestions",
                fields={
                    "title": serializers.CharField(allow_null=True),
                    "correspondents": serializers.ListField(
                        child=serializers.IntegerField(),
                    ),
                    "suggested_correspondents": serializers.ListField(
                        child=serializers.CharField(),
                    ),
                    "tags": serializers.ListField(child=serializers.IntegerField()),
                    "suggested_tags": serializers.ListField(
                        child=serializers.CharField(),
                    ),
                    "document_types": serializers.ListField(
                        child=serializers.IntegerField(),
                    ),
                    "suggested_document_types": serializers.ListField(
                        child=serializers.CharField(),
                    ),
                    "storage_paths": serializers.ListField(
                        child=serializers.IntegerField(),
                    ),
                    "suggested_storage_paths": serializers.ListField(
                        child=serializers.CharField(),
                    ),
                    "dates": serializers.ListField(child=serializers.CharField()),
                },
            ),
            400: None,
            403: None,
            404: None,
        },
    ),
    thumb=extend_schema(
        description="View the document thumbnail",
        responses={200: OpenApiTypes.BINARY},
    ),
    preview=extend_schema(
        description="View the document preview",
        responses={200: OpenApiTypes.BINARY},
    ),
    share_links=extend_schema(
        operation_id="document_share_links",
        description="View share links for the document",
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
            ),
        ],
        responses={
            200: {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "created": {"type": "string", "format": "date-time"},
                        "expiration": {"type": "string", "format": "date-time"},
                        "slug": {"type": "string"},
                    },
                },
            },
            400: None,
            403: None,
            404: None,
        },
    ),
    email_document=extend_schema(
        description="Email the document to one or more recipients as an attachment.",
        request=EmailDocumentDetailSchema,
        responses={
            200: inline_serializer(
                name="EmailDocumentResponse",
                fields={"message": serializers.CharField()},
            ),
            400: None,
            403: None,
            404: None,
            500: None,
        },
        deprecated=True,
    ),
    email_documents=extend_schema(
        operation_id="email_documents",
        description="Email one or more documents as attachments to one or more recipients.",
        request=EmailSerializer,
        responses={
            200: inline_serializer(
                name="EmailDocumentsResponse",
                fields={"message": serializers.CharField()},
            ),
            400: None,
            403: None,
            404: None,
            500: None,
        },
    ),
)
class DocumentViewSet(
    BulkPermissionMixin,
    PassUserMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    GenericViewSet[Document],
):
    model = Document
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        SearchFilter,
        DocumentsOrderingFilter,
        PermittedObjectsFilter,
    )
    filterset_class = DocumentFilterSet
    search_fields = ("title", "correspondent__name", "effective_content")
    ordering_fields = (
        "id",
        "title",
        "correspondent__name",
        "document_type__name",
        "storage_path__name",
        "created",
        "modified",
        "added",
        "archive_serial_number",
        "num_notes",
        "owner",
        "page_count",
        "custom_field_",
    )

    def _get_selection_data_for_queryset(self, queryset):
        # Resolve once instead of once per model below. `queryset` can carry an
        # arbitrarily expensive WHERE clause (user filters plus the permission
        # filter); re-embedding it as a subquery inside 5 separate Count(...)
        # calls forces the database to re-evaluate that whole thing 5 times, and
        # -- for FK relations especially -- can defeat semi-join planning
        # entirely at scale. A concrete id list is cheap to reuse.
        # order_by() drops the default/user ordering -- irrelevant for a plain
        # id list, but left in place it forces a sort over the full filtered
        # set before the ids can even be collected.
        document_ids = list(queryset.order_by().values_list("pk", flat=True))

        correspondents = Correspondent.objects.annotate(
            document_count=Count(
                "documents",
                filter=Q(documents__id__in=document_ids),
                distinct=True,
            ),
        )
        document_types = DocumentType.objects.annotate(
            document_count=Count(
                "documents",
                filter=Q(documents__id__in=document_ids),
                distinct=True,
            ),
        )
        storage_paths = StoragePath.objects.annotate(
            document_count=Count(
                "documents",
                filter=Q(documents__id__in=document_ids),
                distinct=True,
            ),
        )
        # Tag and CustomField reach Document through an M2M/through-model table;
        # a plain Count(filter=...) there is a much more expensive plan than the
        # FK relations above once the bridge table is large -- see
        # annotate_document_count_by_ids() for why.
        tags = annotate_document_count_by_ids(
            Tag.objects.all(),
            through_model=Document.tags.through,
            related_object_field="tag_id",
            document_ids=document_ids,
        )
        custom_fields = annotate_document_count_by_ids(
            CustomField.objects.all(),
            through_model=CustomFieldInstance,
            related_object_field="field_id",
            document_ids=document_ids,
        )
        return {
            "selected_correspondents": [
                {"id": t.id, "document_count": t.document_count} for t in correspondents
            ],
            "selected_tags": [
                {"id": t.id, "document_count": t.document_count} for t in tags
            ],
            "selected_document_types": [
                {"id": t.id, "document_count": t.document_count} for t in document_types
            ],
            "selected_storage_paths": [
                {"id": t.id, "document_count": t.document_count} for t in storage_paths
            ],
            "selected_custom_fields": [
                {"id": t.id, "document_count": t.document_count} for t in custom_fields
            ],
        }

    @classmethod
    def _content_filter_params(cls) -> tuple[str, ...]:
        """
        Query params whose filtering needs effective_content evaluated in SQL
        against every candidate row -- see
        _needs_effective_content_annotation(). Derived rather than
        hand-maintained so a new content-filtering param counts automatically.
        """
        params = [
            name
            for name, f in DocumentFilterSet.declared_filters.items()
            if isinstance(f, (TitleContentFilter, EffectiveContentFilter))
        ]
        if "effective_content" in cls.search_fields:
            params.append(SearchFilter().search_param)
        return tuple(params)

    def _needs_effective_content_annotation(self) -> bool:
        # effective_content is a per-row correlated subquery resolving each
        # document's latest version. Filtering *on* it forces the database to
        # evaluate it for every candidate row before reaching the LIMIT, which
        # the root_document_id self-join makes pathological on MariaDB
        # specifically once real candidate counts get large; otherwise the
        # "versions" prefetch + Document.get_effective_content() resolves only
        # the page that survives pagination. Every param here is deprecated in
        # favor of the Tantivy-backed search endpoint (see filters.py's
        # TitleContentFilter/EffectiveContentFilter docs), so pay that cost
        # only when one is actually used. Blank values don't count, matching
        # how those filters themselves no-op on them -- an empty `?search=`
        # applies no predicate.
        params = self.request.query_params
        return any(
            params.get(param, "").strip() for param in self._content_filter_params()
        )

    def _requested_fields(self) -> list[str] | None:
        # The sparse-fieldset `fields` param, as DynamicFieldsModelSerializer
        # wants it: None means "no restriction, serialize everything", which
        # a blank value means too. get_queryset() and get_serializer() both
        # branch on this, and they have to read it identically -- a queryset
        # that skips the content prefetch for a response that still
        # serializes content reintroduces get_effective_content()'s
        # per-instance fallback.
        fields_param = self.request.query_params.get("fields")
        return fields_param.split(",") if fields_param else None

    def _needs_effective_content_prefetch(self) -> bool:
        # The prefetch spares get_effective_content() a per-instance fallback
        # query, but only earns itself when content can reach the response.
        fields = self._requested_fields()
        return fields is None or "content" in fields

    def get_queryset(self):
        # A correlated subquery avoids the LEFT JOIN + Count() this used to
        # be, which forced a GROUP BY aggregate over every matching document
        # before the query could even be sorted or limited.
        note_count = Subquery(
            Note.objects.filter(document=OuterRef("pk"))
            .order_by()
            .values("document")
            .annotate(count=Count("pk"))
            .values("count"),
            output_field=IntegerField(),
        )
        # No .distinct() here: nothing in this base queryset can produce
        # duplicate document rows (select_related below is all FK-to-PK;
        # permission filtering is a boolean id__in predicate, not a join).
        # M2M-based filters that *do* introduce a join (e.g. tags__id__in)
        # already call .distinct() themselves where they need it -- see
        # ObjectFilter.filter(). A blanket .distinct() here forces the
        # database to fully sort and dedupe every visible document before
        # it can apply LIMIT, which is disastrous at scale.
        prefetches = [
            Prefetch(
                "versions",
                queryset=Document.objects.only(
                    "id",
                    "added",
                    "checksum",
                    "version_label",
                    "root_document_id",
                    "version_index",
                ),
            ),
            "tags",
            Prefetch(
                "custom_fields",
                queryset=CustomFieldInstance.objects.select_related("field"),
            ),
            # NotesSerializer nests the author, this avoids query per note
            Prefetch("notes", queryset=Note.objects.select_related("user")),
        ]
        if self._needs_effective_content_prefetch():
            prefetches.append(latest_version_content_prefetch())
        queryset = (
            Document.objects.filter(root_document__isnull=True)
            .order_by("-created", "-id")
            .annotate(num_notes=Coalesce(note_count, 0))
            .select_related("correspondent", "storage_path", "document_type", "owner")
            .prefetch_related(*prefetches)
        )
        if self._needs_effective_content_annotation():
            queryset = annotate_effective_content(queryset)
        return queryset

    def get_serializer(self, *args, **kwargs):
        truncate_content = self.request.query_params.get("truncate_content", "False")
        kwargs.setdefault("context", self.get_serializer_context())
        kwargs.setdefault("fields", self._requested_fields())
        kwargs.setdefault("truncate_content", truncate_content.lower() in ["true", "1"])
        try:
            full_perms = get_boolean(
                str(self.request.query_params.get("full_perms", "false")),
            )
        except ValueError:
            full_perms = False
        kwargs.setdefault(
            "full_perms",
            full_perms,
        )
        return super().get_serializer(*args, **kwargs)

    @extend_schema(
        operation_id="documents_root",
        responses=inline_serializer(
            name="DocumentRootResponse",
            fields={
                "root_id": serializers.IntegerField(),
            },
        ),
    )
    @action(methods=["get"], detail=True, url_path="root")
    def root(self, request, pk=None):
        try:
            doc = Document.global_objects.select_related(
                "owner",
                "root_document",
            ).get(pk=pk)
        except Document.DoesNotExist:
            raise Http404

        root_doc = get_root_document(doc)
        if request.user is not None and not has_perms_owner_aware(
            request.user,
            "view_document",
            root_doc,
        ):
            return HttpResponseForbidden("Insufficient permissions")

        return Response({"root_id": root_doc.id})

    def retrieve(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        response = super().retrieve(request, *args, **kwargs)
        if (
            "version" not in request.query_params
            or not isinstance(response.data, dict)
            or "content" not in response.data
        ):
            return response

        root_doc = self.get_object()
        content_doc = self._resolve_file_doc(root_doc, request)
        response.data["content"] = content_doc.content or ""
        return response

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        root_doc = self.get_object()
        content_doc = (
            self._resolve_file_doc(root_doc, request)
            if "version" in request.query_params
            else get_latest_version_for_root(root_doc)
        )
        content_updated = "content" in request.data
        updated_content = request.data.get("content") if content_updated else None

        data = request.data.copy()
        serializer_partial = partial
        if content_updated and content_doc.id != root_doc.id:
            if updated_content is None:
                raise ValidationError({"content": ["This field may not be null."]})
            data.pop("content", None)
            serializer_partial = True

        serializer = self.get_serializer(
            root_doc,
            data=data,
            partial=serializer_partial,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if content_updated and content_doc.id != root_doc.id:
            content_doc.content = (
                str(updated_content) if updated_content is not None else ""
            )
            content_doc.save(update_fields=["content", "modified"])

        refreshed_doc = self.get_queryset().get(pk=root_doc.pk)
        response_data = self.get_serializer(refreshed_doc).data
        if "version" in request.query_params and "content" in response_data:
            response_data["content"] = content_doc.content
        response = Response(response_data)

        from documents.search import get_backend

        get_backend().add_or_update(refreshed_doc)

        document_updated.send(
            sender=self.__class__,
            document=refreshed_doc,
        )

        return response

    def list(self, request, *args, **kwargs):
        if not get_boolean(
            str(request.query_params.get("include_selection_data", "false")),
        ):
            return super().list(request, *args, **kwargs)

        queryset = self.filter_queryset(self.get_queryset())
        selection_data = self._get_selection_data_for_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["selection_data"] = selection_data
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({"results": serializer.data, "selection_data": selection_data})

    def destroy(self, request, *args, **kwargs):
        from documents.search import get_backend

        get_backend().remove(self.get_object().pk)
        try:
            return super().destroy(request, *args, **kwargs)
        except Exception as e:
            if "Data too long for column" in str(e):
                logger.warning(
                    "Detected a possible incompatible database column. See https://docs.paperless-ngx.com/troubleshooting/#convert-uuid-field",
                )
            logger.error(f"Error deleting document: {e!s}")
            return HttpResponseBadRequest(
                "Error deleting document, check logs for more detail.",
            )

    @staticmethod
    def original_requested(request):
        return (
            "original" in request.query_params
            and request.query_params["original"] == "true"
        )

    def _resolve_file_doc(self, root_doc: Document, request):
        version_requested = get_request_version_param(request) is not None
        resolution = resolve_requested_version_for_root(
            root_doc,
            request,
            include_deleted=version_requested,
        )
        if resolution.error == VersionResolutionError.INVALID:
            raise NotFound("Invalid version parameter")
        if resolution.document is None:
            raise Http404
        return resolution.document

    def _get_effective_file_doc(
        self,
        request_doc: Document,
        root_doc: Document,
        request: Request,
    ) -> Document:
        if (
            request_doc.root_document_id is not None
            and get_request_version_param(request) is None
        ):
            return request_doc
        return self._resolve_file_doc(root_doc, request)

    def _resolve_request_and_root_doc(
        self,
        pk,
        request: Request,
        *,
        include_deleted: bool = False,
    ) -> ResolvedRequestDocs | HttpResponseForbidden:
        manager = Document.global_objects if include_deleted else Document.objects
        try:
            request_doc = manager.select_related(
                "owner",
                "root_document",
            ).get(id=pk)
        except Document.DoesNotExist:
            raise Http404

        root_doc = get_root_document(
            request_doc,
            include_deleted=include_deleted,
        )
        if request.user is not None and not has_perms_owner_aware(
            request.user,
            "view_document",
            root_doc,
        ):
            return HttpResponseForbidden("Insufficient permissions")
        return ResolvedRequestDocs(request_doc=request_doc, root_doc=root_doc)

    def file_response(self, pk, request, disposition):
        resolved = self._resolve_request_and_root_doc(
            pk,
            request,
            include_deleted=True,
        )
        if isinstance(resolved, HttpResponseForbidden):
            return resolved
        file_doc = self._get_effective_file_doc(
            resolved.request_doc,
            resolved.root_doc,
            request,
        )
        return serve_file(
            doc=file_doc,
            use_archive=not self.original_requested(request)
            and file_doc.has_archive_version,
            disposition=disposition,
            follow_formatting=request.query_params.get("follow_formatting", False),
        )

    def get_metadata(self, file, mime_type):
        if not Path(file).is_file():
            return None

        parser_class = get_parser_registry().get_parser_for_file(
            mime_type,
            Path(file).name,
            Path(file),
        )
        if parser_class:
            try:
                with parser_class() as parser:
                    return parser.extract_metadata(file, mime_type)
            except Exception:  # pragma: no cover
                logger.exception(f"Issue getting metadata for {file}")
                return []
        else:  # pragma: no cover
            logger.warning(f"No parser for {mime_type}")
            return []

    def get_filesize(self, filename):
        if Path(filename).is_file():
            return Path(filename).stat().st_size
        return None

    @action(methods=["get"], detail=True, filter_backends=[])
    @method_decorator(cache_control(no_cache=True))
    @method_decorator(
        condition(etag_func=metadata_etag, last_modified_func=metadata_last_modified),
    )
    def metadata(self, request, pk=None):
        resolved = self._resolve_request_and_root_doc(pk, request)
        if isinstance(resolved, HttpResponseForbidden):
            return resolved

        # Choose the effective document (newest version by default,
        # or explicit via ?version=).
        doc = self._get_effective_file_doc(
            resolved.request_doc,
            resolved.root_doc,
            request,
        )

        document_cached_metadata = get_metadata_cache(doc.pk)

        archive_metadata = None
        archive_filesize = (
            self.get_filesize(doc.archive_path) if doc.has_archive_version else None
        )
        if document_cached_metadata is not None:
            original_metadata = document_cached_metadata.original_metadata
            archive_metadata = document_cached_metadata.archive_metadata
            refresh_metadata_cache(doc.pk)
        else:
            original_metadata = self.get_metadata(doc.source_path, doc.mime_type)

            if doc.has_archive_version:
                archive_metadata = self.get_metadata(
                    doc.archive_path,
                    "application/pdf",
                )
            set_metadata_cache(doc, original_metadata, archive_metadata)

        meta = {
            "original_checksum": doc.checksum,
            "original_size": self.get_filesize(doc.source_path),
            "original_mime_type": doc.mime_type,
            "media_filename": doc.filename,
            "has_archive_version": doc.has_archive_version,
            "original_metadata": original_metadata,
            "archive_checksum": doc.archive_checksum,
            "archive_media_filename": doc.archive_filename,
            "original_filename": doc.original_filename,
            "archive_size": archive_filesize,
            "archive_metadata": archive_metadata,
        }

        lang = "en"
        try:
            lang = detect(doc.content)
        except Exception:
            pass
        meta["lang"] = lang

        return Response(meta)

    @action(methods=["get"], detail=True, filter_backends=[])
    @method_decorator(cache_control(no_cache=True))
    @method_decorator(
        condition(
            etag_func=suggestions_etag,
            last_modified_func=suggestions_last_modified,
        ),
    )
    def suggestions(self, request, pk=None):
        doc = get_object_or_404(
            Document.objects.select_related("owner").prefetch_related("versions"),
            pk=pk,
        )
        if request.user is not None and not has_perms_owner_aware(
            request.user,
            "change_document",
            doc,
        ):
            return HttpResponseForbidden("Insufficient permissions")

        document_suggestions = get_suggestion_cache(doc.pk)

        if document_suggestions is not None:
            refresh_suggestions_cache(doc.pk)
            return Response(document_suggestions.suggestions)

        classifier = load_classifier()

        dates = []
        if settings.NUMBER_OF_SUGGESTED_DATES > 0:
            with get_date_parser() as date_parser:
                gen = date_parser.parse(doc.filename, doc.content)
                dates = sorted(
                    {
                        i
                        for i in itertools.islice(
                            gen,
                            settings.NUMBER_OF_SUGGESTED_DATES,
                        )
                    },
                )

        resp_data = {
            "correspondents": [
                c.id for c in match_correspondents(doc, classifier, request.user)
            ],
            "tags": [t.id for t in match_tags(doc, classifier, request.user)],
            "document_types": [
                dt.id for dt in match_document_types(doc, classifier, request.user)
            ],
            "storage_paths": [
                dt.id for dt in match_storage_paths(doc, classifier, request.user)
            ],
            "dates": [date.strftime("%Y-%m-%d") for date in dates if date is not None],
        }

        # Cache the suggestions and the classifier hash for later
        set_suggestions_cache(doc.pk, resp_data, classifier)

        return Response(resp_data)

    @action(
        methods=["get"],
        detail=True,
        filter_backends=[],
        url_path="ai_suggestions",
    )
    @method_decorator(cache_control(no_cache=True))
    def ai_suggestions(self, request, pk=None):
        doc = get_object_or_404(
            Document.objects.select_related("owner").prefetch_related("versions"),
            pk=pk,
        )
        if request.user is not None and not has_perms_owner_aware(
            request.user,
            "change_document",
            doc,
        ):
            return HttpResponseForbidden("Insufficient permissions")

        ai_config = AIConfig()
        if not ai_config.ai_enabled:
            return HttpResponseBadRequest("AI is required for this feature")

        output_language = get_llm_output_language(
            ai_config=ai_config,
            user=request.user,
        )
        llm_cache_backend = ":".join(
            part
            for part in (
                ai_config.llm_backend,
                ai_config.llm_model,
                ai_config.llm_endpoint,
                output_language,
                f"user={request.user.pk}",
            )
            if part
        )

        cached_llm_suggestions = get_llm_suggestion_cache(
            doc.pk,
            backend=llm_cache_backend,
        )

        if cached_llm_suggestions:
            # Only the raw model choices are cached, never resolved object
            # ids. resolve_choice() below still runs permission filtering
            # freshly for this requester on every request, cache hit or not,
            # so a resolved id cached for one user's visibility can never be
            # handed unfiltered to a second, less-privileged requester of
            # the same (backend + user-keyed) cache entry.
            refresh_llm_suggestions_cache(
                doc.pk,
                backend=llm_cache_backend,
            )
            llm_suggestions = cached_llm_suggestions.suggestions
        else:
            try:
                llm_suggestions = get_ai_document_classification(
                    doc,
                    request.user,
                    output_language,
                )
            except ValueError as exc:
                logger.exception(
                    "Invalid AI configuration while generating suggestions for "
                    "document %s: %s",
                    doc.pk,
                    exc,
                    exc_info=True,
                )
                raise ValidationError(
                    {"ai": [_("Invalid AI configuration.")]},
                ) from exc
            except LLMTimeoutError as exc:
                logger.exception(
                    "AI backend timed out while generating suggestions for "
                    "document %s: %s",
                    doc.pk,
                    exc,
                    exc_info=True,
                )
                return Response(
                    {"ai": [_("AI backend request timed out.")]},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            except LLMProviderError:
                logger.exception(
                    "AI backend rejected the request for document %s",
                    doc.pk,
                )
                return Response(
                    {
                        "ai": [
                            _(
                                "AI backend rejected the request. "
                                "Check logs for details.",
                            ),
                        ],
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            set_llm_suggestions_cache(
                doc.pk,
                llm_suggestions,
                backend=llm_cache_backend,
            )

        tags_choice: TaxonomyChoiceDict = llm_suggestions["tags"]
        correspondents_choice: TaxonomyChoiceDict = llm_suggestions["correspondents"]
        document_types_choice: TaxonomyChoiceDict = llm_suggestions["document_types"]
        storage_paths_choice: TaxonomyChoiceDict = llm_suggestions["storage_paths"]

        def resolve_choice(
            choice: "TaxonomyChoiceDict",
            resolve_ids: Callable[[list[int], User], list],
            match_names: Callable[[list[str], User], list],
        ) -> list:
            """The ids the model picked from the candidates it was shown, plus
            name matches for the values it proposed as new. The schema allows
            the same object to satisfy both an existing_id and a new_name in
            one valid response, so results are deduplicated by pk (keeping
            first-seen order) rather than trusting the two lookups to be
            disjoint.
            """
            matched = resolve_ids(choice["existing_ids"], request.user) + match_names(
                choice["new_names"],
                request.user,
            )
            seen_ids: set[int] = set()
            deduped = []
            for obj in matched:
                if obj.pk in seen_ids:
                    continue
                seen_ids.add(obj.pk)
                deduped.append(obj)
            return deduped

        matched_tags = resolve_choice(
            tags_choice,
            resolve_tag_ids,
            match_tags_by_name,
        )
        matched_correspondents = resolve_choice(
            correspondents_choice,
            resolve_correspondent_ids,
            match_correspondents_by_name,
        )
        matched_types = resolve_choice(
            document_types_choice,
            resolve_document_type_ids,
            match_document_types_by_name,
        )
        matched_paths = resolve_choice(
            storage_paths_choice,
            resolve_storage_path_ids,
            match_storage_paths_by_name,
        )

        resp_data = {
            "title": llm_suggestions["title"],
            "tags": [t.id for t in matched_tags],
            "suggested_tags": extract_unmatched_names(
                tags_choice["new_names"],
                matched_tags,
            ),
            "correspondents": [c.id for c in matched_correspondents],
            "suggested_correspondents": extract_unmatched_names(
                correspondents_choice["new_names"],
                matched_correspondents,
            ),
            "document_types": [d.id for d in matched_types],
            "suggested_document_types": extract_unmatched_names(
                document_types_choice["new_names"],
                matched_types,
            ),
            "storage_paths": [s.id for s in matched_paths],
            "suggested_storage_paths": extract_unmatched_names(
                storage_paths_choice["new_names"],
                matched_paths,
            ),
            "dates": llm_suggestions["dates"],
        }

        return Response(resp_data)

    @action(methods=["get"], detail=True, filter_backends=[])
    @method_decorator(cache_control(no_cache=True))
    @method_decorator(
        condition(etag_func=preview_etag, last_modified_func=preview_last_modified),
    )
    def preview(self, request, pk=None):
        resolved = self._resolve_request_and_root_doc(pk, request, include_deleted=True)
        if isinstance(resolved, HttpResponseForbidden):
            return resolved

        try:
            file_doc = self._get_effective_file_doc(
                resolved.request_doc,
                resolved.root_doc,
                request,
            )

            return serve_file(
                doc=file_doc,
                use_archive=not self.original_requested(request)
                and file_doc.has_archive_version,
                disposition="inline",
            )
        except FileNotFoundError:
            raise Http404

    @action(methods=["get"], detail=True, filter_backends=[])
    @method_decorator(cache_control(no_cache=True))
    @method_decorator(
        condition(
            etag_func=thumbnail_etag,
            last_modified_func=thumbnail_last_modified,
        ),
    )
    def thumb(self, request, pk=None):
        resolved = self._resolve_request_and_root_doc(pk, request, include_deleted=True)
        if isinstance(resolved, HttpResponseForbidden):
            return resolved

        try:
            file_doc = self._get_effective_file_doc(
                resolved.request_doc,
                resolved.root_doc,
                request,
            )
            handle = file_doc.thumbnail_file

            return FileResponse(handle, content_type="image/webp")
        except FileNotFoundError:
            raise Http404

    @action(methods=["get"], detail=True)
    def download(self, request, pk=None):
        try:
            return self.file_response(pk, request, "attachment")
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404

    @action(
        methods=["get", "post", "delete"],
        detail=True,
        permission_classes=[PaperlessNotePermissions],
        pagination_class=None,
        filter_backends=[],
    )
    def notes(self, request, pk=None):
        currentUser = request.user
        try:
            doc = (
                Document.objects.select_related("owner")
                .prefetch_related("notes")
                .only("pk", "owner__id")
                .get(pk=pk)
            )
            if currentUser is not None and not has_perms_owner_aware(
                currentUser,
                "view_document",
                doc,
            ):
                return HttpResponseForbidden("Insufficient permissions to view notes")
        except Document.DoesNotExist:
            raise Http404

        serializer = self.get_serializer(doc)

        if request.method == "GET":
            try:
                notes = serializer.to_representation(doc).get("notes")
                return Response(notes)
            except Exception as e:
                logger.warning(f"An error occurred retrieving notes: {e!s}")
                return Response(
                    {"error": "Error retrieving notes, check logs for more detail."},
                )
        elif request.method == "POST":
            try:
                if currentUser is not None and not has_perms_owner_aware(
                    currentUser,
                    "change_document",
                    doc,
                ):
                    return HttpResponseForbidden(
                        "Insufficient permissions to create notes",
                    )

                c = Note.objects.create(
                    document=doc,
                    note=request.data["note"],
                    user=currentUser,
                )
                # If audit log is enabled make an entry in the log
                # about this note change
                if settings.AUDIT_LOG_ENABLED:
                    LogEntry.objects.log_create(
                        instance=doc,
                        changes={
                            "Note Added": ["None", c.id],
                        },
                        action=LogEntry.Action.UPDATE,
                    )

                doc.modified = timezone.now()
                doc.save(update_fields=["modified"])

                from documents.search import get_backend

                get_backend().add_or_update(doc)

                notes = serializer.to_representation(doc).get("notes")

                return Response(notes)
            except Exception as e:
                logger.warning(f"An error occurred saving note: {e!s}")
                return Response(
                    {
                        "error": "Error saving note, check logs for more detail.",
                    },
                )
        elif request.method == "DELETE":
            if currentUser is not None and not has_perms_owner_aware(
                currentUser,
                "change_document",
                doc,
            ):
                return HttpResponseForbidden("Insufficient permissions to delete notes")

            note_id = request.GET.get("id")
            if not note_id:
                raise ValidationError({"id": "This field is required."})
            try:
                note_id_int = int(note_id)
            except ValueError:
                raise ValidationError({"id": "A valid integer is required."})
            note = get_object_or_404(Note, id=note_id_int, document=doc)
            if settings.AUDIT_LOG_ENABLED:
                LogEntry.objects.log_create(
                    instance=doc,
                    changes={
                        "Note Deleted": [note.id, "None"],
                    },
                    action=LogEntry.Action.UPDATE,
                )

            note.delete()

            doc.modified = timezone.now()
            doc.save(update_fields=["modified"])

            from documents.search import get_backend

            get_backend().add_or_update(doc)

            notes = serializer.to_representation(doc).get("notes")

            return Response(notes)

        return Response(
            {
                "error": "error",
            },
        )

    @action(methods=["get"], detail=True, filter_backends=[])
    def share_links(self, request, pk=None):
        currentUser = request.user
        try:
            doc = Document.objects.select_related("owner").get(pk=pk)
            if currentUser is not None and not has_perms_owner_aware(
                currentUser,
                "change_document",
                doc,
            ):
                return HttpResponseForbidden(
                    "Insufficient permissions to add share link",
                )
        except Document.DoesNotExist:
            raise Http404

        if request.method == "GET":
            now = timezone.now()
            links = (
                ShareLink.objects.filter(document=doc)
                .select_related("document")
                .only(
                    "pk",
                    "created",
                    "expiration",
                    "slug",
                    "document__title",
                )
                .exclude(expiration__lt=now)
                .order_by("-created")
            )
            serializer = ShareLinkSerializer(links, many=True)
            return Response(serializer.data)

    @action(methods=["get"], detail=True, name="Audit Trail", filter_backends=[])
    def history(self, request, pk=None):
        if not settings.AUDIT_LOG_ENABLED:
            return HttpResponseBadRequest("Audit log is disabled")
        try:
            doc = Document.objects.get(pk=pk)
            if not request.user.has_perm("auditlog.view_logentry") or (
                doc.owner is not None
                and doc.owner != request.user
                and not request.user.is_superuser
            ):
                return HttpResponseForbidden(
                    "Insufficient permissions",
                )
        except Document.DoesNotExist:  # pragma: no cover
            raise Http404

        # documents
        entries = [
            {
                "id": entry.id,
                "timestamp": entry.timestamp,
                "action": entry.get_action_display(),
                "changes": entry.changes,
                "actor": (
                    {"id": entry.actor.id, "username": entry.actor.username}
                    if entry.actor
                    else None
                ),
            }
            for entry in LogEntry.objects.get_for_object(doc).select_related(
                "actor",
            )
        ]

        # custom fields
        for entry in LogEntry.objects.get_for_objects(
            doc.custom_fields.all(),
        ).select_related("actor"):
            entries.append(
                {
                    "id": entry.id,
                    "timestamp": entry.timestamp,
                    "action": entry.get_action_display(),
                    "changes": {
                        "custom_fields": {
                            "type": "custom_field",
                            "field": str(entry.object_repr).split(":")[0].strip(),
                            "value": str(entry.object_repr).split(":")[1].strip(),
                        },
                    },
                    "actor": (
                        {"id": entry.actor.id, "username": entry.actor.username}
                        if entry.actor
                        else None
                    ),
                },
            )

        return Response(sorted(entries, key=lambda x: x["timestamp"], reverse=True))

    @extend_schema(
        operation_id="documents_email_document",
        deprecated=True,
    )
    @action(
        methods=["post"],
        detail=True,
        url_path="email",
        permission_classes=[IsAuthenticated, ViewDocumentsPermissions],
    )
    # TODO: deprecated, remove with drop of support for API v9
    def email_document(self, request, pk=None):
        request_data = request.data.copy()
        request_data.setlist("documents", [pk])
        return self.email_documents(request, data=request_data)

    @action(
        methods=["post"],
        detail=False,
        url_path="email",
        serializer_class=EmailSerializer,
        permission_classes=[IsAuthenticated, ViewDocumentsPermissions],
    )
    def email_documents(self, request, data=None):
        serializer = EmailSerializer(data=data or request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        document_ids = validated_data.get("documents")
        addresses = validated_data.get("addresses").split(",")
        addresses = [addr.strip() for addr in addresses]
        subject = validated_data.get("subject")
        message = validated_data.get("message")
        use_archive_version = validated_data.get("use_archive_version", True)

        documents = Document.objects.filter(pk__in=document_ids)
        if (
            request.user is not None
            and documents.exclude(
                pk__in=permitted_document_ids(request.user),
            ).exists()
        ):
            return HttpResponseForbidden("Insufficient permissions")

        try:
            attachments: list[EmailAttachment] = []
            for doc in documents:
                attachment_path = (
                    doc.archive_path
                    if use_archive_version and doc.has_archive_version
                    else doc.source_path
                )
                attachments.append(
                    EmailAttachment(
                        path=attachment_path,
                        mime_type=doc.mime_type,
                        friendly_name=doc.get_public_filename(
                            archive=use_archive_version and doc.has_archive_version,
                        ),
                    ),
                )

            send_email(
                subject=subject,
                body=message,
                to=addresses,
                attachments=attachments,
            )

            logger.debug(
                f"Sent documents {[doc.id for doc in documents]} via email to {addresses}",
            )
            return Response({"message": "Email sent"})
        except Exception as e:
            logger.warning(f"An error occurred emailing documents: {e!s}")
            return HttpResponseServerError(
                "Error emailing documents, check logs for more detail.",
            )

    @extend_schema(
        operation_id="documents_update_version",
        request=DocumentVersionSerializer,
        responses={
            200: OpenApiTypes.STR,
        },
    )
    @action(methods=["post"], detail=True, parser_classes=[parsers.MultiPartParser])
    def update_version(self, request, pk=None):
        serializer = DocumentVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            request_doc = Document.objects.select_related(
                "owner",
                "root_document",
            ).get(pk=pk)
            root_doc = get_root_document(request_doc)
            if request.user is not None and (
                not request.user.has_perm("documents.change_document")
                or not has_perms_owner_aware(
                    request.user,
                    "change_document",
                    root_doc,
                )
            ):
                return HttpResponseForbidden("Insufficient permissions")
        except Document.DoesNotExist:
            raise Http404

        try:
            doc_name, doc_data = serializer.validated_data.get("document")
            version_label = serializer.validated_data.get("version_label")

            t = int(mktime(datetime.now().timetuple()))

            settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

            temp_file_path = Path(tempfile.mkdtemp(dir=settings.SCRATCH_DIR)) / Path(
                pathvalidate.sanitize_filename(doc_name),
            )

            temp_file_path.write_bytes(doc_data)

            os.utime(temp_file_path, times=(t, t))

            input_doc = ConsumableDocument(
                source=DocumentSource.ApiUpload,
                original_file=temp_file_path,
                root_document_id=root_doc.pk,
            )

            overrides = DocumentMetadataOverrides()
            if version_label:
                overrides.version_label = version_label.strip()
            if request.user is not None:
                overrides.owner_id = request.user.id
                overrides.actor_id = request.user.id

            async_task = consume_file.apply_async(
                kwargs={"input_doc": input_doc, "overrides": overrides},
                headers={"trigger_source": PaperlessTask.TriggerSource.WEB_UI},
            )
            logger.debug(
                f"Updated document {root_doc.id} with new version",
            )
            return Response(async_task.id)
        except Exception as e:
            logger.warning(f"An error occurred updating document: {e!s}")
            return HttpResponseServerError(
                "Error updating document, check logs for more detail.",
            )

    def _get_root_doc_for_version_action(self, pk) -> Document:
        try:
            root_doc = Document.objects.select_related(
                "owner",
                "root_document",
            ).get(pk=pk)
        except Document.DoesNotExist:
            raise Http404
        return get_root_document(root_doc)

    def _get_version_doc_for_root(self, root_doc: Document, version_id) -> Document:
        try:
            version_doc = Document.objects.select_related("owner").get(
                pk=version_id,
            )
        except Document.DoesNotExist:
            raise Http404

        if (
            version_doc.id != root_doc.id
            and version_doc.root_document_id != root_doc.id
        ):
            raise Http404
        return version_doc

    @extend_schema(
        operation_id="documents_delete_version",
        parameters=[
            OpenApiParameter(
                name="version_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
            ),
        ],
        responses=inline_serializer(
            name="DeleteDocumentVersionResult",
            fields={
                "result": serializers.CharField(),
                "current_version_id": serializers.IntegerField(),
            },
        ),
    )
    @action(
        methods=["delete"],
        detail=True,
        url_path=r"versions/(?P<version_id>\d+)",
    )
    def delete_version(self, request, pk=None, version_id=None):
        root_doc = self._get_root_doc_for_version_action(pk)

        if request.user is not None and not has_perms_owner_aware(
            request.user,
            "delete_document",
            root_doc,
        ):
            return HttpResponseForbidden("Insufficient permissions")

        version_doc = self._get_version_doc_for_root(root_doc, version_id)

        if version_doc.id == root_doc.id:
            return HttpResponseBadRequest(
                "Cannot delete the root/original version. Delete the document instead.",
            )

        from documents.search import get_backend

        _backend = get_backend()
        _backend.remove(version_doc.pk)
        version_doc_id = version_doc.id
        version_doc.delete()
        root_doc.modified = timezone.now()
        Document.objects.filter(pk=root_doc.pk).update(modified=root_doc.modified)
        _backend.add_or_update(root_doc)
        if settings.AUDIT_LOG_ENABLED:
            actor = (
                request.user if request.user and request.user.is_authenticated else None
            )
            LogEntry.objects.log_create(
                instance=root_doc,
                changes={
                    "Version Deleted": ["None", version_doc_id],
                },
                action=LogEntry.Action.UPDATE,
                actor=actor,
                additional_data={
                    "reason": "Version deleted",
                    "version_id": version_doc_id,
                },
            )

        current = versions_newest_first(
            Document.objects.filter(Q(id=root_doc.id) | Q(root_document=root_doc)),
        ).first()

        document_updated.send(
            sender=self.__class__,
            document=root_doc,
        )
        return Response(
            {
                "result": "OK",
                "current_version_id": current.id if current else root_doc.id,
            },
        )

    @extend_schema(
        operation_id="documents_update_version_label",
        request=DocumentVersionLabelSerializer,
        parameters=[
            OpenApiParameter(
                name="version_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
            ),
        ],
        responses=inline_serializer(
            name="UpdateDocumentVersionLabelResult",
            fields={
                "id": serializers.IntegerField(),
                "added": serializers.DateTimeField(),
                "version_label": serializers.CharField(
                    required=False,
                    allow_null=True,
                ),
                "checksum": serializers.CharField(
                    required=False,
                    allow_null=True,
                ),
                "is_root": serializers.BooleanField(),
            },
        ),
    )
    @delete_version.mapping.patch
    def update_version_label(self, request, pk=None, version_id=None):
        serializer = DocumentVersionLabelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        root_doc = self._get_root_doc_for_version_action(pk)
        if request.user is not None and not has_perms_owner_aware(
            request.user,
            "change_document",
            root_doc,
        ):
            return HttpResponseForbidden("Insufficient permissions")

        version_doc = self._get_version_doc_for_root(root_doc, version_id)
        old_label = version_doc.version_label
        version_doc.version_label = serializer.validated_data["version_label"]
        version_doc.save(update_fields=["version_label"])
        root_doc.modified = timezone.now()
        Document.objects.filter(pk=root_doc.pk).update(modified=root_doc.modified)

        if settings.AUDIT_LOG_ENABLED and old_label != version_doc.version_label:
            actor = (
                request.user if request.user and request.user.is_authenticated else None
            )
            LogEntry.objects.log_create(
                instance=root_doc,
                changes={
                    "Version Label": [old_label, version_doc.version_label],
                },
                action=LogEntry.Action.UPDATE,
                actor=actor,
                additional_data={
                    "reason": "Version label updated",
                    "version_id": version_doc.id,
                },
            )

        document_updated.send(
            sender=self.__class__,
            document=root_doc,
        )

        return Response(
            {
                "id": version_doc.id,
                "added": version_doc.added,
                "version_label": version_doc.version_label,
                "checksum": version_doc.checksum,
                "is_root": version_doc.id == root_doc.id,
            },
        )


@extend_schema_view(
    list=extend_schema(
        description="Document views including search",
        parameters=[
            OpenApiParameter(
                name="text",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Simple Tantivy-backed text search query string",
            ),
            OpenApiParameter(
                name="title_search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Simple Tantivy-backed title-only search query string",
            ),
            OpenApiParameter(
                name="query",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Advanced Tantivy search query string",
            ),
            OpenApiParameter(
                name="full_perms",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="fields",
                type=OpenApiTypes.STR,
                many=True,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={
            200: DocumentSerializer(many=True, all_fields=True),
        },
    ),
    next_asn=extend_schema(
        description="Get the next available Archive Serial Number (ASN) for a new document",
        responses={
            200: OpenApiTypes.INT,
        },
    ),
)
class UnifiedSearchViewSet(DocumentViewSet):
    def get_serializer_class(self):
        if self._is_search_request():
            return SearchResultSerializer
        return DocumentSerializer

    def get_serializer_context(self):
        if self._is_search_request():
            # BulkPermissionMixin.get_serializer_context() (inherited via
            # DocumentViewSet) assumes it's batching permissions for a page of
            # real Document instances. Tantivy search results are SearchHit/
            # dict-like objects instead, so skip straight past it here.
            return super(BulkPermissionMixin, self).get_serializer_context()
        return super().get_serializer_context()

    def _get_active_search_params(self, request: Request | None = None) -> list[str]:
        request = request or self.request
        return [
            param
            for param in _TANTIVY_SEARCH_PARAM_NAMES
            if param in request.query_params
        ]

    def _is_search_request(self):
        return bool(self._get_active_search_params())

    def list(self, request, *args, **kwargs):
        if not self._is_search_request():
            return super().list(request)

        from documents.search import SearchQueryError
        from documents.search import TantivyBackend
        from documents.search import TantivyRelevanceList
        from documents.search import get_backend
        from documents.search import search_query_error_messages

        def parse_search_params() -> SearchParams:
            """Extract query string, search mode, and ordering from request."""
            active = self._get_active_search_params(request)
            if len(active) > 1:
                raise ValidationError(
                    {
                        "detail": _(
                            "Specify only one of text, title_search, query, or more_like_id.",
                        ),
                    },
                )

            ordering_param = request.query_params.get("ordering", "")
            sort_reverse = ordering_param.startswith("-")
            sort_field_name = ordering_param.lstrip("-") or None
            # "score" means relevance order — Tantivy handles it natively,
            # so treat it as a Tantivy sort to preserve the ranked order through
            # the ORM intersection step.
            use_tantivy_sort = (
                sort_field_name in TantivyBackend.SORTABLE_FIELDS
                or sort_field_name is None
                or sort_field_name == "score"
            )

            try:
                page_num = int(request.query_params.get("page", 1))
            except (TypeError, ValueError):
                page_num = 1
            page_size = (
                self.paginator.get_page_size(request) or self.paginator.page_size
            )

            return SearchParams(
                sort_field_name=sort_field_name,
                sort_reverse=sort_reverse,
                use_tantivy_sort=use_tantivy_sort,
                page_num=page_num,
                page_size=page_size,
            )

        def intersect_and_order(
            all_ids: list[int],
            filtered_qs: QuerySet[Document],
            *,
            use_tantivy_sort: bool,
        ) -> list[int]:
            """Intersect search IDs with ORM-visible IDs, preserving order."""
            if not all_ids:
                return []
            if use_tantivy_sort:
                if len(all_ids) <= _TANTIVY_INTERSECT_THRESHOLD:
                    # Small result set: targeted IN-clause avoids a full-table scan.
                    visible_ids = set(
                        filtered_qs.filter(pk__in=all_ids).values_list("pk", flat=True),
                    )
                else:
                    # Large result set: full-table scan + Python intersection is faster
                    # than a large IN-clause on SQLite.
                    visible_ids = set(
                        filtered_qs.values_list("pk", flat=True),
                    )
                return [doc_id for doc_id in all_ids if doc_id in visible_ids]
            return list(
                filtered_qs.filter(id__in=all_ids).values_list("pk", flat=True),
            )

        def run_text_search(
            backend: TantivyBackend,
            user: User | None,
            filtered_qs: QuerySet[Document],
        ) -> SearchResultPage:
            """Handle text/title/query search: IDs, ORM intersection, page highlights."""
            query_str, search_mode = _get_tantivy_query_and_mode(request.query_params)

            # "score" is not a real Tantivy sort field — it means relevance order,
            # which is Tantivy's default when no sort field is specified.
            is_score_sort = sort_field_name == "score"
            all_ids = backend.search_ids(
                query_str,
                user=user,
                sort_field=(
                    None if (not use_tantivy_sort or is_score_sort) else sort_field_name
                ),
                sort_reverse=sort_reverse,
                search_mode=search_mode,
            )
            ordered_ids = intersect_and_order(
                all_ids,
                filtered_qs,
                use_tantivy_sort=use_tantivy_sort,
            )
            # Tantivy returns relevance results best-first (descending score).
            # ordering=score (ascending, worst-first) requires a reversal.
            if is_score_sort and not sort_reverse:
                ordered_ids = list(reversed(ordered_ids))

            page_offset = (page_num - 1) * page_size
            page_ids = ordered_ids[page_offset : page_offset + page_size]
            page_hits = backend.highlight_hits(
                query_str,
                page_ids,
                search_mode=search_mode,
                rank_start=page_offset + 1,
            )
            return SearchResultPage(
                ordered_ids=ordered_ids,
                hits=page_hits,
                page_offset=page_offset,
            )

        def run_more_like_this(
            backend: TantivyBackend,
            user: User | None,
            filtered_qs: QuerySet[Document],
        ) -> SearchResultPage:
            """Handle more_like_id search: permission check, IDs, stub hits."""
            more_like_doc_id = _get_more_like_id(request.query_params, user)

            all_ids = backend.more_like_this_ids(more_like_doc_id, user=user)
            ordered_ids = intersect_and_order(
                all_ids,
                filtered_qs,
                use_tantivy_sort=True,
            )

            page_offset = (page_num - 1) * page_size
            page_ids = ordered_ids[page_offset : page_offset + page_size]
            page_hits = [
                SearchHit(id=doc_id, score=0.0, rank=rank, highlights={})
                for rank, doc_id in enumerate(page_ids, start=page_offset + 1)
            ]
            return SearchResultPage(
                ordered_ids=ordered_ids,
                hits=page_hits,
                page_offset=page_offset,
            )

        try:
            sort_field_name, sort_reverse, use_tantivy_sort, page_num, page_size = (
                parse_search_params()
            )

            backend = get_backend()
            filtered_qs = self.filter_queryset(self.get_queryset())
            user = None if request.user.is_superuser else request.user

            if "more_like_id" in request.query_params:
                result = run_more_like_this(backend, user, filtered_qs)
            else:
                result = run_text_search(backend, user, filtered_qs)

            rl = TantivyRelevanceList(
                result.ordered_ids,
                result.hits,
                result.page_offset,
            )
            page = self.paginate_queryset(rl)

            if page is not None:
                serializer = self.get_serializer(page, many=True)
                response = self.get_paginated_response(serializer.data)
                response.data["corrected_query"] = None
                if get_boolean(
                    str(request.query_params.get("include_selection_data", "false")),
                ):
                    # NOTE: pk__in=ordered_ids generates a large SQL IN clause
                    # for big result sets.  Acceptable today but may need a temp
                    # table or chunked approach if selection_data becomes slow
                    # at scale (tens of thousands of matching documents).
                    response.data["selection_data"] = (
                        self._get_selection_data_for_queryset(
                            filtered_qs.filter(pk__in=result.ordered_ids),
                        )
                    )
                return response

            serializer = self.get_serializer(result.hits, many=True)
            return Response(serializer.data)

        except NotFound:
            raise
        except PermissionDenied as e:
            invalid_more_like_id_message = _("Invalid more_like_id")
            if str(e.detail) == str(invalid_more_like_id_message):
                return HttpResponseForbidden(invalid_more_like_id_message)
            return HttpResponseForbidden(_("Insufficient permissions."))
        except ValidationError:
            raise
        except SearchQueryError as e:
            # User-fixable query error(s) (e.g. unparsable dates/numbers):
            # surface every offending field's message, not just the first,
            # so the user can fix them all in one round-trip.
            raise ValidationError({"query": search_query_error_messages(e)}) from e

    @action(detail=False, methods=["GET"], name="Get Next ASN")
    def next_asn(self, request, *args, **kwargs):
        max_asn = Document.objects.aggregate(
            Max("archive_serial_number", default=0),
        ).get(
            "archive_serial_number__max",
        )
        return Response(max_asn + 1)
