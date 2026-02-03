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
from pathlib import Path
from time import mktime
from typing import Literal
from unicodedata import normalize
from urllib.parse import quote
from urllib.parse import urlparse

import httpx
import magic
import pathvalidate
from celery import states
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import connections
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Case
from django.db.models import Count
from django.db.models import IntegerField
from django.db.models import Max
from django.db.models import Model
from django.db.models import Q
from django.db.models import Sum
from django.db.models import When
from django.db.models.functions import Lower
from django.db.models.manager import Manager
from django.http import FileResponse
from django.http import Http404
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
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.filters import SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.viewsets import ModelViewSet
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.viewsets import ViewSet

from documents import bulk_edit
from documents import index
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
from documents.parsers import get_parser_class_for_mime_type
from documents.permissions import AcknowledgeTasksPermissions
from documents.permissions import PaperlessAdminPermissions
from documents.permissions import PaperlessNotePermissions
from documents.permissions import PaperlessObjectPermissions
from documents.permissions import ViewDocumentsPermissions
from documents.permissions import get_document_count_filter_for_user
from documents.permissions import get_objects_for_user_owner_aware
from documents.permissions import has_perms_owner_aware
from documents.permissions import set_permissions_for_object
from documents.plugins.date_parsing import get_date_parser
from documents.schema import generate_object_with_permissions_schema
from documents.serialisers import AcknowledgeTasksViewSerializer
from documents.serialisers import BulkDownloadSerializer
from documents.serialisers import BulkEditObjectsSerializer
from documents.serialisers import BulkEditSerializer
from documents.serialisers import CorrespondentSerializer
from documents.serialisers import CustomFieldSerializer
from documents.serialisers import DocumentListSerializer
from documents.serialisers import DocumentSerializer
from documents.serialisers import DocumentTypeSerializer
from documents.serialisers import EmailSerializer
from documents.serialisers import NotesSerializer
from documents.serialisers import PostDocumentSerializer
from documents.serialisers import RunTaskViewSerializer
from documents.serialisers import SavedViewSerializer
from documents.serialisers import SearchResultSerializer
from documents.serialisers import ShareLinkBundleSerializer
from documents.serialisers import ShareLinkSerializer
from documents.serialisers import StoragePathSerializer
from documents.serialisers import StoragePathTestSerializer
from documents.serialisers import TagSerializer
from documents.serialisers import TagSerializerVersion1
from documents.serialisers import TasksViewSerializer
from documents.serialisers import TrashSerializer
from documents.serialisers import UiSettingsViewSerializer
from documents.serialisers import WorkflowActionSerializer
from documents.serialisers import WorkflowSerializer
from documents.serialisers import WorkflowTriggerSerializer
from documents.signals import document_updated
from documents.tasks import build_share_link_bundle
from documents.tasks import consume_file
from documents.tasks import empty_trash
from documents.tasks import index_optimize
from documents.tasks import llmindex_index
from documents.tasks import sanity_check
from documents.tasks import train_classifier
from documents.tasks import update_document_parent_tags
from documents.utils import get_boolean
from paperless import version
from paperless.celery import app as celery_app
from paperless.config import AIConfig
from paperless.config import GeneralConfig
from paperless.models import ApplicationConfiguration
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
        else:
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


class PassUserMixin(GenericAPIView):
    """
    Pass a user object to serializer
    """

    def get_serializer(self, *args, **kwargs):
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
    """
    Mixin to add document count to queryset, permissions-aware if needed
    """

    def get_document_count_filter(self):
        request = getattr(self, "request", None)
        user = getattr(request, "user", None) if request else None
        return get_document_count_filter_for_user(user)

    def get_queryset(self):
        filter = self.get_document_count_filter()
        return (
            super()
            .get_queryset()
            .annotate(document_count=Count("documents", filter=filter))
        )


@extend_schema_view(**generate_object_with_permissions_schema(CorrespondentSerializer))
class CorrespondentViewSet(ModelViewSet, PermissionsAwareDocumentCountMixin):
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
class TagViewSet(ModelViewSet, PermissionsAwareDocumentCountMixin):
    model = Tag

    queryset = Tag.objects.select_related("owner").order_by(
        Lower("name"),
    )

    def get_serializer_class(self, *args, **kwargs):
        if int(self.request.version) == 1:
            return TagSerializerVersion1
        else:
            return TagSerializer

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
            filter_q = self.get_document_count_filter()
            children_source = list(
                Tag.objects.filter(pk__in=descendant_pks | {t.pk for t in all_tags})
                .select_related("owner")
                .annotate(document_count=Count("documents", filter=filter_q))
                .order_by(*ordering),
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
        if descendant_pks:
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
class DocumentTypeViewSet(ModelViewSet, PermissionsAwareDocumentCountMixin):
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
                    "original_metadata": serializers.DictField(),
                    "archive_checksum": serializers.CharField(),
                    "archive_media_filename": serializers.CharField(),
                    "original_filename": serializers.CharField(),
                    "archive_size": serializers.IntegerField(),
                    "archive_metadata": serializers.DictField(),
                    "lang": serializers.CharField(),
                },
            ),
            400: None,
            403: None,
            404: None,
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
    GenericViewSet,
):
    model = Document
    queryset = Document.objects.annotate(num_notes=Count("notes"))
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
    search_fields = ("title", "correspondent__name", "content")
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

    def get_queryset(self):
        return (
            Document.objects.distinct()
            .order_by("-created")
            .annotate(num_notes=Count("notes"))
            .select_related("correspondent", "storage_path", "document_type", "owner")
            .prefetch_related("tags", "custom_fields", "notes")
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

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        from documents import index

        index.add_or_update_document(self.get_object())

        document_updated.send(
            sender=self.__class__,
            document=self.get_object(),
        )

        return response

    def destroy(self, request, *args, **kwargs):
        from documents import index

        index.remove_document_from_index(self.get_object())
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

    def file_response(self, pk, request, disposition):
        doc = Document.global_objects.select_related("owner").get(id=pk)
        if request.user is not None and not has_perms_owner_aware(
            request.user,
            "view_document",
            doc,
        ):
            return HttpResponseForbidden("Insufficient permissions")
        return serve_file(
            doc=doc,
            use_archive=not self.original_requested(request)
            and doc.has_archive_version,
            disposition=disposition,
        )

    def get_metadata(self, file, mime_type):
        if not Path(file).is_file():
            return None

        parser_class = get_parser_class_for_mime_type(mime_type)
        if parser_class:
            parser = parser_class(progress_callback=None, logging_group=None)

            try:
                return parser.extract_metadata(file, mime_type)
            except Exception:  # pragma: no cover
                logger.exception(f"Issue getting metadata for {file}")
                # TODO: cover GPG errors, remove later.
                return []
        else:  # pragma: no cover
            logger.warning(f"No parser for {mime_type}")
            return []

    def get_filesize(self, filename):
        if Path(filename).is_file():
            return Path(filename).stat().st_size
        else:
            return None

    @action(methods=["get"], detail=True, filter_backends=[])
    @method_decorator(cache_control(no_cache=True))
    @method_decorator(
        condition(etag_func=metadata_etag, last_modified_func=metadata_last_modified),
    )
    def metadata(self, request, pk=None):
        try:
            doc = Document.objects.select_related("owner").get(pk=pk)
            if request.user is not None and not has_perms_owner_aware(
                request.user,
                "view_document",
                doc,
            ):
                return HttpResponseForbidden("Insufficient permissions")
        except Document.DoesNotExist:
            raise Http404

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
        doc = get_object_or_404(Document.objects.select_related("owner"), pk=pk)
        if request.user is not None and not has_perms_owner_aware(
            request.user,
            "view_document",
            doc,
        ):
            return HttpResponseForbidden("Insufficient permissions")

        ai_config = AIConfig()

        if ai_config.ai_enabled:
            cached_llm_suggestions = get_llm_suggestion_cache(
                doc.pk,
                backend=ai_config.llm_backend,
            )

            if cached_llm_suggestions:
                refresh_suggestions_cache(doc.pk)
                return Response(cached_llm_suggestions.suggestions)

            llm_suggestions = get_ai_document_classification(doc, request.user)

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
        else:
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
                "dates": [
                    date.strftime("%Y-%m-%d") for date in dates if date is not None
                ],
            }

            # Cache the suggestions and the classifier hash for later
            set_suggestions_cache(doc.pk, resp_data, classifier)

        return Response(resp_data)

    @action(methods=["get"], detail=True, filter_backends=[])
    @method_decorator(cache_control(no_cache=True))
    @method_decorator(
        condition(etag_func=preview_etag, last_modified_func=preview_last_modified),
    )
    def preview(self, request, pk=None):
        try:
            response = self.file_response(pk, request, "inline")
            return response
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404

    @action(methods=["get"], detail=True, filter_backends=[])
    @method_decorator(cache_control(no_cache=True))
    @method_decorator(last_modified(thumbnail_last_modified))
    def thumb(self, request, pk=None):
        try:
            doc = Document.objects.select_related("owner").get(id=pk)
            if request.user is not None and not has_perms_owner_aware(
                request.user,
                "view_document",
                doc,
            ):
                return HttpResponseForbidden("Insufficient permissions")

            handle = doc.thumbnail_file

            return HttpResponse(handle, content_type="image/webp")
        except (FileNotFoundError, Document.DoesNotExist):
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

                from documents import index

                index.add_or_update_document(doc)

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

            note = Note.objects.get(id=int(request.GET.get("id")), document=doc)
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

            from documents import index

            index.add_or_update_document(doc)

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

    @action(
        methods=["post"],
        detail=True,
        url_path="email",
        permission_classes=[IsAuthenticated, ViewDocumentsPermissions],
    )
    # TODO: deprecated as of 2.19, remove in future release
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


class ChatStreamingSerializer(serializers.Serializer):
    q = serializers.CharField(required=True)
    document_id = serializers.IntegerField(required=False, allow_null=True)


@method_decorator(
    [
        ensure_csrf_cookie,
        cache_control(no_cache=True),
    ],
    name="dispatch",
)
class ChatStreamingView(GenericAPIView):
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
                name="query",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Advanced search query string",
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
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.searcher = None

    def get_serializer_class(self):
        if self._is_search_request():
            return SearchResultSerializer
        else:
            return DocumentSerializer

    def _is_search_request(self):
        return (
            "query" in self.request.query_params
            or "more_like_id" in self.request.query_params
        )

    def filter_queryset(self, queryset):
        filtered_queryset = super().filter_queryset(queryset)

        if self._is_search_request():
            from documents import index

            if "query" in self.request.query_params:
                query_class = index.DelayedFullTextQuery
            elif "more_like_id" in self.request.query_params:
                query_class = index.DelayedMoreLikeThisQuery
            else:
                raise ValueError

            return query_class(
                self.searcher,
                self.request.query_params,
                self.paginator.get_page_size(self.request),
                filter_queryset=filtered_queryset,
            )
        else:
            return filtered_queryset

    def list(self, request, *args, **kwargs):
        if self._is_search_request():
            from documents import index

            try:
                with index.open_index_searcher() as s:
                    self.searcher = s
                    queryset = self.filter_queryset(self.get_queryset())
                    page = self.paginate_queryset(queryset)

                    serializer = self.get_serializer(page, many=True)
                    response = self.get_paginated_response(serializer.data)

                    response.data["corrected_query"] = (
                        queryset.suggested_correction
                        if hasattr(queryset, "suggested_correction")
                        else None
                    )

                    return response
            except NotFound:
                raise
            except Exception as e:
                logger.warning(f"An error occurred listing search results: {e!s}")
                return HttpResponseBadRequest(
                    "Error listing search results, check logs for more detail.",
                )
        else:
            return super().list(request)

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


class SavedViewViewSet(ModelViewSet, PassUserMixin):
    model = SavedView

    queryset = SavedView.objects.all()
    serializer_class = SavedViewSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    def get_queryset(self):
        user = self.request.user
        return (
            SavedView.objects.filter(owner=user)
            .select_related("owner")
            .prefetch_related("filter_rules")
        )

    def perform_create(self, serializer) -> None:
        serializer.save(owner=self.request.user)


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
class BulkEditView(PassUserMixin):
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
        "rotate": "checksum",
        "delete_pages": "checksum",
        "split": None,
        "merge": None,
        "edit_pdf": "checksum",
        "reprocess": "checksum",
        "remove_password": "checksum",
    }

    permission_classes = (IsAuthenticated,)
    serializer_class = BulkEditSerializer
    parser_classes = (parsers.JSONParser,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = self.request.user
        method = serializer.validated_data.get("method")
        parameters = serializer.validated_data.get("parameters")
        documents = serializer.validated_data.get("documents")
        if method in [
            bulk_edit.split,
            bulk_edit.merge,
            bulk_edit.edit_pdf,
            bulk_edit.remove_password,
        ]:
            parameters["user"] = user

        if not user.is_superuser:
            document_objs = Document.objects.select_related("owner").filter(
                pk__in=documents,
            )
            user_is_owner_of_all_documents = all(
                (doc.owner == user or doc.owner is None) for doc in document_objs
            )

            # check global and object permissions for all documents
            has_perms = user.has_perm("documents.change_document") and all(
                has_perms_owner_aware(user, "change_document", doc)
                for doc in document_objs
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
                    and parameters["delete_originals"]
                )
                or (method == bulk_edit.edit_pdf and parameters["update_document"])
            ):
                has_perms = user_is_owner_of_all_documents

            # check global add permissions for methods that create documents
            if (
                has_perms
                and (
                    method in [bulk_edit.split, bulk_edit.merge]
                    or (
                        method in [bulk_edit.edit_pdf, bulk_edit.remove_password]
                        and not parameters["update_document"]
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
                        and parameters["delete_originals"]
                    )
                )
                and not user.has_perm("documents.delete_document")
            ):
                has_perms = False

            if not has_perms:
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
class PostDocumentView(GenericAPIView):
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

        async_task = consume_file.delay(
            input_doc,
            input_doc_overrides,
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
class SelectionDataView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = DocumentListSerializer
    parser_classes = (parsers.MultiPartParser, parsers.JSONParser)

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data.get("documents")

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
class SearchAutoCompleteView(GenericAPIView):
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

        from documents import index

        ix = index.open_index()

        return Response(
            index.autocomplete(
                ix,
                term,
                limit,
                user,
            ),
        )


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
        query = request.query_params.get("query", None)
        if query is None:
            return HttpResponseBadRequest("Query required")
        elif len(query) < 3:
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
            # First search by title
            docs = all_docs.filter(title__icontains=query)
            if not db_only and len(docs) < OBJECT_LIMIT:
                # If we don't have enough results, search by content
                from documents import index

                with index.open_index_searcher() as s:
                    fts_query = index.DelayedFullTextQuery(
                        s,
                        request.query_params,
                        OBJECT_LIMIT,
                        filter_queryset=all_docs,
                    )
                    results = fts_query[0:1]
                    docs = docs | Document.objects.filter(
                        id__in=[r["id"] for r in results],
                    )
            docs = docs[:OBJECT_LIMIT]
        saved_views = (
            SavedView.objects.filter(owner=request.user, name__icontains=query)
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
            MailRule.objects.filter(name__icontains=query)
            if request.user.has_perm("paperless_mail.view_mailrule")
            else []
        )
        mail_rules = mail_rules[:OBJECT_LIMIT]
        mail_accounts = (
            MailAccount.objects.filter(name__icontains=query)
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
class StatisticsView(GenericAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        user = request.user if request.user is not None else None

        documents = (
            Document.objects.all()
            if user is None
            else get_objects_for_user_owner_aware(
                user,
                "documents.view_document",
                Document,
            )
        )
        tags = (
            Tag.objects.all()
            if user is None
            else get_objects_for_user_owner_aware(user, "documents.view_tag", Tag)
        ).only("id", "is_inbox_tag")
        correspondent_count = (
            Correspondent.objects.count()
            if user is None
            else get_objects_for_user_owner_aware(
                user,
                "documents.view_correspondent",
                Correspondent,
            ).count()
        )
        document_type_count = (
            DocumentType.objects.count()
            if user is None
            else get_objects_for_user_owner_aware(
                user,
                "documents.view_documenttype",
                DocumentType,
            ).count()
        )
        storage_path_count = (
            StoragePath.objects.count()
            if user is None
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
                "inbox_tags": (inbox_tag_pks if inbox_tag_pks else None),
                "document_file_type_counts": document_file_type_counts,
                "character_count": character_count,
                "tag_count": len(tags),
                "correspondent_count": correspondent_count,
                "document_type_count": document_type_count,
                "storage_path_count": storage_path_count,
                "current_asn": current_asn,
            },
        )


class BulkDownloadView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = BulkDownloadSerializer
    parser_classes = (parsers.JSONParser,)

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data.get("documents")
        documents = Document.objects.filter(pk__in=ids)
        compression = serializer.validated_data.get("compression")
        content = serializer.validated_data.get("content")
        follow_filename_format = serializer.validated_data.get("follow_formatting")

        for document in documents:
            if not has_perms_owner_aware(request.user, "change_document", document):
                return HttpResponseForbidden("Insufficient permissions")

        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        temp = tempfile.NamedTemporaryFile(  # noqa: SIM115
            dir=settings.SCRATCH_DIR,
            suffix="-compressed-archive",
            delete=False,
        )

        if content == "both":
            strategy_class = OriginalAndArchiveStrategy
        elif content == "originals":
            strategy_class = OriginalsOnlyStrategy
        else:
            strategy_class = ArchiveOnlyStrategy

        with zipfile.ZipFile(temp.name, "w", compression) as zipf:
            strategy = strategy_class(zipf, follow_formatting=follow_filename_format)
            for document in documents:
                strategy.add_document(document)

        # TODO(stumpylog): Investigate using FileResponse here
        with Path(temp.name).open("rb") as f:
            response = HttpResponse(f, content_type="application/zip")
            response["Content-Disposition"] = '{}; filename="{}"'.format(
                "attachment",
                "documents.zip",
            )

            return response


@extend_schema_view(**generate_object_with_permissions_schema(StoragePathSerializer))
class StoragePathViewSet(ModelViewSet, PermissionsAwareDocumentCountMixin):
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
            bulk_edit.bulk_update_documents.delay(doc_ids)

        return response

    @action(methods=["post"], detail=False)
    def test(self, request):
        """
        Test storage path against a document
        """
        serializer = StoragePathTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        document = serializer.validated_data.get("document")
        path = serializer.validated_data.get("path")

        result = format_filename(document, path)
        return Response(result)


class UiSettingsView(GenericAPIView):
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
class RemoteVersionView(GenericAPIView):
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


@extend_schema_view(
    acknowledge=extend_schema(
        operation_id="acknowledge_tasks",
        description="Acknowledge a list of tasks",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": ["tasks"],
            },
        },
        responses={
            (200, "application/json"): inline_serializer(
                name="AcknowledgeTasks",
                fields={
                    "result": serializers.IntegerField(),
                },
            ),
            (400, "application/json"): None,
        },
    ),
)
@extend_schema(
    parameters=[
        OpenApiParameter(
            name="task_id",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter tasks by Celery UUID",
        ),
    ],
)
class TasksViewSet(ReadOnlyModelViewSet):
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    serializer_class = TasksViewSerializer
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = PaperlessTaskFilterSet

    TASK_AND_ARGS_BY_NAME = {
        PaperlessTask.TaskName.INDEX_OPTIMIZE: (index_optimize, {}),
        PaperlessTask.TaskName.TRAIN_CLASSIFIER: (
            train_classifier,
            {"scheduled": False},
        ),
        PaperlessTask.TaskName.CHECK_SANITY: (
            sanity_check,
            {"scheduled": False, "raise_on_error": False},
        ),
        PaperlessTask.TaskName.LLMINDEX_UPDATE: (
            llmindex_index,
            {"scheduled": False, "rebuild": False},
        ),
    }

    def get_queryset(self):
        queryset = PaperlessTask.objects.all().order_by("-date_created")
        task_id = self.request.query_params.get("task_id")
        if task_id is not None:
            queryset = PaperlessTask.objects.filter(task_id=task_id)
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

        try:
            tasks = PaperlessTask.objects.filter(id__in=task_ids)
            if request.user is not None and not request.user.is_superuser:
                tasks = tasks.filter(owner=request.user) | tasks.filter(owner=None)
            result = tasks.update(
                acknowledged=True,
            )
            return Response({"result": result})
        except Exception:
            return HttpResponseBadRequest()

    @action(methods=["post"], detail=False)
    def run(self, request):
        serializer = RunTaskViewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task_name = serializer.validated_data.get("task_name")

        if not request.user.is_superuser:
            return HttpResponseForbidden("Insufficient permissions")

        try:
            task_func, task_args = self.TASK_AND_ARGS_BY_NAME[task_name]
            result = task_func(**task_args)
            return Response({"result": result})
        except Exception as e:
            logger.warning(f"An error occurred running task: {e!s}")
            return HttpResponseServerError(
                "Error running task, check logs for more detail.",
            )


class ShareLinkViewSet(ModelViewSet, PassUserMixin):
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


class ShareLinkBundleViewSet(ModelViewSet, PassUserMixin):
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
        build_share_link_bundle.delay(bundle.pk)
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
        build_share_link_bundle.delay(bundle.pk)
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


def serve_file(*, doc: Document, use_archive: bool, disposition: str):
    if use_archive:
        file_handle = doc.archive_file
        filename = doc.get_public_filename(archive=True)
        mime_type = "application/pdf"
    else:
        file_handle = doc.source_file
        filename = doc.get_public_filename()
        mime_type = doc.mime_type
        # Support browser previewing csv files by using text mime type
        if mime_type in {"application/csv", "text/csv"} and disposition == "inline":
            mime_type = "text/plain"

    response = HttpResponse(file_handle, content_type=mime_type)
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
        object_class = serializer.get_object_class(object_type)
        operation = serializer.validated_data.get("operation")

        objs = object_class.objects.select_related("owner").filter(pk__in=object_ids)

        if not user.is_superuser:
            model_name = object_class._meta.model_name
            perm = (
                f"documents.change_{model_name}"
                if operation == "set_permissions"
                else f"documents.delete_{model_name}"
            )
            has_perms = user.has_perm(perm) and all(
                (obj.owner == user or obj.owner is None) for obj in objs
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


class WorkflowTriggerViewSet(ModelViewSet):
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


class WorkflowActionViewSet(ModelViewSet):
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


class WorkflowViewSet(ModelViewSet):
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    serializer_class = WorkflowSerializer
    pagination_class = StandardPagination

    model = Workflow

    queryset = (
        Workflow.objects.all()
        .order_by("order")
        .prefetch_related(
            "triggers",
            "actions",
        )
    )


class CustomFieldViewSet(ModelViewSet):
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    serializer_class = CustomFieldSerializer
    pagination_class = StandardPagination
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )
    filterset_class = CustomFieldFilterSet

    model = CustomField

    queryset = CustomField.objects.all().order_by("-created")

    def get_queryset(self):
        filter = (
            Q(fields__document__deleted_at__isnull=True)
            if self.request.user is None or self.request.user.is_superuser
            else (
                Q(
                    fields__document__deleted_at__isnull=True,
                    fields__document__id__in=get_objects_for_user_owner_aware(
                        self.request.user,
                        "documents.view_document",
                        Document,
                    ).values_list("id", flat=True),
                )
            )
        )
        return (
            super()
            .get_queryset()
            .annotate(
                document_count=Count(
                    "fields",
                    filter=filter,
                ),
            )
        )


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

    def get(self, request, format=None):
        if not request.user.is_staff:
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
            ix = index.open_index()
            index_status = "OK"
            index_last_modified = make_aware(
                datetime.fromtimestamp(ix.last_modified()),
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
                task_name=PaperlessTask.TaskName.TRAIN_CLASSIFIER,
                status__in=[
                    states.SUCCESS,
                    states.FAILURE,
                    states.REVOKED,
                ],  # ignore running tasks
            )
            .order_by("-date_done")
            .first()
        )
        classifier_status = "OK"
        classifier_error = None
        if last_trained_task is None:
            classifier_status = "WARNING"
            classifier_error = "No classifier training tasks found"
        elif last_trained_task and last_trained_task.status != states.SUCCESS:
            classifier_status = "ERROR"
            classifier_error = last_trained_task.result
        classifier_last_trained = (
            last_trained_task.date_done if last_trained_task else None
        )

        last_sanity_check = (
            PaperlessTask.objects.filter(
                task_name=PaperlessTask.TaskName.CHECK_SANITY,
                status__in=[
                    states.SUCCESS,
                    states.FAILURE,
                    states.REVOKED,
                ],  # ignore running tasks
            )
            .order_by("-date_done")
            .first()
        )
        sanity_check_status = "OK"
        sanity_check_error = None
        if last_sanity_check is None:
            sanity_check_status = "WARNING"
            sanity_check_error = "No sanity check tasks found"
        elif last_sanity_check and last_sanity_check.status != states.SUCCESS:
            sanity_check_status = "ERROR"
            sanity_check_error = last_sanity_check.result
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
                    task_name=PaperlessTask.TaskName.LLMINDEX_UPDATE,
                )
                .order_by("-date_done")
                .first()
            )
            llmindex_status = "OK"
            llmindex_error = None
            if last_llmindex_update is None:
                llmindex_status = "WARNING"
                llmindex_error = "No LLM index update tasks found"
            elif last_llmindex_update and last_llmindex_update.status == states.FAILURE:
                llmindex_status = "ERROR"
                llmindex_error = last_llmindex_update.result
            llmindex_last_modified = (
                last_llmindex_update.date_done if last_llmindex_update else None
            )

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

    def get(self, request, format=None):
        self.serializer_class = DocumentSerializer
        return self.list(request, format)

    def post(self, request, *args, **kwargs):
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


def serve_logo(request, filename=None):
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
