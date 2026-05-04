import itertools
import logging
import os
import platform
import re
import tempfile
import zipfile
from collections import defaultdict
from collections import deque
from datetime import datetime
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path
from time import mktime
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal
from unicodedata import normalize
from urllib.parse import quote
from urllib.parse import urlparse

import httpx
import magic
import pathvalidate
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import connections
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Avg
from django.db.models import Case
from django.db.models import Count
from django.db.models import F
from django.db.models import IntegerField
from django.db.models import Max
from django.db.models import Model
from django.db.models import OuterRef
from django.db.models import Prefetch
from django.db.models import Q
from django.db.models import QuerySet
from django.db.models import Subquery
from django.db.models import Sum
from django.db.models import When
from django.db.models.functions import Coalesce
from django.db.models.functions import Lower
from django.db.models.manager import Manager
from django.http import FileResponse
from django.http import Http404
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.http import HttpResponseRedirect
from django.http import HttpResponseServerError
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.timezone import make_aware
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import condition
from django.views.decorators.http import last_modified
from django.views.generic import TemplateView
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_serializer
from drf_spectacular.utils import extend_schema_view
from drf_spectacular.utils import inline_serializer
from guardian.utils import get_group_obj_perms_model
from guardian.utils import get_user_obj_perms_model
from langdetect import detect
from packaging import version as packaging_version
from redis import Redis
from rest_framework import parsers
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.filters import SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.viewsets import ModelViewSet
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.viewsets import ViewSet

from documents import bulk_edit
from documents.bulk_download import ArchiveOnlyStrategy
from documents.bulk_download import OriginalAndArchiveStrategy
from documents.bulk_download import OriginalsOnlyStrategy
from documents.caching import get_llm_suggestion_cache
from documents.caching import get_metadata_cache
from documents.caching import get_suggestion_cache
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
from documents.conditionals import thumbnail_last_modified
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.file_handling import format_filename
from documents.filters import CorrespondentFilterSet
from documents.filters import CustomFieldFilterSet
from documents.filters import DocumentFilterSet
from documents.filters import DocumentsOrderingFilter
from documents.filters import DocumentTypeFilterSet
from documents.filters import ObjectOwnedOrGrantedPermissionsFilter
from documents.filters import ObjectOwnedPermissionsFilter
from documents.filters import PaperlessTaskFilterSet
from documents.filters import ShareLinkBundleFilterSet
from documents.filters import ShareLinkFilterSet
from documents.filters import StoragePathFilterSet
from documents.filters import TagFilterSet
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
from documents.models import SavedView
from documents.models import ShareLink
from documents.models import ShareLinkBundle
from documents.models import StoragePath
from documents.models import Tag
from documents.models import UiSettings
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.permissions import AcknowledgeTasksPermissions
from documents.permissions import PaperlessAdminPermissions
from documents.permissions import PaperlessNotePermissions
from documents.permissions import PaperlessObjectPermissions
from documents.permissions import ViewDocumentsPermissions
from documents.permissions import annotate_document_count_for_related_queryset
from documents.permissions import get_document_count_filter_for_user
from documents.permissions import get_objects_for_user_owner_aware
from documents.permissions import has_global_statistics_permission
from documents.permissions import has_perms_owner_aware
from documents.permissions import has_system_status_permission
from documents.permissions import set_permissions_for_object
from documents.plugins.date_parsing import get_date_parser
from documents.schema import generate_object_with_permissions_schema
from documents.serialisers import AcknowledgeTasksViewSerializer
from documents.serialisers import BulkDownloadSerializer
from documents.serialisers import BulkEditObjectsSerializer
from documents.serialisers import BulkEditSerializer
from documents.serialisers import CorrespondentSerializer
from documents.serialisers import CustomFieldSerializer
from documents.serialisers import DeleteDocumentsSerializer
from documents.serialisers import DocumentListSerializer
from documents.serialisers import DocumentSerializer
from documents.serialisers import DocumentTypeSerializer
from documents.serialisers import DocumentVersionLabelSerializer
from documents.serialisers import DocumentVersionSerializer
from documents.serialisers import EditPdfDocumentsSerializer
from documents.serialisers import EmailSerializer
from documents.serialisers import MergeDocumentsSerializer
from documents.serialisers import NotesSerializer
from documents.serialisers import PostDocumentSerializer
from documents.serialisers import RemovePasswordDocumentsSerializer
from documents.serialisers import ReprocessDocumentsSerializer
from documents.serialisers import RotateDocumentsSerializer
from documents.serialisers import RunTaskSerializer
from documents.serialisers import SavedViewSerializer
from documents.serialisers import SearchResultSerializer
from documents.serialisers import SerializerWithPerms
from documents.serialisers import ShareLinkBundleSerializer
from documents.serialisers import ShareLinkSerializer
from documents.serialisers import StoragePathSerializer
from documents.serialisers import StoragePathTestSerializer
from documents.serialisers import TagSerializer
from documents.serialisers import TaskSerializerV9
from documents.serialisers import TaskSerializerV10
from documents.serialisers import TaskSummarySerializer
from documents.serialisers import TrashSerializer
from documents.serialisers import UiSettingsViewSerializer
from documents.serialisers import WorkflowActionSerializer
from documents.serialisers import WorkflowSerializer
from documents.serialisers import WorkflowTriggerSerializer
from documents.signals import document_updated
from documents.tasks import build_share_link_bundle
from documents.tasks import consume_file
from documents.tasks import empty_trash
from documents.tasks import llmindex_index
from documents.tasks import sanity_check
from documents.tasks import train_classifier
from documents.tasks import update_document_parent_tags
from documents.utils import get_boolean
from documents.versioning import VersionResolutionError
from documents.versioning import get_latest_version_for_root
from documents.versioning import get_request_version_param
from documents.versioning import get_root_document
from documents.versioning import resolve_requested_version_for_root
from paperless import version
from paperless.celery import app as celery_app
from paperless.config import AIConfig
from paperless.config import GeneralConfig
from paperless.models import ApplicationConfiguration
from paperless.parsers.registry import get_parser_registry
from paperless.serialisers import GroupSerializer
from paperless.serialisers import UserSerializer
from paperless.views import StandardPagination
from paperless_ai.ai_classifier import get_ai_document_classification
from paperless_ai.chat import stream_chat_with_documents
from paperless_ai.matching import extract_unmatched_names
from paperless_ai.matching import match_correspondents_by_name
from paperless_ai.matching import match_document_types_by_name
from paperless_ai.matching import match_storage_paths_by_name
from paperless_ai.matching import match_tags_by_name
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.oauth import PaperlessMailOAuth2Manager
from paperless_mail.serialisers import MailAccountSerializer
from paperless_mail.serialisers import MailRuleSerializer

if settings.AUDIT_LOG_ENABLED:
    from auditlog.models import LogEntry

logger = logging.getLogger("paperless.api")

# Crossover point for intersect_and_order: below this count use a targeted
# IN-clause query; at or above this count fall back to a full-table scan +
# Python set intersection.  The IN-clause is faster for small result sets but
# degrades on SQLite with thousands of parameters.  PostgreSQL handles large IN
# clauses efficiently, so this threshold mainly protects SQLite users.
_TANTIVY_INTERSECT_THRESHOLD = 5_000
_TANTIVY_SEARCH_PARAM_NAMES = ("text", "title_search", "query", "more_like_id")


def _get_tantivy_query_and_mode(params):
    from documents.search import SearchMode

    if "text" in params:
        return str(params["text"]), SearchMode.TEXT
    if "title_search" in params:
        return str(params["title_search"]), SearchMode.TITLE
    if "query" in params:
        return str(params["query"]), SearchMode.QUERY
    return None


def _get_more_like_id(query_params: dict[str, Any], user: User) -> int:
    try:
        more_like_doc_id = int(query_params["more_like_id"])
        more_like_doc = Document.objects.select_related("owner").get(
            pk=more_like_doc_id,
        )
    except (TypeError, ValueError, Document.DoesNotExist):
        raise PermissionDenied(_("Invalid more_like_id"))

    if not has_perms_owner_aware(
        user,
        "view_document",
        more_like_doc,
    ):
        raise PermissionDenied(_("Insufficient permissions."))

    return more_like_doc_id


class IndexView(TemplateView):
    template_name = "index.html"

    def get_frontend_language(self):
        if hasattr(
            self.request.user,
            "ui_settings",
        ) and self.request.user.ui_settings.settings.get("language"):
            lang = self.request.user.ui_settings.settings.get("language")
        else:
            lang = get_language()
        # This is here for the following reason:
        # Django identifies languages in the form "en-us"
        # However, angular generates locales as "en-US".
        # this translates between these two forms.
        if "-" in lang:
            first = lang[: lang.index("-")]
            second = lang[lang.index("-") + 1 :]
            return f"{first}-{second.upper()}"
        return lang

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cookie_prefix"] = settings.COOKIE_PREFIX
        context["username"] = self.request.user.username
        context["full_name"] = self.request.user.get_full_name()
        context["styles_css"] = f"frontend/{self.get_frontend_language()}/styles.css"
        context["runtime_js"] = f"frontend/{self.get_frontend_language()}/runtime.js"
        context["polyfills_js"] = (
            f"frontend/{self.get_frontend_language()}/polyfills.js"
        )
        context["main_js"] = f"frontend/{self.get_frontend_language()}/main.js"
        context["webmanifest"] = (
            f"frontend/{self.get_frontend_language()}/manifest.webmanifest"
        )
        context["apple_touch_icon"] = (
            f"frontend/{self.get_frontend_language()}/apple-touch-icon.png"
        )
        return context


class PassUserMixin(GenericAPIView[Any]):
    """
    Pass a user object to serializer
    """

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        if isinstance(serializer_class, type) and issubclass(
            serializer_class,
            SerializerWithPerms,
        ):
            kwargs.setdefault("user", self.request.user)
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


class BulkPermissionMixin:
    """
    Prefetch Django-Guardian permissions for a list before serialization, to avoid N+1 queries.
    """

    def _get_object_perms(
        self,
        objects: list,
        perm_codenames: list[str],
        actor: Literal["users", "groups"],
    ) -> dict[int, dict[str, list[int]]]:
        """
        Collect object-level permissions for either users or groups.
        """
        model = self.queryset.model
        obj_perm_model = (
            get_user_obj_perms_model(model)
            if actor == "users"
            else get_group_obj_perms_model(model)
        )
        id_field = "user_id" if actor == "users" else "group_id"
        ctype = ContentType.objects.get_for_model(model)
        object_pks = [obj.pk for obj in objects]

        perms_qs = obj_perm_model.objects.filter(
            content_type=ctype,
            object_pk__in=object_pks,
            permission__codename__in=perm_codenames,
        ).values_list("object_pk", id_field, "permission__codename")

        perms: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
        for object_pk, actor_id, codename in perms_qs:
            perms[int(object_pk)][codename].append(actor_id)

        # Ensure that all objects have all codenames, even if empty
        for pk in object_pks:
            for codename in perm_codenames:
                perms[pk][codename]

        return perms

    def get_serializer_context(self):
        """
        Get all permissions of the current list of objects at once and pass them to the serializer.
        This avoid fetching permissions object by object in database.
        """
        context = super().get_serializer_context()
        try:
            full_perms = get_boolean(
                str(self.request.query_params.get("full_perms", "false")),
            )
        except ValueError:
            full_perms = False

        if not full_perms:
            return context

        # Check which objects are being paginated
        page = getattr(self, "paginator", None)
        if page and hasattr(page, "page"):
            queryset = page.page.object_list
        elif hasattr(self, "page"):
            queryset = self.page
        else:
            queryset = self.filter_queryset(self.get_queryset())

        model_name = self.queryset.model.__name__.lower()
        permission_name_view = f"view_{model_name}"
        permission_name_change = f"change_{model_name}"

        user_perms = self._get_object_perms(
            objects=queryset,
            perm_codenames=[permission_name_view, permission_name_change],
            actor="users",
        )
        group_perms = self._get_object_perms(
            objects=queryset,
            perm_codenames=[permission_name_view, permission_name_change],
            actor="groups",
        )

        context["users_view_perms"] = {
            pk: user_perms[pk][permission_name_view] for pk in user_perms
        }
        context["users_change_perms"] = {
            pk: user_perms[pk][permission_name_change] for pk in user_perms
        }
        context["groups_view_perms"] = {
            pk: group_perms[pk][permission_name_view] for pk in group_perms
        }
        context["groups_change_perms"] = {
            pk: group_perms[pk][permission_name_change] for pk in group_perms
        }

        return context


class PermissionsAwareDocumentCountMixin(BulkPermissionMixin, PassUserMixin):
    """Mixin to add document count to queryset, permissions-aware if needed"""

    # Default is simple relation path, override for through-table/count specialization.
    document_count_through: type[Model] | None = None
    document_count_source_field: str | None = None

    def _get_document_count_source_field(self) -> str:
        if self.document_count_source_field is None:
            msg = (
                "document_count_source_field must be set when "
                "document_count_through is configured"
            )
            raise ValueError(msg)
        return self.document_count_source_field

    def get_document_count_filter(self):
        request = getattr(self, "request", None)
        user = getattr(request, "user", None) if request else None
        return get_document_count_filter_for_user(user)

    def get_queryset(self):
        base_qs = super().get_queryset()

        # Use optimized through-table counting when configured.
        if self.document_count_through:
            user = getattr(getattr(self, "request", None), "user", None)
            return annotate_document_count_for_related_queryset(
                base_qs,
                through_model=self.document_count_through,
                related_object_field=self._get_document_count_source_field(),
                user=user,
            )

        # Fallback: simple Count on relation with permission filter.
        filter = self.get_document_count_filter()
        return base_qs.annotate(
            document_count=Count("documents", filter=filter),
        )


@extend_schema_view(**generate_object_with_permissions_schema(CorrespondentSerializer))
class CorrespondentViewSet(
    PermissionsAwareDocumentCountMixin,
    ModelViewSet[Correspondent],
):
    model = Correspondent

    queryset = Correspondent.objects.select_related("owner").order_by(Lower("name"))

    serializer_class = CorrespondentSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = CorrespondentFilterSet
    ordering_fields = (
        "name",
        "matching_algorithm",
        "match",
        "document_count",
        "last_correspondence",
    )

    def list(self, request, *args, **kwargs):
        if request.query_params.get("last_correspondence", None):
            self.queryset = self.queryset.annotate(
                last_correspondence=Max("documents__created"),
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        self.queryset = self.queryset.annotate(
            last_correspondence=Max("documents__created"),
        )
        return super().retrieve(request, *args, **kwargs)


@extend_schema_view(**generate_object_with_permissions_schema(TagSerializer))
class TagViewSet(PermissionsAwareDocumentCountMixin, ModelViewSet[Tag]):
    model = Tag
    serializer_class = TagSerializer
    document_count_through = Document.tags.through
    document_count_source_field = "tag_id"

    queryset = Tag.objects.select_related("owner").order_by(
        Lower("name"),
    )

    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = TagFilterSet
    ordering_fields = ("color", "name", "matching_algorithm", "match", "document_count")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["document_count_filter"] = self.get_document_count_filter()
        if hasattr(self, "_children_map"):
            context["children_map"] = self._children_map
        return context

    def list(self, request, *args, **kwargs):
        """
        Build a children map once to avoid per-parent queries in the serializer.
        """
        queryset = self.filter_queryset(self.get_queryset())
        ordering = OrderingFilter().get_ordering(request, queryset, self) or (
            Lower("name"),
        )
        queryset = queryset.order_by(*ordering)

        all_tags = list(queryset)
        descendant_pks = {pk for tag in all_tags for pk in tag.get_descendants_pks()}

        if descendant_pks:
            user = getattr(getattr(self, "request", None), "user", None)
            children_source = list(
                annotate_document_count_for_related_queryset(
                    Tag.objects.filter(
                        pk__in=descendant_pks | {t.pk for t in all_tags},
                    ).select_related("owner"),
                    through_model=self.document_count_through,
                    related_object_field=self._get_document_count_source_field(),
                    user=user,
                ).order_by(*ordering),
            )
        else:
            children_source = all_tags

        children_map = {}
        for tag in children_source:
            children_map.setdefault(tag.tn_parent_id, []).append(tag)
        self._children_map = children_map

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        response.data["display_count"] = len(children_source)
        api_version = int(request.version or settings.REST_FRAMEWORK["DEFAULT_VERSION"])
        if descendant_pks and api_version < 10:
            # Include children in the "all" field, if needed
            response.data["all"] = [tag.pk for tag in children_source]
        return response

    def perform_update(self, serializer):
        old_parent = self.get_object().get_parent()
        tag = serializer.save()
        new_parent = tag.get_parent()
        if new_parent and old_parent != new_parent:
            update_document_parent_tags(tag, new_parent)


@extend_schema_view(**generate_object_with_permissions_schema(DocumentTypeSerializer))
class DocumentTypeViewSet(
    PermissionsAwareDocumentCountMixin,
    ModelViewSet[DocumentType],
):
    model = DocumentType

    queryset = DocumentType.objects.select_related("owner").order_by(Lower("name"))

    serializer_class = DocumentTypeSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = DocumentTypeFilterSet
    ordering_fields = ("name", "matching_algorithm", "match", "document_count")


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
        ObjectOwnedOrGrantedPermissionsFilter,
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
        correspondents = Correspondent.objects.annotate(
            document_count=Count(
                "documents",
                filter=Q(documents__in=queryset),
                distinct=True,
            ),
        )
        tags = Tag.objects.annotate(
            document_count=Count(
                "documents",
                filter=Q(documents__in=queryset),
                distinct=True,
            ),
        )
        document_types = DocumentType.objects.annotate(
            document_count=Count(
                "documents",
                filter=Q(documents__in=queryset),
                distinct=True,
            ),
        )
        storage_paths = StoragePath.objects.annotate(
            document_count=Count(
                "documents",
                filter=Q(documents__in=queryset),
                distinct=True,
            ),
        )
        custom_fields = CustomField.objects.annotate(
            document_count=Count(
                "fields__document",
                filter=Q(fields__document__in=queryset),
                distinct=True,
            ),
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

    def get_queryset(self):
        latest_version_content = Subquery(
            Document.objects.filter(root_document=OuterRef("pk"))
            .order_by("-id")
            .values("content")[:1],
        )
        return (
            Document.objects.filter(root_document__isnull=True)
            .distinct()
            .order_by("-created", "-id")
            .annotate(effective_content=Coalesce(latest_version_content, F("content")))
            .annotate(num_notes=Count("notes"))
            .select_related("correspondent", "storage_path", "document_type", "owner")
            .prefetch_related(
                Prefetch(
                    "versions",
                    queryset=Document.objects.only(
                        "id",
                        "added",
                        "checksum",
                        "version_label",
                        "root_document_id",
                    ),
                ),
                "tags",
                Prefetch(
                    "custom_fields",
                    queryset=CustomFieldInstance.objects.select_related("field"),
                ),
                "notes",
            )
        )

    def get_serializer(self, *args, **kwargs):
        fields_param = self.request.query_params.get("fields", None)
        fields = fields_param.split(",") if fields_param else None
        truncate_content = self.request.query_params.get("truncate_content", "False")
        kwargs.setdefault("context", self.get_serializer_context())
        kwargs.setdefault("fields", fields)
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
    ) -> tuple[Document, Document] | HttpResponseForbidden:
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
        return request_doc, root_doc

    def file_response(self, pk, request, disposition):
        resolved = self._resolve_request_and_root_doc(
            pk,
            request,
            include_deleted=True,
        )
        if isinstance(resolved, HttpResponseForbidden):
            return resolved
        request_doc, root_doc = resolved
        file_doc = self._get_effective_file_doc(request_doc, root_doc, request)
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
        request_doc, root_doc = resolved

        # Choose the effective document (newest version by default,
        # or explicit via ?version=).
        doc = self._get_effective_file_doc(request_doc, root_doc, request)

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
            "view_document",
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
            "view_document",
            doc,
        ):
            return HttpResponseForbidden("Insufficient permissions")

        ai_config = AIConfig()
        if not ai_config.ai_enabled:
            return HttpResponseBadRequest("AI is required for this feature")

        cached_llm_suggestions = get_llm_suggestion_cache(
            doc.pk,
            backend=ai_config.llm_backend,
        )

        if cached_llm_suggestions:
            refresh_suggestions_cache(doc.pk)
            return Response(cached_llm_suggestions.suggestions)

        try:
            llm_suggestions = get_ai_document_classification(doc, request.user)
        except ValueError as exc:
            logger.exception(
                "Invalid AI configuration while generating suggestions for "
                "document %s: %s",
                doc.pk,
                exc,
                exc_info=True,
            )
            raise ValidationError({"ai": [_("Invalid AI configuration.")]}) from exc

        matched_tags = match_tags_by_name(
            llm_suggestions.get("tags", []),
            request.user,
        )
        matched_correspondents = match_correspondents_by_name(
            llm_suggestions.get("correspondents", []),
            request.user,
        )
        matched_types = match_document_types_by_name(
            llm_suggestions.get("document_types", []),
            request.user,
        )
        matched_paths = match_storage_paths_by_name(
            llm_suggestions.get("storage_paths", []),
            request.user,
        )

        resp_data = {
            "title": llm_suggestions.get("title"),
            "tags": [t.id for t in matched_tags],
            "suggested_tags": extract_unmatched_names(
                llm_suggestions.get("tags", []),
                matched_tags,
            ),
            "correspondents": [c.id for c in matched_correspondents],
            "suggested_correspondents": extract_unmatched_names(
                llm_suggestions.get("correspondents", []),
                matched_correspondents,
            ),
            "document_types": [d.id for d in matched_types],
            "suggested_document_types": extract_unmatched_names(
                llm_suggestions.get("document_types", []),
                matched_types,
            ),
            "storage_paths": [s.id for s in matched_paths],
            "suggested_storage_paths": extract_unmatched_names(
                llm_suggestions.get("storage_paths", []),
                matched_paths,
            ),
            "dates": llm_suggestions.get("dates", []),
        }

        set_llm_suggestions_cache(doc.pk, resp_data, backend=ai_config.llm_backend)

        return Response(resp_data)

    @action(methods=["get"], detail=True, filter_backends=[])
    @method_decorator(cache_control(no_cache=True))
    @method_decorator(
        condition(etag_func=preview_etag, last_modified_func=preview_last_modified),
    )
    def preview(self, request, pk=None):
        resolved = self._resolve_request_and_root_doc(pk, request)
        if isinstance(resolved, HttpResponseForbidden):
            return resolved
        request_doc, root_doc = resolved

        try:
            file_doc = self._get_effective_file_doc(request_doc, root_doc, request)

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
    @method_decorator(last_modified(thumbnail_last_modified))
    def thumb(self, request, pk=None):
        resolved = self._resolve_request_and_root_doc(pk, request)
        if isinstance(resolved, HttpResponseForbidden):
            return resolved
        request_doc, root_doc = resolved

        try:
            file_doc = self._get_effective_file_doc(request_doc, root_doc, request)
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
                doc.save()

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
            doc.save()

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
                .only("pk", "created", "expiration", "slug")
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

        documents = Document.objects.select_related("owner").filter(pk__in=document_ids)
        for document in documents:
            if request.user is not None and not has_perms_owner_aware(
                request.user,
                "view_document",
                document,
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
            if request.user is not None and not has_perms_owner_aware(
                request.user,
                "change_document",
                root_doc,
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

        current = (
            Document.objects.filter(Q(id=root_doc.id) | Q(root_document=root_doc))
            .order_by("-id")
            .first()
        )

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


class ChatStreamingSerializer(serializers.Serializer[dict[str, Any]]):
    q = serializers.CharField(required=True)
    document_id = serializers.IntegerField(required=False, allow_null=True)


@method_decorator(
    [
        ensure_csrf_cookie,
        cache_control(no_cache=True),
    ],
    name="dispatch",
)
class ChatStreamingView(GenericAPIView[Any]):
    permission_classes = (IsAuthenticated,)
    serializer_class = ChatStreamingSerializer

    def post(self, request, *args, **kwargs):
        request.compress_exempt = True
        ai_config = AIConfig()
        if not ai_config.ai_enabled:
            return HttpResponseBadRequest("AI is required for this feature")

        try:
            question = request.data["q"]
        except KeyError:
            return HttpResponseBadRequest("Invalid request")

        doc_id = request.data.get("document_id")

        if doc_id:
            try:
                document = Document.objects.get(id=doc_id)
            except Document.DoesNotExist:
                return HttpResponseBadRequest("Document not found")

            if not has_perms_owner_aware(request.user, "view_document", document):
                return HttpResponseForbidden("Insufficient permissions")

            documents = [document]
        else:
            documents = get_objects_for_user_owner_aware(
                request.user,
                "view_document",
                Document,
            )

        response = StreamingHttpResponse(
            stream_chat_with_documents(query_str=question, documents=documents),
            content_type="text/event-stream",
        )
        return response


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

        from documents.search import SearchHit
        from documents.search import TantivyBackend
        from documents.search import TantivyRelevanceList
        from documents.search import get_backend

        def parse_search_params() -> tuple[str | None, bool, bool, int, int]:
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

            return sort_field_name, sort_reverse, use_tantivy_sort, page_num, page_size

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
        ) -> tuple[list[int], list[SearchHit], int]:
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
            return ordered_ids, page_hits, page_offset

        def run_more_like_this(
            backend: TantivyBackend,
            user: User | None,
            filtered_qs: QuerySet[Document],
        ) -> tuple[list[int], list[SearchHit], int]:
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
            return ordered_ids, page_hits, page_offset

        try:
            sort_field_name, sort_reverse, use_tantivy_sort, page_num, page_size = (
                parse_search_params()
            )

            backend = get_backend()
            filtered_qs = self.filter_queryset(self.get_queryset())
            user = None if request.user.is_superuser else request.user

            if "more_like_id" in request.query_params:
                ordered_ids, page_hits, page_offset = run_more_like_this(
                    backend,
                    user,
                    filtered_qs,
                )
            else:
                ordered_ids, page_hits, page_offset = run_text_search(
                    backend,
                    user,
                    filtered_qs,
                )

            rl = TantivyRelevanceList(ordered_ids, page_hits, page_offset)
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
                            filtered_qs.filter(pk__in=ordered_ids),
                        )
                    )
                return response

            serializer = self.get_serializer(page_hits, many=True)
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
        except Exception as e:
            logger.warning(f"An error occurred listing search results: {e!s}")
            return HttpResponseBadRequest(
                "Error listing search results, check logs for more detail.",
            )

    @action(detail=False, methods=["GET"], name="Get Next ASN")
    def next_asn(self, request, *args, **kwargs):
        max_asn = Document.objects.aggregate(
            Max("archive_serial_number", default=0),
        ).get(
            "archive_serial_number__max",
        )
        return Response(max_asn + 1)


@extend_schema_view(
    list=extend_schema(
        description="Logs view",
        responses={
            (200, "application/json"): serializers.ListSerializer(
                child=serializers.CharField(),
            ),
        },
    ),
    retrieve=extend_schema(
        description="Single log view",
        operation_id="retrieve_log",
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Return only the last N entries from the log file",
                required=False,
            ),
        ],
        responses={
            (200, "application/json"): serializers.ListSerializer(
                child=serializers.CharField(),
            ),
            (404, "application/json"): None,
        },
    ),
)
class LogViewSet(ViewSet):
    permission_classes = (IsAuthenticated, PaperlessAdminPermissions)

    ALLOWED_LOG_FILES = {
        "paperless": "paperless.log",
        "mail": "mail.log",
        "celery": "celery.log",
    }

    def get_log_file(self, log_key: str) -> Path:
        return Path(settings.LOGGING_DIR) / self.ALLOWED_LOG_FILES[log_key]

    def retrieve(self, request, *args, **kwargs):
        log_key = kwargs.get("pk")
        if log_key not in self.ALLOWED_LOG_FILES:
            raise Http404

        log_file = self.get_log_file(log_key)

        if not log_file.is_file():
            raise Http404

        limit_param = request.query_params.get("limit")
        if limit_param is not None:
            try:
                limit = int(limit_param)
            except (TypeError, ValueError):
                raise ValidationError({"limit": "Must be a positive integer"})
            if limit < 1:
                raise ValidationError({"limit": "Must be a positive integer"})
        else:
            limit = None

        with log_file.open() as f:
            if limit is None:
                lines = [line.rstrip() for line in f.readlines()]
            else:
                lines = [line.rstrip() for line in deque(f, maxlen=limit)]

        return Response(lines)

    def list(self, request, *args, **kwargs):
        existing_logs = [
            log_key
            for log_key in self.ALLOWED_LOG_FILES
            if self.get_log_file(log_key).is_file()
        ]
        return Response(existing_logs)


@extend_schema_view(**generate_object_with_permissions_schema(SavedViewSerializer))
class SavedViewViewSet(BulkPermissionMixin, PassUserMixin, ModelViewSet[SavedView]):
    model = SavedView

    queryset = SavedView.objects.select_related("owner").prefetch_related(
        "filter_rules",
    )
    serializer_class = SavedViewSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    ordering_fields = ("name",)


class DocumentSelectionMixin:
    def _get_search_document_ids(
        self,
        *,
        user: User,
        filters: dict[str, Any],
    ) -> list[int] | None:
        search_filters = [
            filter_name
            for filter_name in _TANTIVY_SEARCH_PARAM_NAMES
            if filter_name in filters
        ]
        if not search_filters:
            return None
        if len(search_filters) > 1:
            raise ValidationError(
                {
                    "detail": _(
                        "Specify only one of text, title_search, query, or more_like_id.",
                    ),
                },
            )

        from documents.search import get_backend

        filter_name = search_filters[0]
        backend = get_backend()
        search_user = None if user.is_superuser else user

        if filter_name == "more_like_id":
            more_like_doc_id = _get_more_like_id(filters, user)

            search_ids = backend.more_like_this_ids(more_like_doc_id, user=search_user)
        else:
            query_str, search_mode = _get_tantivy_query_and_mode(filters)
            search_ids = backend.search_ids(
                query_str,
                user=search_user,
                search_mode=search_mode,
            )

        return search_ids

    def _resolve_document_ids(
        self,
        *,
        user: User,
        validated_data: dict[str, Any],
        permission_codename: str = "view_document",
    ) -> list[int]:
        if not validated_data.get("all", False):
            # if all is not true, just pass through the provided document ids
            return validated_data["documents"]

        # otherwise, reconstruct the document list based on the provided filters
        filters = validated_data.get("filters") or {}
        orm_filters = {
            key: value
            for key, value in filters.items()
            if key not in _TANTIVY_SEARCH_PARAM_NAMES
        }
        permitted_documents = get_objects_for_user_owner_aware(
            user,
            permission_codename,
            Document,
        )
        # orm-filtered docs
        filtered_documents = DocumentFilterSet(
            data=orm_filters,
            queryset=permitted_documents,
        ).qs.distinct()
        # tantivy-filtered docs (if search params provided)
        search_filtered_ids = self._get_search_document_ids(
            user=user,
            filters=filters,
        )
        if search_filtered_ids is not None:
            filtered_documents = filtered_documents.filter(pk__in=search_filtered_ids)
        return list(filtered_documents.values_list("pk", flat=True))


class DocumentOperationPermissionMixin(PassUserMixin, DocumentSelectionMixin):
    permission_classes = (IsAuthenticated,)
    parser_classes = (parsers.JSONParser,)
    METHOD_NAMES_REQUIRING_USER = {
        "split",
        "merge",
        "rotate",
        "delete_pages",
        "edit_pdf",
        "remove_password",
    }
    METHOD_NAMES_REQUIRING_TRIGGER_SOURCE = METHOD_NAMES_REQUIRING_USER

    def _has_document_permissions(
        self,
        *,
        user: User,
        documents: list[int],
        method,
        parameters: dict[str, Any],
    ) -> bool:
        if user.is_superuser:
            return True

        document_objs = Document.objects.select_related("owner").filter(
            pk__in=documents,
        )
        user_is_owner_of_all_documents = all(
            (doc.owner == user or doc.owner is None) for doc in document_objs
        )

        # check global and object permissions for all documents
        has_perms = user.has_perm("documents.change_document") and all(
            has_perms_owner_aware(user, "change_document", doc) for doc in document_objs
        )

        # check ownership for methods that change original document
        if (
            (
                has_perms
                and method
                in [
                    bulk_edit.set_permissions,
                    bulk_edit.delete,
                    bulk_edit.rotate,
                    bulk_edit.delete_pages,
                    bulk_edit.edit_pdf,
                    bulk_edit.remove_password,
                ]
            )
            or (
                method in [bulk_edit.merge, bulk_edit.split]
                and parameters.get("delete_originals")
            )
            or (method == bulk_edit.edit_pdf and parameters.get("update_document"))
        ):
            has_perms = user_is_owner_of_all_documents

        # check global add permissions for methods that create documents
        if (
            has_perms
            and (
                method in [bulk_edit.split, bulk_edit.merge]
                or (
                    method in [bulk_edit.edit_pdf, bulk_edit.remove_password]
                    and not parameters.get("update_document")
                )
            )
            and not user.has_perm("documents.add_document")
        ):
            has_perms = False

        # check global delete permissions for methods that delete documents
        if (
            has_perms
            and (
                method == bulk_edit.delete
                or (
                    method in [bulk_edit.merge, bulk_edit.split]
                    and parameters.get("delete_originals")
                )
            )
            and not user.has_perm("documents.delete_document")
        ):
            has_perms = False

        return has_perms

    def _execute_document_action(
        self,
        *,
        method,
        validated_data: dict[str, Any],
        operation_label: str,
    ):
        documents = self._resolve_document_ids(
            user=self.request.user,
            validated_data=validated_data,
        )
        parameters = {
            k: v
            for k, v in validated_data.items()
            if k not in {"documents", "all", "filters", "from_webui"}
        }
        user = self.request.user
        from_webui = validated_data.get("from_webui", False)

        if method.__name__ in self.METHOD_NAMES_REQUIRING_USER:
            parameters["user"] = user
        if method.__name__ in self.METHOD_NAMES_REQUIRING_TRIGGER_SOURCE:
            parameters["trigger_source"] = (
                PaperlessTask.TriggerSource.WEB_UI
                if from_webui
                else PaperlessTask.TriggerSource.API_UPLOAD
            )

        if not self._has_document_permissions(
            user=user,
            documents=documents,
            method=method,
            parameters=parameters,
        ):
            return HttpResponseForbidden("Insufficient permissions")

        try:
            result = method(documents, **parameters)
            return Response({"result": result})
        except Exception as e:
            logger.warning(f"An error occurred performing {operation_label}: {e!s}")
            return HttpResponseBadRequest(
                f"Error performing {operation_label}, check logs for more detail.",
            )


@extend_schema_view(
    post=extend_schema(
        operation_id="bulk_edit",
        description="Perform a bulk edit operation on a list of documents",
        external_docs={
            "description": "Further documentation",
            "url": "https://docs.paperless-ngx.com/api/#bulk-editing",
        },
        responses={
            200: inline_serializer(
                name="BulkEditDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class BulkEditView(DocumentOperationPermissionMixin):
    MODIFIED_FIELD_BY_METHOD = {
        "set_correspondent": "correspondent",
        "set_document_type": "document_type",
        "set_storage_path": "storage_path",
        "add_tag": "tags",
        "remove_tag": "tags",
        "modify_tags": "tags",
        "modify_custom_fields": "custom_fields",
        "set_permissions": None,
        "delete": "deleted_at",
        # These operations create new documents/versions no longer altering
        # fields on the selected document in place
        "rotate": None,
        "delete_pages": None,
        "split": None,
        "merge": None,
        "edit_pdf": None,
        "reprocess": "checksum",
        "remove_password": None,
    }

    serializer_class = BulkEditSerializer

    def post(self, request, *args, **kwargs):
        request_method = request.data.get("method")
        api_version = int(request.version or settings.REST_FRAMEWORK["DEFAULT_VERSION"])
        # TODO: remove this and related backwards compatibility code when API v9 is dropped
        if request_method in BulkEditSerializer.LEGACY_DOCUMENT_ACTION_METHODS:
            endpoint = BulkEditSerializer.MOVED_DOCUMENT_ACTION_ENDPOINTS[
                request_method
            ]
            logger.warning(
                "Deprecated bulk_edit method '%s' requested on API version %s. "
                "Use '%s' instead.",
                request_method,
                api_version,
                endpoint,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = self.request.user
        method = serializer.validated_data.get("method")
        parameters = serializer.validated_data.get("parameters")
        from_webui = serializer.validated_data.get("from_webui", False)
        documents = self._resolve_document_ids(
            user=user,
            validated_data=serializer.validated_data,
        )
        if method.__name__ in self.METHOD_NAMES_REQUIRING_USER:
            parameters["user"] = user
        if method.__name__ in self.METHOD_NAMES_REQUIRING_TRIGGER_SOURCE:
            parameters["trigger_source"] = (
                PaperlessTask.TriggerSource.WEB_UI
                if from_webui
                else PaperlessTask.TriggerSource.API_UPLOAD
            )
        if not self._has_document_permissions(
            user=user,
            documents=documents,
            method=method,
            parameters=parameters,
        ):
            return HttpResponseForbidden("Insufficient permissions")

        try:
            modified_field = self.MODIFIED_FIELD_BY_METHOD.get(method.__name__, None)
            if settings.AUDIT_LOG_ENABLED and modified_field:
                old_documents = {
                    obj["pk"]: obj
                    for obj in Document.objects.filter(pk__in=documents).values(
                        "pk",
                        "correspondent",
                        "document_type",
                        "storage_path",
                        "tags",
                        "custom_fields",
                        "deleted_at",
                        "checksum",
                    )
                }

            result = method(documents, **parameters)

            if settings.AUDIT_LOG_ENABLED and modified_field:
                new_documents = Document.objects.filter(pk__in=documents)
                for doc in new_documents:
                    old_value = old_documents[doc.pk][modified_field]
                    new_value = getattr(doc, modified_field)

                    if isinstance(new_value, Model):
                        # correspondent, document type, etc.
                        new_value = new_value.pk
                    elif isinstance(new_value, Manager):
                        # tags, custom fields
                        new_value = list(new_value.values_list("pk", flat=True))

                    LogEntry.objects.log_create(
                        instance=doc,
                        changes={
                            modified_field: [
                                old_value,
                                new_value,
                            ],
                        },
                        action=LogEntry.Action.UPDATE,
                        actor=user,
                        additional_data={
                            "reason": f"Bulk edit: {method.__name__}",
                        },
                    )

            return Response({"result": result})
        except Exception as e:
            logger.warning(f"An error occurred performing bulk edit: {e!s}")
            return HttpResponseBadRequest(
                "Error performing bulk edit, check logs for more detail.",
            )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_rotate",
        description="Rotate one or more documents",
        responses={
            200: inline_serializer(
                name="RotateDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class RotateDocumentsView(DocumentOperationPermissionMixin):
    serializer_class = RotateDocumentsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.rotate,
            validated_data=serializer.validated_data,
            operation_label="document rotate",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_merge",
        description="Merge selected documents into a new document",
        responses={
            200: inline_serializer(
                name="MergeDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class MergeDocumentsView(DocumentOperationPermissionMixin):
    serializer_class = MergeDocumentsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.merge,
            validated_data=serializer.validated_data,
            operation_label="document merge",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_delete",
        description="Move selected documents to trash",
        responses={
            200: inline_serializer(
                name="DeleteDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class DeleteDocumentsView(DocumentOperationPermissionMixin):
    serializer_class = DeleteDocumentsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.delete,
            validated_data=serializer.validated_data,
            operation_label="document delete",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_reprocess",
        description="Reprocess selected documents",
        responses={
            200: inline_serializer(
                name="ReprocessDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class ReprocessDocumentsView(DocumentOperationPermissionMixin):
    serializer_class = ReprocessDocumentsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.reprocess,
            validated_data=serializer.validated_data,
            operation_label="document reprocess",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_edit_pdf",
        description="Perform PDF edit operations on a selected document",
        responses={
            200: inline_serializer(
                name="EditPdfDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class EditPdfDocumentsView(DocumentOperationPermissionMixin):
    serializer_class = EditPdfDocumentsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.edit_pdf,
            validated_data=serializer.validated_data,
            operation_label="PDF edit",
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="documents_remove_password",
        description="Remove password protection from selected PDFs",
        responses={
            200: inline_serializer(
                name="RemovePasswordDocumentsResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class RemovePasswordDocumentsView(DocumentOperationPermissionMixin):
    serializer_class = RemovePasswordDocumentsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute_document_action(
            method=bulk_edit.remove_password,
            validated_data=serializer.validated_data,
            operation_label="password removal",
        )


@extend_schema_view(
    post=extend_schema(
        description="Upload a document via the API",
        external_docs={
            "description": "Further documentation",
            "url": "https://docs.paperless-ngx.com/api/#file-uploads",
        },
        responses={
            (200, "application/json"): OpenApiTypes.STR,
        },
    ),
)
class PostDocumentView(GenericAPIView[Any]):
    permission_classes = (IsAuthenticated,)
    serializer_class = PostDocumentSerializer
    parser_classes = (parsers.MultiPartParser,)

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm("documents.add_document"):
            return HttpResponseForbidden("Insufficient permissions")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_name, doc_data = serializer.validated_data.get("document")
        correspondent_id = serializer.validated_data.get("correspondent")
        document_type_id = serializer.validated_data.get("document_type")
        storage_path_id = serializer.validated_data.get("storage_path")
        tag_ids = serializer.validated_data.get("tags")
        title = serializer.validated_data.get("title")
        created = serializer.validated_data.get("created")
        archive_serial_number = serializer.validated_data.get("archive_serial_number")
        cf = serializer.validated_data.get("custom_fields")
        from_webui = serializer.validated_data.get("from_webui")

        t = int(mktime(datetime.now().timetuple()))

        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

        temp_file_path = Path(tempfile.mkdtemp(dir=settings.SCRATCH_DIR)) / Path(
            pathvalidate.sanitize_filename(doc_name),
        )

        temp_file_path.write_bytes(doc_data)

        os.utime(temp_file_path, times=(t, t))

        input_doc = ConsumableDocument(
            source=DocumentSource.WebUI if from_webui else DocumentSource.ApiUpload,
            original_file=temp_file_path,
        )
        custom_fields = None
        if isinstance(cf, dict) and cf:
            custom_fields = cf
        elif isinstance(cf, list) and cf:
            custom_fields = dict.fromkeys(cf, None)
        input_doc_overrides = DocumentMetadataOverrides(
            filename=doc_name,
            title=title,
            correspondent_id=correspondent_id,
            document_type_id=document_type_id,
            storage_path_id=storage_path_id,
            tag_ids=tag_ids,
            created=created,
            asn=archive_serial_number,
            owner_id=request.user.id,
            custom_fields=custom_fields,
        )

        async_task = consume_file.apply_async(
            kwargs={"input_doc": input_doc, "overrides": input_doc_overrides},
            headers={
                "trigger_source": (
                    PaperlessTask.TriggerSource.WEB_UI
                    if from_webui
                    else PaperlessTask.TriggerSource.API_UPLOAD
                ),
            },
        )

        return Response(async_task.id)


@extend_schema_view(
    post=extend_schema(
        description="Get selection data for the selected documents",
        responses={
            (200, "application/json"): inline_serializer(
                name="SelectionData",
                fields={
                    "selected_correspondents": serializers.ListSerializer(
                        child=inline_serializer(
                            name="CorrespondentCounts",
                            fields={
                                "id": serializers.IntegerField(),
                                "document_count": serializers.IntegerField(),
                            },
                        ),
                    ),
                    "selected_tags": serializers.ListSerializer(
                        child=inline_serializer(
                            name="TagCounts",
                            fields={
                                "id": serializers.IntegerField(),
                                "document_count": serializers.IntegerField(),
                            },
                        ),
                    ),
                    "selected_document_types": serializers.ListSerializer(
                        child=inline_serializer(
                            name="DocumentTypeCounts",
                            fields={
                                "id": serializers.IntegerField(),
                                "document_count": serializers.IntegerField(),
                            },
                        ),
                    ),
                    "selected_storage_paths": serializers.ListSerializer(
                        child=inline_serializer(
                            name="StoragePathCounts",
                            fields={
                                "id": serializers.IntegerField(),
                                "document_count": serializers.IntegerField(),
                            },
                        ),
                    ),
                    "selected_custom_fields": serializers.ListSerializer(
                        child=inline_serializer(
                            name="CustomFieldCounts",
                            fields={
                                "id": serializers.IntegerField(),
                                "document_count": serializers.IntegerField(),
                            },
                        ),
                    ),
                },
            ),
        },
    ),
)
class SelectionDataView(GenericAPIView[Any]):
    permission_classes = (IsAuthenticated,)
    serializer_class = DocumentListSerializer
    parser_classes = (parsers.MultiPartParser, parsers.JSONParser)

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data.get("documents")
        permitted_documents = get_objects_for_user_owner_aware(
            request.user,
            "documents.view_document",
            Document,
        )
        if permitted_documents.filter(pk__in=ids).count() != len(ids):
            return HttpResponseForbidden("Insufficient permissions")

        correspondents = Correspondent.objects.annotate(
            document_count=Count(
                Case(When(documents__id__in=ids, then=1), output_field=IntegerField()),
            ),
        )

        tags = Tag.objects.annotate(
            document_count=Count(
                Case(When(documents__id__in=ids, then=1), output_field=IntegerField()),
            ),
        )

        types = DocumentType.objects.annotate(
            document_count=Count(
                Case(When(documents__id__in=ids, then=1), output_field=IntegerField()),
            ),
        )

        storage_paths = StoragePath.objects.annotate(
            document_count=Count(
                Case(When(documents__id__in=ids, then=1), output_field=IntegerField()),
            ),
        )

        custom_fields = CustomField.objects.annotate(
            document_count=Count(
                Case(
                    When(
                        fields__document__id__in=ids,
                        then=1,
                    ),
                    output_field=IntegerField(),
                ),
            ),
        )

        r = Response(
            {
                "selected_correspondents": [
                    {"id": t.id, "document_count": t.document_count}
                    for t in correspondents
                ],
                "selected_tags": [
                    {"id": t.id, "document_count": t.document_count} for t in tags
                ],
                "selected_document_types": [
                    {"id": t.id, "document_count": t.document_count} for t in types
                ],
                "selected_storage_paths": [
                    {"id": t.id, "document_count": t.document_count}
                    for t in storage_paths
                ],
                "selected_custom_fields": [
                    {"id": t.id, "document_count": t.document_count}
                    for t in custom_fields
                ],
            },
        )

        return r


@extend_schema_view(
    get=extend_schema(
        description="Get a list of all available tags",
        parameters=[
            OpenApiParameter(
                name="term",
                required=False,
                type=str,
                description="Term to search for",
            ),
            OpenApiParameter(
                name="limit",
                required=False,
                type=int,
                description="Number of completions to return",
            ),
        ],
        responses={
            (200, "application/json"): serializers.ListSerializer(
                child=serializers.CharField(),
            ),
        },
    ),
)
class SearchAutoCompleteView(GenericAPIView[Any]):
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        user = self.request.user if hasattr(self.request, "user") else None

        if "term" in request.query_params:
            term = request.query_params["term"].strip()
        else:
            return HttpResponseBadRequest("Term required")

        if "limit" in request.query_params:
            limit = int(request.query_params["limit"])
            if limit <= 0:
                return HttpResponseBadRequest("Invalid limit")
        else:
            limit = 10

        from documents.search import get_backend

        return Response(get_backend().autocomplete(term, limit, user))


@extend_schema_view(
    get=extend_schema(
        description="Global search",
        parameters=[
            OpenApiParameter(
                name="query",
                required=True,
                type=str,
                description="Query to search for",
            ),
            OpenApiParameter(
                name="db_only",
                required=False,
                type=bool,
                description="Search only the database",
            ),
        ],
        responses={
            (200, "application/json"): inline_serializer(
                name="SearchResult",
                fields={
                    "total": serializers.IntegerField(),
                    "documents": DocumentSerializer(many=True),
                    "saved_views": SavedViewSerializer(many=True),
                    "tags": TagSerializer(many=True),
                    "correspondents": CorrespondentSerializer(many=True),
                    "document_types": DocumentTypeSerializer(many=True),
                    "storage_paths": StoragePathSerializer(many=True),
                    "users": UserSerializer(many=True),
                    "groups": GroupSerializer(many=True),
                    "mail_rules": MailRuleSerializer(many=True),
                    "mail_accounts": MailAccountSerializer(many=True),
                    "workflows": WorkflowSerializer(many=True),
                    "custom_fields": CustomFieldSerializer(many=True),
                },
            ),
        },
    ),
)
class GlobalSearchView(PassUserMixin):
    permission_classes = (IsAuthenticated,)
    serializer_class = SearchResultSerializer

    def get(self, request, *args, **kwargs):
        from documents.search import SearchMode
        from documents.search import get_backend

        query = request.query_params.get("query", None)
        if query is None:
            return HttpResponseBadRequest("Query required")
        if len(query) < 3:
            return HttpResponseBadRequest("Query must be at least 3 characters")

        db_only = request.query_params.get("db_only", False)

        OBJECT_LIMIT = 3
        docs = []
        if request.user.has_perm("documents.view_document"):
            all_docs = get_objects_for_user_owner_aware(
                request.user,
                "view_document",
                Document,
            )
            if db_only:
                docs = all_docs.filter(title__icontains=query)[:OBJECT_LIMIT]
            else:
                user = None if request.user.is_superuser else request.user
                matching_ids = get_backend().search_ids(
                    query,
                    user=user,
                    search_mode=SearchMode.TEXT,
                    limit=OBJECT_LIMIT * 3,
                )
                docs_by_id = all_docs.in_bulk(matching_ids)
                docs = [
                    docs_by_id[doc_id]
                    for doc_id in matching_ids
                    if doc_id in docs_by_id
                ][:OBJECT_LIMIT]
        saved_views = (
            get_objects_for_user_owner_aware(
                request.user,
                "view_savedview",
                SavedView,
            ).filter(name__icontains=query)
            if request.user.has_perm("documents.view_savedview")
            else []
        )
        saved_views = saved_views[:OBJECT_LIMIT]
        tags = (
            get_objects_for_user_owner_aware(request.user, "view_tag", Tag).filter(
                name__icontains=query,
            )
            if request.user.has_perm("documents.view_tag")
            else []
        )
        tags = tags[:OBJECT_LIMIT]
        correspondents = (
            get_objects_for_user_owner_aware(
                request.user,
                "view_correspondent",
                Correspondent,
            ).filter(name__icontains=query)
            if request.user.has_perm("documents.view_correspondent")
            else []
        )
        correspondents = correspondents[:OBJECT_LIMIT]
        document_types = (
            get_objects_for_user_owner_aware(
                request.user,
                "view_documenttype",
                DocumentType,
            ).filter(name__icontains=query)
            if request.user.has_perm("documents.view_documenttype")
            else []
        )
        document_types = document_types[:OBJECT_LIMIT]
        storage_paths = (
            get_objects_for_user_owner_aware(
                request.user,
                "view_storagepath",
                StoragePath,
            ).filter(name__icontains=query)
            if request.user.has_perm("documents.view_storagepath")
            else []
        )
        storage_paths = storage_paths[:OBJECT_LIMIT]
        users = (
            User.objects.filter(username__icontains=query)
            if request.user.has_perm("auth.view_user")
            else []
        )
        users = users[:OBJECT_LIMIT]
        groups = (
            Group.objects.filter(name__icontains=query)
            if request.user.has_perm("auth.view_group")
            else []
        )
        groups = groups[:OBJECT_LIMIT]
        mail_rules = (
            get_objects_for_user_owner_aware(
                request.user,
                "view_mailrule",
                MailRule,
            ).filter(name__icontains=query)
            if request.user.has_perm("paperless_mail.view_mailrule")
            else []
        )
        mail_rules = mail_rules[:OBJECT_LIMIT]
        mail_accounts = (
            get_objects_for_user_owner_aware(
                request.user,
                "view_mailaccount",
                MailAccount,
            ).filter(name__icontains=query)
            if request.user.has_perm("paperless_mail.view_mailaccount")
            else []
        )
        mail_accounts = mail_accounts[:OBJECT_LIMIT]
        workflows = (
            Workflow.objects.filter(name__icontains=query)
            if request.user.has_perm("documents.view_workflow")
            else []
        )
        workflows = workflows[:OBJECT_LIMIT]
        custom_fields = (
            CustomField.objects.filter(name__icontains=query)
            if request.user.has_perm("documents.view_customfield")
            else []
        )
        custom_fields = custom_fields[:OBJECT_LIMIT]

        context = {
            "request": request,
        }

        docs_serializer = DocumentSerializer(docs, many=True, context=context)
        saved_views_serializer = SavedViewSerializer(
            saved_views,
            many=True,
            context=context,
        )
        tags_serializer = TagSerializer(tags, many=True, context=context)
        correspondents_serializer = CorrespondentSerializer(
            correspondents,
            many=True,
            context=context,
        )
        document_types_serializer = DocumentTypeSerializer(
            document_types,
            many=True,
            context=context,
        )
        storage_paths_serializer = StoragePathSerializer(
            storage_paths,
            many=True,
            context=context,
        )
        users_serializer = UserSerializer(users, many=True, context=context)
        groups_serializer = GroupSerializer(groups, many=True, context=context)
        mail_rules_serializer = MailRuleSerializer(
            mail_rules,
            many=True,
            context=context,
        )
        mail_accounts_serializer = MailAccountSerializer(
            mail_accounts,
            many=True,
            context=context,
        )
        workflows_serializer = WorkflowSerializer(workflows, many=True, context=context)
        custom_fields_serializer = CustomFieldSerializer(
            custom_fields,
            many=True,
            context=context,
        )

        return Response(
            {
                "total": len(docs)
                + len(saved_views)
                + len(tags)
                + len(correspondents)
                + len(document_types)
                + len(storage_paths)
                + len(users)
                + len(groups)
                + len(mail_rules)
                + len(mail_accounts)
                + len(workflows)
                + len(custom_fields),
                "documents": docs_serializer.data,
                "saved_views": saved_views_serializer.data,
                "tags": tags_serializer.data,
                "correspondents": correspondents_serializer.data,
                "document_types": document_types_serializer.data,
                "storage_paths": storage_paths_serializer.data,
                "users": users_serializer.data,
                "groups": groups_serializer.data,
                "mail_rules": mail_rules_serializer.data,
                "mail_accounts": mail_accounts_serializer.data,
                "workflows": workflows_serializer.data,
                "custom_fields": custom_fields_serializer.data,
            },
        )


@extend_schema_view(
    get=extend_schema(
        description="Get statistics for the current user",
        responses={
            (200, "application/json"): OpenApiTypes.OBJECT,
        },
    ),
)
class StatisticsView(GenericAPIView[Any]):
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        user = request.user if request.user is not None else None
        can_view_global_stats = has_global_statistics_permission(user) or user is None

        documents = (
            Document.objects.all()
            if can_view_global_stats
            else get_objects_for_user_owner_aware(
                user,
                "documents.view_document",
                Document,
            )
        )
        tags = (
            Tag.objects.all()
            if can_view_global_stats
            else get_objects_for_user_owner_aware(user, "documents.view_tag", Tag)
        ).only("id", "is_inbox_tag")
        correspondent_count = (
            Correspondent.objects.count()
            if can_view_global_stats
            else get_objects_for_user_owner_aware(
                user,
                "documents.view_correspondent",
                Correspondent,
            ).count()
        )
        document_type_count = (
            DocumentType.objects.count()
            if can_view_global_stats
            else get_objects_for_user_owner_aware(
                user,
                "documents.view_documenttype",
                DocumentType,
            ).count()
        )
        storage_path_count = (
            StoragePath.objects.count()
            if can_view_global_stats
            else get_objects_for_user_owner_aware(
                user,
                "documents.view_storagepath",
                StoragePath,
            ).count()
        )

        inbox_tag_pks = list(
            tags.filter(is_inbox_tag=True).values_list("pk", flat=True),
        )

        documents_inbox = (
            documents.filter(tags__id__in=inbox_tag_pks).values("id").distinct().count()
            if inbox_tag_pks
            else None
        )

        # Single SQL request for document stats and mime type counts
        mime_type_stats = list(
            documents.values("mime_type")
            .annotate(
                mime_type_count=Count("id"),
                mime_type_chars=Sum("content_length"),
            )
            .order_by("-mime_type_count"),
        )

        # Calculate totals from grouped results
        documents_total = sum(row["mime_type_count"] for row in mime_type_stats)
        character_count = sum(row["mime_type_chars"] or 0 for row in mime_type_stats)
        document_file_type_counts = [
            {"mime_type": row["mime_type"], "mime_type_count": row["mime_type_count"]}
            for row in mime_type_stats
        ]

        current_asn = Document.objects.aggregate(
            Max("archive_serial_number", default=0),
        ).get(
            "archive_serial_number__max",
        )

        return Response(
            {
                "documents_total": documents_total,
                "documents_inbox": documents_inbox,
                "inbox_tag": (
                    inbox_tag_pks[0] if inbox_tag_pks else None
                ),  # backwards compatibility
                "inbox_tags": (inbox_tag_pks or None),
                "document_file_type_counts": document_file_type_counts,
                "character_count": character_count,
                "tag_count": len(tags),
                "correspondent_count": correspondent_count,
                "document_type_count": document_type_count,
                "storage_path_count": storage_path_count,
                "current_asn": current_asn,
            },
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="bulk_download",
        description="Download multiple documents as a ZIP archive.",
        responses={
            (HTTPStatus.OK, "application/zip"): OpenApiTypes.BINARY,
            HTTPStatus.FORBIDDEN: None,
        },
    ),
)
class BulkDownloadView(DocumentSelectionMixin, GenericAPIView[Any]):
    permission_classes = (IsAuthenticated,)
    serializer_class = BulkDownloadSerializer
    parser_classes = (parsers.JSONParser,)

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = self._resolve_document_ids(
            user=request.user,
            validated_data=serializer.validated_data,
        )
        documents = Document.objects.filter(pk__in=ids)
        compression = serializer.validated_data.get("compression")
        content = serializer.validated_data.get("content")
        follow_filename_format = serializer.validated_data.get("follow_formatting")

        for document in documents:
            if not has_perms_owner_aware(request.user, "change_document", document):
                return HttpResponseForbidden("Insufficient permissions")

        if content == "both":
            strategy_class = OriginalAndArchiveStrategy
        elif content == "originals":
            strategy_class = OriginalsOnlyStrategy
        else:
            strategy_class = ArchiveOnlyStrategy

        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            dir=settings.SCRATCH_DIR,
            suffix="-compressed-archive",
        )
        os.close(fd)
        temp_path = Path(temp_name)

        try:
            with zipfile.ZipFile(temp_path, "w", compression) as zipf:
                strategy = strategy_class(
                    zipf,
                    follow_formatting=follow_filename_format,
                )
                for document in documents:
                    strategy.add_document(document)

            f = temp_path.open("rb")
            temp_path.unlink()
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        return FileResponse(
            f,
            as_attachment=True,
            filename="documents.zip",
            content_type="application/zip",
        )


@extend_schema_view(
    **generate_object_with_permissions_schema(StoragePathSerializer),
    test=extend_schema(
        operation_id="storage_paths_test",
        description="Test a storage path template against a document.",
        request=StoragePathTestSerializer,
        responses={
            (HTTPStatus.OK, "application/json"): OpenApiTypes.STR,
        },
    ),
)
class StoragePathViewSet(PermissionsAwareDocumentCountMixin, ModelViewSet[StoragePath]):
    model = StoragePath

    queryset = StoragePath.objects.select_related("owner").order_by(
        Lower("name"),
    )

    serializer_class = StoragePathSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = StoragePathFilterSet
    ordering_fields = ("name", "path", "matching_algorithm", "match", "document_count")

    def get_permissions(self):
        if self.action == "test":
            # Test action does not require object level permissions
            self.permission_classes = (IsAuthenticated,)
        return super().get_permissions()

    def destroy(self, request, *args, **kwargs):
        """
        When a storage path is deleted, see if documents
        using it require a rename/move
        """
        instance = self.get_object()
        doc_ids = [doc.id for doc in instance.documents.all()]

        # perform the deletion so renaming/moving can happen
        response = super().destroy(request, *args, **kwargs)

        if doc_ids:
            bulk_edit.bulk_update_documents.apply_async(
                kwargs={"document_ids": doc_ids},
                headers={"trigger_source": PaperlessTask.TriggerSource.SYSTEM},
            )

        return response

    @action(methods=["post"], detail=False)
    def test(self, request):
        """
        Test storage path against a document
        """
        serializer = StoragePathTestSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        document = serializer.validated_data.get("document")
        path = serializer.validated_data.get("path")

        result = format_filename(document, path)
        if result:
            extension = (
                Path(str(document.filename)).suffix if document.filename else ""
            ) or document.file_type
            result_path = Path(result)
            result = str(result_path.with_name(f"{result_path.name}{extension}"))
        return Response(result)


class UiSettingsView(GenericAPIView[Any]):
    queryset = UiSettings.objects.all()
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    serializer_class = UiSettingsViewSerializer

    def get(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.select_related("ui_settings").get(pk=request.user.id)
        ui_settings = {}
        if hasattr(user, "ui_settings"):
            ui_settings = user.ui_settings.settings
        if "update_checking" in ui_settings:
            ui_settings["update_checking"]["backend_setting"] = (
                settings.ENABLE_UPDATE_CHECK
            )
        else:
            ui_settings["update_checking"] = {
                "backend_setting": settings.ENABLE_UPDATE_CHECK,
            }

        ui_settings["trash_delay"] = settings.EMPTY_TRASH_DELAY

        general_config = GeneralConfig()

        ui_settings["version"] = version.__full_version_str__

        ui_settings["app_title"] = settings.APP_TITLE
        if general_config.app_title is not None and len(general_config.app_title) > 0:
            ui_settings["app_title"] = general_config.app_title
        ui_settings["app_logo"] = settings.APP_LOGO
        if general_config.app_logo is not None and len(general_config.app_logo) > 0:
            ui_settings["app_logo"] = general_config.app_logo

        ui_settings["auditlog_enabled"] = settings.AUDIT_LOG_ENABLED

        if settings.GMAIL_OAUTH_ENABLED or settings.OUTLOOK_OAUTH_ENABLED:
            manager = PaperlessMailOAuth2Manager()
            if settings.GMAIL_OAUTH_ENABLED:
                ui_settings["gmail_oauth_url"] = manager.get_gmail_authorization_url()
                request.session["oauth_state"] = manager.state
            if settings.OUTLOOK_OAUTH_ENABLED:
                ui_settings["outlook_oauth_url"] = (
                    manager.get_outlook_authorization_url()
                )
                request.session["oauth_state"] = manager.state

        ui_settings["email_enabled"] = settings.EMAIL_ENABLED

        ai_config = AIConfig()

        ui_settings["ai_enabled"] = ai_config.ai_enabled

        user_resp = {
            "id": user.id,
            "username": user.username,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "groups": list(user.groups.values_list("id", flat=True)),
        }

        if len(user.first_name) > 0:
            user_resp["first_name"] = user.first_name
        if len(user.last_name) > 0:
            user_resp["last_name"] = user.last_name

        # strip <app_label>.
        roles = map(lambda perm: re.sub(r"^\w+.", "", perm), user.get_all_permissions())
        return Response(
            {
                "user": user_resp,
                "settings": ui_settings,
                "permissions": roles,
            },
        )

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save(user=self.request.user)

        return Response(
            {
                "success": True,
            },
        )


@extend_schema_view(
    get=extend_schema(
        description="Get the current version of the Paperless-NGX server",
        responses={
            (200, "application/json"): OpenApiTypes.OBJECT,
        },
    ),
)
class RemoteVersionView(GenericAPIView[Any]):
    cache_key = "remote_version_view_latest_release"

    def get(self, request, format=None):
        current_version = packaging_version.parse(version.__full_version_str__)
        remote_version = cache.get(self.cache_key)
        if remote_version is None:
            try:
                resp = httpx.get(
                    "https://api.github.com/repos/paperless-ngx/paperless-ngx/releases/latest",
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                remote_version = data["tag_name"]
                # Some early tags used ngx-x.y.z
                remote_version = remote_version.removeprefix("ngx-")
            except ValueError as e:
                logger.debug(f"An error occurred parsing remote version json: {e}")
            except httpx.HTTPError as e:
                logger.debug(f"An error occurred checking for available updates: {e}")

            if remote_version:
                cache.set(self.cache_key, remote_version, 60 * 15)
            else:
                remote_version = "0.0.0"

        is_greater_than_current = (
            packaging_version.parse(remote_version) > current_version
        )

        return Response(
            {
                "version": remote_version,
                "update_available": is_greater_than_current,
            },
        )


class _TasksViewSetSchema(AutoSchema):
    _UNPAGINATED_ACTIONS = frozenset({"summary", "active"})

    def _get_paginator(self):
        if getattr(self.view, "action", None) in self._UNPAGINATED_ACTIONS:
            return None
        return super()._get_paginator()


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="task_id",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter tasks by Celery UUID",
            ),
        ],
    ),
    acknowledge=extend_schema(
        operation_id="acknowledge_tasks",
        description="Acknowledge a list of tasks",
        request=AcknowledgeTasksViewSerializer,
        responses={
            (200, "application/json"): inline_serializer(
                name="AcknowledgeTasks",
                fields={
                    "result": serializers.IntegerField(),
                },
            ),
        },
    ),
    run=extend_schema(
        operation_id="run_task",
        description="Manually dispatch a background task. Superuser only.",
        request=RunTaskSerializer,
        responses={
            (200, "application/json"): inline_serializer(
                name="RunTask",
                fields={"task_id": serializers.CharField()},
            ),
            (400, "application/json"): inline_serializer(
                name="RunTaskError",
                fields={"error": serializers.CharField()},
            ),
        },
    ),
    summary=extend_schema(
        responses={200: TaskSummarySerializer(many=True)},
        parameters=[
            OpenApiParameter(
                name="days",
                type={"type": "integer", "minimum": 1, "maximum": 365, "default": 30},
                location=OpenApiParameter.QUERY,
                required=False,
                description="Number of days to include in aggregation (default 30, min 1, max 365)",
            ),
        ],
    ),
    active=extend_schema(
        description="Currently pending and running tasks (capped at 50).",
        responses={200: TaskSerializerV10(many=True)},
    ),
)
class TasksViewSet(ReadOnlyModelViewSet[PaperlessTask]):
    schema = _TasksViewSetSchema()
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    pagination_class = StandardPagination
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )
    filterset_class = PaperlessTaskFilterSet
    ordering_fields = [
        "date_created",
        "date_done",
        "status",
        "task_type",
        "duration_seconds",
        "wait_time_seconds",
    ]
    ordering = ["-date_created"]
    # Needed for drf-spectacular schema generation (get_queryset touches request.user)
    queryset = PaperlessTask.objects.none()

    # v9 backwards compat: maps old task_name values to new task_type values
    _V9_TASK_NAME_TO_TYPE = {
        "check_sanity": PaperlessTask.TaskType.SANITY_CHECK,
        "llmindex_update": PaperlessTask.TaskType.LLM_INDEX,
    }

    # v9 backwards compat: maps old "type" query param values to new TriggerSource.
    # Must match the reverse of TaskSerializerV9._TRIGGER_SOURCE_TO_V9_TYPE.
    _V9_TYPE_TO_TRIGGER_SOURCES = {
        "auto_task": [
            PaperlessTask.TriggerSource.SYSTEM,
            PaperlessTask.TriggerSource.EMAIL_CONSUME,
            PaperlessTask.TriggerSource.FOLDER_CONSUME,
        ],
        "scheduled_task": [PaperlessTask.TriggerSource.SCHEDULED],
        "manual_task": [
            PaperlessTask.TriggerSource.MANUAL,
            PaperlessTask.TriggerSource.WEB_UI,
            PaperlessTask.TriggerSource.API_UPLOAD,
        ],
    }

    _RUNNABLE_TASKS = {
        PaperlessTask.TaskType.TRAIN_CLASSIFIER: (train_classifier, {}),
        PaperlessTask.TaskType.SANITY_CHECK: (sanity_check, {"raise_on_error": False}),
        PaperlessTask.TaskType.LLM_INDEX: (llmindex_index, {"rebuild": False}),
    }

    def get_serializer_class(self):
        # v9: use backwards-compatible serializer with old field names
        if self.request.version and int(self.request.version) < 10:
            return TaskSerializerV9
        return TaskSerializerV10

    def paginate_queryset(self, queryset):
        # v9: tasks endpoint was not paginated; preserve plain-list response
        if self.request.version and int(self.request.version) < 10:
            return None
        return super().paginate_queryset(queryset)

    def get_queryset(self):
        is_v9 = self.request.version and int(self.request.version) < 10
        if self.request.user.is_staff:
            queryset = PaperlessTask.objects.all()
        else:
            # Own tasks + unowned (system/scheduled) tasks. Tasks owned by other
            # users are never visible to non-staff regardless of API version.
            queryset = PaperlessTask.objects.filter(
                Q(owner=self.request.user) | Q(owner__isnull=True),
            )
        # v9 backwards compat: map old query params to new field names
        if is_v9:
            task_name = self.request.query_params.get("task_name")
            if task_name is not None:
                mapped = self._V9_TASK_NAME_TO_TYPE.get(task_name, task_name)
                queryset = queryset.filter(task_type=mapped)
            task_type_old = self.request.query_params.get("type")
            if task_type_old is not None:
                sources = self._V9_TYPE_TO_TRIGGER_SOURCES.get(task_type_old)
                if sources:
                    queryset = queryset.filter(trigger_source__in=sources)
        # v10+: direct task_id param for backwards compat
        task_id = self.request.query_params.get("task_id")
        if task_id is not None:
            queryset = queryset.filter(task_id=task_id)
        return queryset

    @action(
        methods=["post"],
        detail=False,
        permission_classes=[IsAuthenticated, AcknowledgeTasksPermissions],
    )
    def acknowledge(self, request):
        serializer = AcknowledgeTasksViewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task_ids = serializer.validated_data.get("tasks")
        tasks = self.get_queryset().filter(id__in=task_ids)
        count = tasks.update(acknowledged=True)
        return Response({"result": count})

    def get_permissions(self):
        if self.action == "summary" and has_system_status_permission(
            getattr(self.request, "user", None),
        ):
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(methods=["get"], detail=False)
    def summary(self, request):
        """Aggregated task statistics per task_type over the last N days (default 30)."""
        try:
            days = min(365, max(1, int(request.query_params.get("days", 30))))
        except (TypeError, ValueError):
            return Response(
                {"days": "Must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cutoff = timezone.now() - timedelta(days=days)
        if has_system_status_permission(request.user):
            queryset = PaperlessTask.objects.filter(date_created__gte=cutoff)
        else:
            queryset = self.get_queryset().filter(date_created__gte=cutoff)

        data = queryset.values("task_type").annotate(
            total_count=Count("id"),
            pending_count=Count("id", filter=Q(status=PaperlessTask.Status.PENDING)),
            success_count=Count("id", filter=Q(status=PaperlessTask.Status.SUCCESS)),
            failure_count=Count("id", filter=Q(status=PaperlessTask.Status.FAILURE)),
            avg_duration_seconds=Avg(
                "duration_seconds",
                filter=Q(duration_seconds__isnull=False),
            ),
            avg_wait_time_seconds=Avg(
                "wait_time_seconds",
                filter=Q(wait_time_seconds__isnull=False),
            ),
            last_run=Max("date_created"),
            last_success=Max(
                "date_done",
                filter=Q(status=PaperlessTask.Status.SUCCESS),
            ),
            last_failure=Max(
                "date_done",
                filter=Q(status=PaperlessTask.Status.FAILURE),
            ),
        )
        serializer = TaskSummarySerializer(data, many=True)
        return Response(serializer.data)

    @action(methods=["get"], detail=False)
    def active(self, request):
        """Currently pending and running tasks (capped at 50)."""
        queryset = (
            self.get_queryset()
            .filter(
                status__in=[PaperlessTask.Status.PENDING, PaperlessTask.Status.STARTED],
            )
            .order_by("-date_created")[:50]
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=["post"], detail=False)
    def run(self, request):
        """Manually dispatch a background task. Superuser only."""
        if not request.user.is_superuser:
            return HttpResponseForbidden("Insufficient permissions")
        serializer = RunTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task_type = serializer.validated_data.get("task_type")

        if task_type not in self._RUNNABLE_TASKS:
            return Response(
                {"error": f"Task type '{task_type}' cannot be manually triggered"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task_func, task_kwargs = self._RUNNABLE_TASKS[task_type]
            async_result = task_func.apply_async(
                kwargs=task_kwargs,
                headers={"trigger_source": PaperlessTask.TriggerSource.MANUAL},
            )
            return Response({"task_id": async_result.id})
        except Exception as e:
            logger.warning(f"Error running task: {e!s}")
            return HttpResponseServerError(
                "Error running task, check logs for more detail.",
            )


class ShareLinkViewSet(
    PassUserMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    GenericViewSet,
):
    model = ShareLink

    queryset = ShareLink.objects.all()

    serializer_class = ShareLinkSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = ShareLinkFilterSet
    ordering_fields = ("created", "expiration", "document")


@extend_schema_view(
    rebuild=extend_schema(
        operation_id="share_link_bundles_rebuild",
        description="Reset and re-queue a share link bundle for processing.",
        responses={
            HTTPStatus.OK: ShareLinkBundleSerializer,
            (HTTPStatus.BAD_REQUEST, "application/json"): inline_serializer(
                name="RebuildBundleError",
                fields={"detail": serializers.CharField()},
            ),
        },
    ),
)
class ShareLinkBundleViewSet(PassUserMixin, ModelViewSet[ShareLinkBundle]):
    model = ShareLinkBundle

    queryset = ShareLinkBundle.objects.all()

    serializer_class = ShareLinkBundleSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = ShareLinkBundleFilterSet
    ordering_fields = ("created", "expiration", "status")

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .prefetch_related("documents")
            .annotate(document_total=Count("documents", distinct=True))
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_ids = serializer.validated_data["document_ids"]
        documents_qs = Document.objects.filter(pk__in=document_ids).select_related(
            "owner",
        )
        found_ids = set(documents_qs.values_list("pk", flat=True))
        missing = sorted(set(document_ids) - found_ids)
        if missing:
            raise ValidationError(
                {
                    "document_ids": _(
                        "Documents not found: %(ids)s",
                    )
                    % {"ids": ", ".join(str(item) for item in missing)},
                },
            )

        documents = list(documents_qs)
        for document in documents:
            if not has_perms_owner_aware(request.user, "view_document", document):
                raise ValidationError(
                    {
                        "document_ids": _(
                            "Insufficient permissions to share document %(id)s.",
                        )
                        % {"id": document.pk},
                    },
                )

        document_map = {document.pk: document for document in documents}
        ordered_documents = [document_map[doc_id] for doc_id in document_ids]

        bundle = serializer.save(
            owner=request.user,
            documents=ordered_documents,
        )
        bundle.remove_file()
        bundle.status = ShareLinkBundle.Status.PENDING
        bundle.last_error = None
        bundle.size_bytes = None
        bundle.built_at = None
        bundle.file_path = ""
        bundle.save(
            update_fields=[
                "status",
                "last_error",
                "size_bytes",
                "built_at",
                "file_path",
            ],
        )
        build_share_link_bundle.apply_async(
            kwargs={"bundle_id": bundle.pk},
            headers={"trigger_source": PaperlessTask.TriggerSource.MANUAL},
        )
        bundle.document_total = len(ordered_documents)
        response_serializer = self.get_serializer(bundle)
        headers = self.get_success_headers(response_serializer.data)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    @action(detail=True, methods=["post"])
    def rebuild(self, request, pk=None):
        bundle = self.get_object()
        if bundle.status == ShareLinkBundle.Status.PROCESSING:
            return Response(
                {"detail": _("Bundle is already being processed.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bundle.remove_file()
        bundle.status = ShareLinkBundle.Status.PENDING
        bundle.last_error = None
        bundle.size_bytes = None
        bundle.built_at = None
        bundle.file_path = ""
        bundle.save(
            update_fields=[
                "status",
                "last_error",
                "size_bytes",
                "built_at",
                "file_path",
            ],
        )
        build_share_link_bundle.apply_async(
            kwargs={"bundle_id": bundle.pk},
            headers={"trigger_source": PaperlessTask.TriggerSource.MANUAL},
        )
        bundle.document_total = (
            getattr(bundle, "document_total", None) or bundle.documents.count()
        )
        serializer = self.get_serializer(bundle)
        return Response(serializer.data)


class SharedLinkView(View):
    authentication_classes = []
    permission_classes = []

    def get(self, request, slug):
        share_link = ShareLink.objects.filter(slug=slug).first()
        if share_link is not None:
            if (
                share_link.expiration is not None
                and share_link.expiration < timezone.now()
            ):
                return HttpResponseRedirect("/accounts/login/?sharelink_expired=1")
            return serve_file(
                doc=share_link.document,
                use_archive=share_link.file_version == "archive",
                disposition="inline",
            )

        bundle = ShareLinkBundle.objects.filter(slug=slug).first()
        if bundle is None:
            return HttpResponseRedirect("/accounts/login/?sharelink_notfound=1")

        if bundle.expiration is not None and bundle.expiration < timezone.now():
            return HttpResponseRedirect("/accounts/login/?sharelink_expired=1")

        if bundle.status in {
            ShareLinkBundle.Status.PENDING,
            ShareLinkBundle.Status.PROCESSING,
        }:
            return HttpResponse(
                _(
                    "The share link bundle is still being prepared. Please try again later.",
                ),
                status=status.HTTP_202_ACCEPTED,
            )

        file_path = bundle.absolute_file_path

        if bundle.status == ShareLinkBundle.Status.FAILED or file_path is None:
            return HttpResponse(
                _(
                    "The share link bundle is unavailable.",
                ),
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        response = FileResponse(file_path.open("rb"), content_type="application/zip")
        short_slug = bundle.slug[:12]
        download_name = f"paperless-share-{short_slug}.zip"
        filename_normalized = (
            normalize("NFKD", download_name)
            .encode(
                "ascii",
                "ignore",
            )
            .decode("ascii")
        )
        filename_encoded = quote(download_name)
        response["Content-Disposition"] = (
            f"attachment; filename='{filename_normalized}'; "
            f"filename*=utf-8''{filename_encoded}"
        )
        return response


def serve_file(
    *,
    doc: Document,
    use_archive: bool,
    disposition: str,
    follow_formatting: bool = False,
) -> FileResponse:
    if use_archive:
        if TYPE_CHECKING:
            assert doc.archive_filename

        file_handle = doc.archive_file
        filename = (
            doc.archive_filename
            if follow_formatting
            else doc.get_public_filename(archive=True)
        )
        mime_type = "application/pdf"
    else:
        if TYPE_CHECKING:
            assert doc.filename

        file_handle = doc.source_file
        filename = doc.filename if follow_formatting else doc.get_public_filename()
        mime_type = doc.mime_type
        # Support browser previewing csv files by using text mime type
        if mime_type in {"application/csv", "text/csv"} and disposition == "inline":
            mime_type = "text/plain"

    response = FileResponse(file_handle, content_type=mime_type)
    # Firefox is not able to handle unicode characters in filename field
    # RFC 5987 addresses this issue
    # see https://datatracker.ietf.org/doc/html/rfc5987#section-4.2
    # Chromium cannot handle commas in the filename
    filename_normalized = (
        normalize("NFKD", filename.replace(",", "_"))
        .encode(
            "ascii",
            "ignore",
        )
        .decode("ascii")
    )
    filename_encoded = quote(filename)
    content_disposition = (
        f"{disposition}; "
        f'filename="{filename_normalized}"; '
        f"filename*=utf-8''{filename_encoded}"
    )
    response["Content-Disposition"] = content_disposition
    return response


@extend_schema_view(
    post=extend_schema(
        operation_id="bulk_edit_objects",
        description="Perform a bulk edit operation on a list of objects",
        external_docs={
            "description": "Further documentation",
            "url": "https://docs.paperless-ngx.com/api/#objects",
        },
        responses={
            200: inline_serializer(
                name="BulkEditResult",
                fields={
                    "result": serializers.CharField(),
                },
            ),
        },
    ),
)
class BulkEditObjectsView(PassUserMixin):
    permission_classes = (IsAuthenticated,)
    serializer_class = BulkEditObjectsSerializer
    parser_classes = (parsers.JSONParser,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = self.request.user
        object_type = serializer.validated_data.get("object_type")
        object_ids = serializer.validated_data.get("objects")
        apply_to_all = serializer.validated_data.get("all")
        object_class = serializer.get_object_class(object_type)
        operation = serializer.validated_data.get("operation")
        model_name = object_class._meta.model_name
        perm_codename = (
            f"change_{model_name}"
            if operation == "set_permissions"
            else f"delete_{model_name}"
        )

        if apply_to_all:
            # Support all to avoid sending large lists of ids for bulk operations, with optional filters
            filters = serializer.validated_data.get("filters") or {}
            filterset_class = {
                "tags": TagFilterSet,
                "correspondents": CorrespondentFilterSet,
                "document_types": DocumentTypeFilterSet,
                "storage_paths": StoragePathFilterSet,
            }[object_type]
            user_permitted_objects = get_objects_for_user_owner_aware(
                user,
                perm_codename,
                object_class,
            )
            objs = filterset_class(
                data=filters,
                queryset=user_permitted_objects,
            ).qs
            if object_type == "tags":
                editable_ids = set(user_permitted_objects.values_list("pk", flat=True))
                all_ids = set(objs.values_list("pk", flat=True))
                for tag in objs:
                    all_ids.update(
                        descendant.pk
                        for descendant in tag.get_descendants()
                        if descendant.pk in editable_ids
                    )
                objs = object_class.objects.filter(pk__in=all_ids)
            objs = objs.select_related("owner")
            object_ids = list(objs.values_list("pk", flat=True))
        else:
            objs = object_class.objects.select_related("owner").filter(
                pk__in=object_ids,
            )

        if not user.is_superuser:
            perm = f"documents.{perm_codename}"
            has_perms = user.has_perm(perm) and all(
                has_perms_owner_aware(user, perm_codename, obj) for obj in objs
            )

            if not has_perms:
                return HttpResponseForbidden("Insufficient permissions")

        if operation == "set_permissions":
            permissions = serializer.validated_data.get("permissions")
            owner = serializer.validated_data.get("owner")
            merge = serializer.validated_data.get("merge")

            try:
                qs = object_class.objects.filter(id__in=object_ids)

                # if merge is true, we dont want to remove the owner
                if "owner" in serializer.validated_data and (
                    not merge or (merge and owner is not None)
                ):
                    # if merge is true, we dont want to overwrite the owner
                    qs_owner_update = qs.filter(owner__isnull=True) if merge else qs
                    qs_owner_update.update(owner=owner)

                if "permissions" in serializer.validated_data:
                    for obj in qs:
                        set_permissions_for_object(
                            permissions=permissions,
                            object=obj,
                            merge=merge,
                        )

            except Exception as e:
                logger.warning(
                    f"An error occurred performing bulk permissions edit: {e!s}",
                )
                return HttpResponseBadRequest(
                    "Error performing bulk permissions edit, check logs for more detail.",
                )

        elif operation == "delete":
            objs.delete()

        return Response({"result": "OK"})


class WorkflowTriggerViewSet(ModelViewSet[WorkflowTrigger]):
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    serializer_class = WorkflowTriggerSerializer
    pagination_class = StandardPagination

    model = WorkflowTrigger

    queryset = WorkflowTrigger.objects.all()

    def partial_update(self, request, *args, **kwargs):
        if "id" in request.data and str(request.data["id"]) != str(kwargs["pk"]):
            return HttpResponseBadRequest(
                "ID in body does not match URL",
            )
        return super().partial_update(request, *args, **kwargs)


class WorkflowActionViewSet(ModelViewSet[WorkflowAction]):
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    serializer_class = WorkflowActionSerializer
    pagination_class = StandardPagination

    model = WorkflowAction

    queryset = WorkflowAction.objects.all().prefetch_related(
        "assign_tags",
        "assign_view_users",
        "assign_view_groups",
        "assign_change_users",
        "assign_change_groups",
        "assign_custom_fields",
    )

    def partial_update(self, request, *args, **kwargs):
        if "id" in request.data and str(request.data["id"]) != str(kwargs["pk"]):
            return HttpResponseBadRequest(
                "ID in body does not match URL",
            )
        return super().partial_update(request, *args, **kwargs)


class WorkflowViewSet(ModelViewSet[Workflow]):
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    serializer_class = WorkflowSerializer
    pagination_class = StandardPagination

    model = Workflow

    queryset = (
        Workflow.objects.all()
        .order_by("order")
        .prefetch_related(
            Prefetch(
                "triggers",
                queryset=WorkflowTrigger.objects.prefetch_related(
                    "filter_has_tags",
                    "filter_has_all_tags",
                    "filter_has_not_tags",
                    "filter_has_any_correspondents",
                    "filter_has_not_correspondents",
                    "filter_has_any_document_types",
                    "filter_has_not_document_types",
                    "filter_has_any_storage_paths",
                    "filter_has_not_storage_paths",
                ),
            ),
            Prefetch(
                "actions",
                queryset=WorkflowAction.objects.order_by(
                    "order",
                    "pk",
                ).prefetch_related(
                    "assign_tags",
                    "assign_view_users",
                    "assign_view_groups",
                    "assign_change_users",
                    "assign_change_groups",
                    "assign_custom_fields",
                    "remove_tags",
                    "remove_correspondents",
                    "remove_document_types",
                    "remove_storage_paths",
                    "remove_custom_fields",
                    "remove_owners",
                    "remove_view_users",
                    "remove_view_groups",
                    "remove_change_users",
                    "remove_change_groups",
                ),
            ),
        )
    )


class CustomFieldViewSet(PermissionsAwareDocumentCountMixin, ModelViewSet[CustomField]):
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    serializer_class = CustomFieldSerializer
    pagination_class = StandardPagination
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )
    filterset_class = CustomFieldFilterSet

    model = CustomField
    document_count_through = CustomFieldInstance
    document_count_source_field = "field_id"

    queryset = CustomField.objects.all().order_by("name")


@extend_schema_view(
    get=extend_schema(
        description="Get the current system status of the Paperless-NGX server",
        responses={
            (200, "application/json"): inline_serializer(
                name="SystemStatus",
                fields={
                    "pngx_version": serializers.CharField(),
                    "server_os": serializers.CharField(),
                    "install_type": serializers.CharField(),
                    "storage": inline_serializer(
                        name="Storage",
                        fields={
                            "total": serializers.IntegerField(),
                            "available": serializers.IntegerField(),
                        },
                    ),
                    "database": inline_serializer(
                        name="Database",
                        fields={
                            "type": serializers.CharField(),
                            "url": serializers.CharField(),
                            "status": serializers.CharField(),
                            "error": serializers.CharField(),
                            "migration_status": inline_serializer(
                                name="MigrationStatus",
                                fields={
                                    "latest_migration": serializers.CharField(),
                                    "unapplied_migrations": serializers.ListSerializer(
                                        child=serializers.CharField(),
                                    ),
                                },
                            ),
                        },
                    ),
                    "tasks": inline_serializer(
                        name="Tasks",
                        fields={
                            "redis_url": serializers.CharField(),
                            "redis_status": serializers.CharField(),
                            "redis_error": serializers.CharField(),
                            "celery_status": serializers.CharField(),
                            "summary": inline_serializer(
                                name="TasksSummaryOverview",
                                fields={
                                    "days": serializers.IntegerField(),
                                    "total_count": serializers.IntegerField(),
                                    "pending_count": serializers.IntegerField(),
                                    "success_count": serializers.IntegerField(),
                                    "failure_count": serializers.IntegerField(),
                                },
                            ),
                        },
                    ),
                    "index": inline_serializer(
                        name="Index",
                        fields={
                            "status": serializers.CharField(),
                            "error": serializers.CharField(),
                            "last_modified": serializers.DateTimeField(),
                        },
                    ),
                    "classifier": inline_serializer(
                        name="Classifier",
                        fields={
                            "status": serializers.CharField(),
                            "error": serializers.CharField(),
                            "last_trained": serializers.DateTimeField(),
                        },
                    ),
                    "sanity_check": inline_serializer(
                        name="SanityCheck",
                        fields={
                            "status": serializers.CharField(),
                            "error": serializers.CharField(),
                            "last_run": serializers.DateTimeField(),
                        },
                    ),
                },
            ),
        },
    ),
)
class SystemStatusView(PassUserMixin):
    permission_classes = (IsAuthenticated,)
    TASK_SUMMARY_DAYS = 30

    def get(self, request, format=None):
        if not has_system_status_permission(request.user):
            return HttpResponseForbidden("Insufficient permissions")

        current_version = version.__full_version_str__

        install_type = "bare-metal"
        if os.environ.get("KUBERNETES_SERVICE_HOST") is not None:
            install_type = "kubernetes"
        elif os.environ.get("PNGX_CONTAINERIZED") == "1":
            install_type = "docker"

        db_conn = connections["default"]
        db_url = str(db_conn.settings_dict["NAME"])
        db_error = None

        try:
            db_conn.ensure_connection()
            db_status = "OK"
            loader = MigrationLoader(connection=db_conn)
            all_migrations = [f"{app}.{name}" for app, name in loader.graph.nodes]
            applied_migrations = [
                f"{m.app}.{m.name}"
                for m in MigrationRecorder.Migration.objects.all().order_by("id")
            ]
        except Exception as e:  # pragma: no cover
            applied_migrations = []
            db_status = "ERROR"
            logger.exception(
                f"System status detected a possible problem while connecting to the database: {e}",
            )
            db_error = "Error connecting to database, check logs for more detail."

        media_stats = os.statvfs(settings.MEDIA_ROOT)

        redis_url = settings._CHANNELS_REDIS_URL
        redis_url_parsed = urlparse(redis_url)
        redis_constructed_url = f"{redis_url_parsed.scheme}://{redis_url_parsed.path or redis_url_parsed.hostname}"
        if redis_url_parsed.hostname is not None:
            redis_constructed_url += f":{redis_url_parsed.port}"
        redis_error = None
        with Redis.from_url(url=redis_url) as client:
            try:
                client.ping()
                redis_status = "OK"
            except Exception as e:
                redis_status = "ERROR"
                logger.exception(
                    f"System status detected a possible problem while connecting to redis: {e}",
                )
                redis_error = "Error connecting to redis, check logs for more detail."

        celery_error = None
        celery_url = None
        try:
            celery_ping = celery_app.control.inspect().ping()
            celery_url = next(iter(celery_ping.keys()))
            first_worker_ping = celery_ping[celery_url]
            if first_worker_ping["ok"] == "pong":
                celery_active = "OK"
        except Exception as e:
            celery_active = "ERROR"
            logger.exception(
                f"System status detected a possible problem while connecting to celery: {e}",
            )
            celery_error = "Error connecting to celery, check logs for more detail."

        index_error = None
        try:
            from documents.search import get_backend

            get_backend()  # triggers open/rebuild; raises on error
            index_status = "OK"
            # Use the most-recently modified file in the index directory as a proxy
            # for last index write time (Tantivy has no single last_modified() call).
            index_dir = settings.INDEX_DIR
            mtimes = [p.stat().st_mtime for p in index_dir.iterdir() if p.is_file()]
            index_last_modified = (
                make_aware(datetime.fromtimestamp(max(mtimes))) if mtimes else None
            )
        except Exception as e:
            index_status = "ERROR"
            index_error = "Error opening index, check logs for more detail."
            logger.exception(
                f"System status detected a possible problem while opening the index: {e}",
            )
            index_last_modified = None

        last_trained_task = (
            PaperlessTask.objects.filter(
                task_type=PaperlessTask.TaskType.TRAIN_CLASSIFIER,
                status__in=PaperlessTask.COMPLETE_STATUSES,  # ignore running tasks
            )
            .order_by("-date_done")
            .first()
        )
        classifier_status = "OK"
        classifier_error = None
        if last_trained_task is None:
            classifier_status = "WARNING"
            classifier_error = "No classifier training tasks found"
        elif last_trained_task.status != PaperlessTask.Status.SUCCESS:
            classifier_status = "ERROR"
            classifier_error = (
                last_trained_task.result_data.get("error_message")
                if last_trained_task.result_data
                else None
            )
        classifier_last_trained = (
            last_trained_task.date_done if last_trained_task else None
        )

        last_sanity_check = (
            PaperlessTask.objects.filter(
                task_type=PaperlessTask.TaskType.SANITY_CHECK,
                status__in=PaperlessTask.COMPLETE_STATUSES,  # ignore running tasks
            )
            .order_by("-date_done")
            .first()
        )
        sanity_check_status = "OK"
        sanity_check_error = None
        if last_sanity_check is None:
            sanity_check_status = "WARNING"
            sanity_check_error = "No sanity check tasks found"
        elif last_sanity_check.status != PaperlessTask.Status.SUCCESS:
            sanity_check_status = "ERROR"
            sanity_check_error = (
                last_sanity_check.result_data.get("error_message")
                if last_sanity_check.result_data
                else None
            )
        sanity_check_last_run = (
            last_sanity_check.date_done if last_sanity_check else None
        )

        ai_config = AIConfig()
        if not ai_config.llm_index_enabled:
            llmindex_status = "DISABLED"
            llmindex_error = None
            llmindex_last_modified = None
        else:
            last_llmindex_update = (
                PaperlessTask.objects.filter(
                    task_type=PaperlessTask.TaskType.LLM_INDEX,
                )
                .order_by("-date_done")
                .first()
            )
            llmindex_status = "OK"
            llmindex_error = None
            if last_llmindex_update is None:
                llmindex_status = "WARNING"
                llmindex_error = "No LLM index update tasks found"
            elif last_llmindex_update.status == PaperlessTask.Status.FAILURE:
                llmindex_status = "ERROR"
                llmindex_error = (
                    last_llmindex_update.result_data.get("error_message")
                    if last_llmindex_update.result_data
                    else None
                )
            llmindex_last_modified = (
                last_llmindex_update.date_done if last_llmindex_update else None
            )

        summary_cutoff = timezone.now() - timedelta(days=self.TASK_SUMMARY_DAYS)
        task_summary_agg = PaperlessTask.objects.filter(
            date_created__gte=summary_cutoff,
        ).aggregate(
            total_count=Count("id"),
            pending_count=Count(
                "id",
                filter=Q(status=PaperlessTask.Status.PENDING),
            ),
            success_count=Count(
                "id",
                filter=Q(status=PaperlessTask.Status.SUCCESS),
            ),
            failure_count=Count(
                "id",
                filter=Q(status=PaperlessTask.Status.FAILURE),
            ),
        )
        task_summary = {
            "days": self.TASK_SUMMARY_DAYS,
            **task_summary_agg,
        }

        return Response(
            {
                "pngx_version": current_version,
                "server_os": platform.platform(),
                "install_type": install_type,
                "storage": {
                    "total": media_stats.f_frsize * media_stats.f_blocks,
                    "available": media_stats.f_frsize * media_stats.f_bavail,
                },
                "database": {
                    "type": db_conn.vendor,
                    "url": db_url,
                    "status": db_status,
                    "error": db_error,
                    "migration_status": {
                        "latest_migration": applied_migrations[-1],
                        "unapplied_migrations": [
                            m for m in all_migrations if m not in applied_migrations
                        ],
                    },
                },
                "tasks": {
                    "redis_url": redis_constructed_url,
                    "redis_status": redis_status,
                    "redis_error": redis_error,
                    "celery_status": celery_active,
                    "celery_url": celery_url,
                    "celery_error": celery_error,
                    "index_status": index_status,
                    "index_last_modified": index_last_modified,
                    "index_error": index_error,
                    "classifier_status": classifier_status,
                    "classifier_last_trained": classifier_last_trained,
                    "classifier_error": classifier_error,
                    "sanity_check_status": sanity_check_status,
                    "sanity_check_last_run": sanity_check_last_run,
                    "sanity_check_error": sanity_check_error,
                    "llmindex_status": llmindex_status,
                    "llmindex_last_modified": llmindex_last_modified,
                    "llmindex_error": llmindex_error,
                    "summary": task_summary,
                },
            },
        )


class TrashView(ListModelMixin, PassUserMixin):
    permission_classes = (IsAuthenticated,)
    serializer_class = TrashSerializer
    filter_backends = (ObjectOwnedPermissionsFilter,)
    pagination_class = StandardPagination

    model = Document

    queryset = Document.deleted_objects.all()

    def get(self, request: Request, format: str | None = None) -> Response:
        self.serializer_class = DocumentSerializer
        return self.list(request, format)

    def post(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response | HttpResponse:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_ids = serializer.validated_data.get("documents")
        docs = (
            Document.global_objects.filter(id__in=doc_ids)
            if doc_ids is not None
            else self.filter_queryset(self.get_queryset()).all()
        )
        for doc in docs:
            if not has_perms_owner_aware(request.user, "delete_document", doc):
                return HttpResponseForbidden("Insufficient permissions")
        action = serializer.validated_data.get("action")
        if action == "restore":
            for doc in Document.deleted_objects.filter(id__in=doc_ids).all():
                doc.restore(strict=False)
        elif action == "empty":
            if doc_ids is None:
                doc_ids = [doc.id for doc in docs]
            empty_trash(doc_ids=doc_ids)
        return Response({"result": "OK", "doc_ids": doc_ids})


def serve_logo(request: HttpRequest, filename: str | None = None) -> FileResponse:
    """
    Serves the configured logo file with Content-Disposition: attachment.
    Prevents inline execution of SVGs. See GHSA-6p53-hqqw-8j62
    """
    config = ApplicationConfiguration.objects.first()
    app_logo = config.app_logo

    if not app_logo:
        raise Http404("No logo configured")

    path = app_logo.path
    content_type = magic.from_file(path, mime=True) or "application/octet-stream"

    return FileResponse(
        app_logo.open("rb"),
        content_type=content_type,
        filename=app_logo.name,
        as_attachment=True,
    )
