import hashlib
import itertools
import json
import logging
import os
import platform
import re
import tempfile
import traceback
import urllib
import zipfile
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from time import mktime
from unicodedata import normalize
from urllib.parse import quote
from urllib.parse import urlparse

import pandas as pd
import pathvalidate
import pytz
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import connections
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Case
from django.db.models import Count
from django.db.models import IntegerField
from django.db.models import Max
from django.db.models import Q
from django.db.models import Sum
from django.db.models import When
from django.db.models.functions import Length
from django.db.models.functions import Lower
from django.db.models.functions import TruncDate
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.timezone import make_aware
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.cache import cache_control
from django.views.decorators.http import condition
from django.views.decorators.http import last_modified
from django.views.generic import TemplateView
from django_elasticsearch_dsl_drf.pagination import LimitOffsetPagination
from django_filters.rest_framework import DjangoFilterBackend
from guardian.shortcuts import get_objects_for_user
from guardian.shortcuts import get_users_with_perms
from langdetect import detect
from packaging import version as packaging_version
from redis import Redis
from rest_framework import parsers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter
from rest_framework.filters import SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework.viewsets import ModelViewSet
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.viewsets import ViewSet

from documents import bulk_edit
from documents import index
from documents.bulk_download import ArchiveOnlyStrategy
from documents.bulk_download import OriginalAndArchiveStrategy
from documents.bulk_download import OriginalsOnlyStrategy
from documents.caching import CACHE_50_MINUTES
from documents.caching import get_metadata_cache
from documents.caching import get_suggestion_cache
from documents.caching import refresh_metadata_cache
from documents.caching import refresh_suggestions_cache
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
from documents.documents import DocumentDocument
from documents.filters import ArchiveFontFilterSet
from documents.filters import BackupRecordFilterSet
from documents.filters import CorrespondentFilterSet
from documents.filters import CustomFieldFilterSet
from documents.filters import DocumentFilterSet
from documents.filters import DocumentTypeFilterSet
from documents.filters import DossierFilterSet
from documents.filters import DossierFormFilterSet
from documents.filters import FolderFilterSet
from documents.filters import FontLanguageFilterSet
from documents.filters import ObjectOwnedOrGrantedPermissionsFilter
from documents.filters import ObjectOwnedPermissionsFilter
from documents.filters import ShareLinkFilterSet
from documents.filters import StoragePathFilterSet
from documents.filters import TagFilterSet
from documents.filters import WarehouseFilterSet
from documents.index import autocomplete_elastic_search
from documents.matching import match_correspondents
from documents.matching import match_document_types
from documents.matching import match_folders
from documents.matching import match_storage_paths
from documents.matching import match_tags
from documents.matching import match_warehouses
from documents.models import Approval
from documents.models import ArchiveFont
from documents.models import BackupRecord
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Dossier
from documents.models import DossierForm
from documents.models import Folder
from documents.models import FontLanguage
from documents.models import Note
from documents.models import PaperlessTask
from documents.models import SavedView
from documents.models import ShareLink
from documents.models import StoragePath
from documents.models import Tag
from documents.models import UiSettings
from documents.models import Warehouse
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.parsers import custom_get_parser_class_for_mime_type
from documents.parsers import parse_date_generator
from documents.permissions import PaperlessAdminPermissions
from documents.permissions import PaperlessObjectPermissions
from documents.permissions import check_user_can_change_folder
from documents.permissions import get_groups_with_only_permission
from documents.permissions import get_objects_for_user_owner_aware
from documents.permissions import has_perms_owner_aware
from documents.permissions import set_permissions_for_object
from documents.permissions import update_view_folder_parent_permissions
from documents.permissions import \
    update_view_warehouse_shelf_boxcase_permissions
from documents.serialisers import AcknowledgeTasksViewSerializer, \
    DocumentDocumentSerializer
from documents.serialisers import ApprovalSerializer
from documents.serialisers import ApprovalViewSerializer
from documents.serialisers import ArchiveFontSerializer
from documents.serialisers import BackupRecordSerializer
from documents.serialisers import BulkDownloadSerializer
from documents.serialisers import BulkEditObjectsSerializer
from documents.serialisers import BulkEditSerializer
from documents.serialisers import CorrespondentSerializer
from documents.serialisers import CustomFieldSerializer
from documents.serialisers import DocumentListSerializer
from documents.serialisers import DocumentSerializer
from documents.serialisers import DocumentTypeSerializer
from documents.serialisers import DossierFormSerializer
from documents.serialisers import DossierSerializer
from documents.serialisers import ExportDocumentFromFolderSerializer
from documents.serialisers import FolderSerializer
from documents.serialisers import FontLanguageSerializer
from documents.serialisers import PostDocumentSerializer
from documents.serialisers import SavedViewSerializer
from documents.serialisers import ShareLinkSerializer
from documents.serialisers import StoragePathSerializer
from documents.serialisers import TagSerializer
from documents.serialisers import TagSerializerVersion1
from documents.serialisers import TasksViewSerializer
from documents.serialisers import TrashSerializer
from documents.serialisers import UiSettingsViewSerializer
from documents.serialisers import WarehouseSerializer
from documents.serialisers import WorkflowActionSerializer
from documents.serialisers import WorkflowSerializer
from documents.serialisers import WorkflowTriggerSerializer
from documents.signals import approval_updated
from documents.signals import document_updated
from documents.tasks import backup_documents
from documents.tasks import consume_file
from documents.tasks import deleted_backup
from documents.tasks import empty_trash
from documents.tasks import restore_documents
from documents.utils import check_storage
from documents.utils import generate_unique_name
from documents.utils import get_directory_size
from paperless import version
from paperless.celery import app as celery_app
from paperless.config import GeneralConfig
from paperless.db import GnuPG
from paperless.views import StandardPagination

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
        kwargs.setdefault(
            "full_perms",
            self.request.query_params.get("full_perms", False),
        )
        return super().get_serializer(*args, **kwargs)


class PermissionsAwareDocumentCountMixin(PassUserMixin):
    """
    Mixin to add document count to queryset, permissions-aware if needed
    """

    def get_queryset(self):
        filter = (
            None
            if self.request.user is None or self.request.user.is_superuser
            else (
                Q(
                    documents__id__in=get_objects_for_user_owner_aware(
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
            .annotate(document_count=Count("documents", filter=filter))
        )


class CorrespondentViewSet(ModelViewSet, PermissionsAwareDocumentCountMixin):
    model = Correspondent

    queryset = (
        Correspondent.objects.annotate(
            last_correspondence=Max("documents__created"),
        )
        .select_related("owner")
        .order_by(Lower("name"))
    )

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


class ArchiveFontViewSet(ModelViewSet, PermissionsAwareDocumentCountMixin):
    model = ArchiveFont

    queryset = ArchiveFont.objects.select_related("owner").order_by(Lower("name"))

    serializer_class = ArchiveFontSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = ArchiveFontFilterSet
    ordering_fields = ("name", "matching_algorithm", "match", "document_count")


class FontLanguageViewSet(ModelViewSet, PermissionsAwareDocumentCountMixin):
    model = FontLanguage

    queryset = FontLanguage.objects.select_related("owner").order_by(Lower("name"))

    serializer_class = FontLanguageSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = FontLanguageFilterSet
    ordering_fields = ("name", "matching_algorithm", "match", "document_count")

from django_elasticsearch_dsl_drf.viewsets import (
    BaseDocumentViewSet,
)

from django_elasticsearch_dsl_drf.filter_backends import (
    FilteringFilterBackend,
    HighlightBackend,
    OrderingFilterBackend,
    SearchFilterBackend,
)



from django_elasticsearch_dsl_drf.constants import (
    LOOKUP_QUERY_IN,
)


class DocumentElasticSearch(BaseDocumentViewSet):
    document = DocumentDocument
    serializer_class = DocumentDocumentSerializer
    pagination_class = LimitOffsetPagination

    filter_backends = [
        FilteringFilterBackend,
        OrderingFilterBackend,
        SearchFilterBackend,
        HighlightBackend,
    ]

    lookup_field = 'id'

    # Xác định các trường tìm kiếm
    search_fields = ('title', 'content')

    # Lọc theo các trường
    filter_fields = {
        # 'id': {
        #     'field': 'id',
        #     'lookups': [
        #         LOOKUP_FILTER_RANGE,
        #         LOOKUP_QUERY_IN,
        #         LOOKUP_QUERY_GT,
        #         LOOKUP_QUERY_GTE,
        #         LOOKUP_QUERY_LT,
        #         LOOKUP_QUERY_LTE,
        #         LOOKUP_FILTER_TERMS,
        #     ],
        # },
        'title': 'title.raw',  # Bạn có thể vẫn giữ title nếu cần
        'content': 'content.raw',  # Đảm bảo trường này được hỗ trợ
        'folder': {
            'field': 'folder',  # Trường trong Elasticsearch
            'lookups': [
                LOOKUP_QUERY_IN,  # Tìm kiếm trong danh sách ID
                # Bạn có thể thêm các lookups khác nếu cần
            ],
        },
    }

    # Các trường highlight
    highlight_fields = {
        'title': {
                'options': {
                    'pre_tags': ["<b>"],
                    'post_tags': ["</b>"]
                },
            'enabled': True,
        },'content': {
                'options': {
                    'pre_tags': ["<b>"],
                    'post_tags': ["</b>"]
                },
            'enabled': True,
        },
    }

    ordering = ('id',)  # Sửa lại để sử dụng tuple
    ordering_fields = {
        'id': 'id',
    }



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
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = DocumentFilterSet
    search_fields = ("title", "correspondent__name", "content", "warehouse", "folder")
    ordering_fields = (
        "id",
        "title",
        "correspondent__name",
        "document_type__name",
        "archive_font__namecreated",
        "modified",
        "added",
        "archive_serial_number",
        "num_notes",
        "owner",
        "page_count",
    )

    def get_queryset(self):
        return (
            Document.objects.distinct()
            .annotate(num_notes=Count("notes"))
            .select_related(
                "correspondent",
                "storage_path",
                "document_type",
                "warehouse",
                "folder",
                "owner",
            )
            .prefetch_related("tags", "custom_fields", "notes")
        )

    def get_serializer(self, *args, **kwargs):
        fields_param = self.request.query_params.get("fields", None)
        fields = fields_param.split(",") if fields_param else None
        truncate_content = self.request.query_params.get("truncate_content", "False")
        kwargs.setdefault("context", self.get_serializer_context())
        kwargs.setdefault("fields", fields)
        kwargs.setdefault("truncate_content", truncate_content.lower() in ["true", "1"])
        kwargs.setdefault(
            "full_perms",
            self.request.query_params.get("full_perms", False),
        )
        return super().get_serializer(*args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        data = request.data.copy()  # Tạo một bản sao của dữ liệu
        # Loại bỏ trường archive_serial_number khỏi quá trình xác thực
        if "archive_serial_number" in data:
            data.pop("archive_serial_number")

        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        response = super().update(request, *args, **kwargs)
        # logger.debug(response)
        self.update_time_archive_font(self.get_object())
        self.update_name_folder(self.get_object(), serializer)
        self.update_folder_permisisons(self.get_object(), serializer)
        self.update_dossier_permisisons(self.get_object(), serializer)
        from documents import index

        index.add_or_update_document(self.get_object())

        document_updated.send(
            sender=self.__class__,
            document=self.get_object(),
        )

        return response

    def destroy(self, request, *args, **kwargs):
        from documents import index

        instance = self.get_object()
        folder = instance.folder
        dossier = instance.dossier
        # instance.folder = None
        # instance.dossier = None
        # instance.save()
        if folder is not None:
            folder.delete()
        if dossier is not None:
            dossier.delete()
        index.remove_document_from_index(self.get_object())

        return super().destroy(request, *args, **kwargs)

    @staticmethod
    def original_requested(request):
        return (
            "original" in request.query_params
            and request.query_params["original"] == "true"
        )

    def file_response(self, pk, request, disposition):
        doc = Document.objects.get(id=pk)
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
        if not os.path.isfile(file):
            return None

        parser_class = custom_get_parser_class_for_mime_type(mime_type)
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
        if os.path.isfile(filename):
            return os.stat(filename).st_size
        else:
            return None

    @action(methods=["get"], detail=True)
    @method_decorator(
        condition(etag_func=metadata_etag, last_modified_func=metadata_last_modified),
    )
    def metadata(self, request, pk=None):
        try:
            doc = Document.objects.get(pk=pk)
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
        archive_filesize = None
        if document_cached_metadata is not None:
            original_metadata = document_cached_metadata.original_metadata
            archive_metadata = document_cached_metadata.archive_metadata
            refresh_metadata_cache(doc.pk)
        else:
            original_metadata = self.get_metadata(doc.source_path, doc.mime_type)

            if doc.has_archive_version:
                archive_filesize = self.get_filesize(doc.archive_path)
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

    @action(methods=["get"], detail=True)
    @method_decorator(
        condition(
            etag_func=suggestions_etag,
            last_modified_func=suggestions_last_modified,
        ),
    )
    def suggestions(self, request, pk=None):
        doc = get_object_or_404(Document, pk=pk)
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
            gen = parse_date_generator(doc.filename, doc.content)
            dates = sorted(
                {i for i in itertools.islice(gen, settings.NUMBER_OF_SUGGESTED_DATES)},
            )

        resp_data = {
            "correspondents": [
                c.id for c in match_correspondents(doc, classifier, request.user)
            ],
            "warehouses": [
                wh.id for wh in match_warehouses(doc, classifier, request.user)
            ],
            "folders": [f.id for f in match_folders(doc, classifier, request.user)],
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

    @action(methods=["get"], detail=True)
    @method_decorator(cache_control(public=False, max_age=5 * 60))
    @method_decorator(
        condition(etag_func=preview_etag, last_modified_func=preview_last_modified),
    )
    def preview(self, request, pk=None):
        try:
            response = self.file_response(pk, request, "inline")
            return response
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404

    @action(methods=["get"], detail=True)
    @method_decorator(cache_control(public=False, max_age=CACHE_50_MINUTES))
    @method_decorator(last_modified(thumbnail_last_modified))
    def thumb(self, request, pk=None):
        try:
            doc = Document.objects.get(id=pk)
            # Allow all users to view thumbnails
            if request.user is None:
                return HttpResponseForbidden("Insufficient permissions")

            # Original
            # if request.user is not None and not has_perms_owner_aware(
            #     request.user,
            #     "view_document",
            #     doc,
            # ):
            #     return HttpResponseForbidden("Insufficient permissions")

            if doc.storage_type == Document.STORAGE_TYPE_GPG:
                handle = GnuPG.decrypted(doc.thumbnail_file)
            else:
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

    @action(methods=["get"], detail=True)
    def export_excel(self, request, pk=None):
        try:

            document = Document.objects.get(pk=pk)
            fields = CustomFieldInstance.objects.filter(document=pk)

            data = {
                "Tên file": document.title,
                "Nội dung": [document.content],
                "Ngày tạo": [document.created.strftime("%d-%m-%Y")],
            }

            for f in fields:
                data[f.field.name] = [f.value_text]

            df = pd.DataFrame(data)

            # Tên file Excel sẽ được tạo
            excel_file_name = f"{document.title}.xlsx"

            # Tạo response để trả về file Excel
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{excel_file_name}"'
            )

            # Ghi DataFrame vào response dưới dạng Excel
            df.to_excel(response, index=False)

            return response
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404

    def getNotes(self, doc):
        return [
            {
                "id": c.id,
                "note": c.note,
                "created": c.created,
                "user": {
                    "id": c.user.id,
                    "username": c.user.username,
                    "first_name": c.user.first_name,
                    "last_name": c.user.last_name,
                },
            }
            for c in Note.objects.filter(document=doc).order_by("-created")
        ]

    @action(methods=["get", "post", "delete"], detail=True)
    def notes(self, request, pk=None):
        currentUser = request.user
        try:
            doc = Document.objects.get(pk=pk)
            if currentUser is not None and not has_perms_owner_aware(
                currentUser,
                "view_document",
                doc,
            ):
                return HttpResponseForbidden("Insufficient permissions to view notes")
        except Document.DoesNotExist:
            raise Http404

        if request.method == "GET":
            try:
                return Response(self.getNotes(doc))
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
                c.save()
                # If audit log is enabled make an entry in the log
                # about this note change
                if settings.AUDIT_LOG_ENABLED:
                    LogEntry.objects.log_create(
                        instance=doc,
                        changes=json.dumps(
                            {
                                "Note Added": ["None", c.id],
                            },
                        ),
                        action=LogEntry.Action.UPDATE,
                    )

                doc.modified = timezone.now()
                doc.save()

                from documents import index

                index.add_or_update_document(self.get_object())

                return Response(self.getNotes(doc))
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

            note = Note.objects.get(id=int(request.GET.get("id")))
            if settings.AUDIT_LOG_ENABLED:
                LogEntry.objects.log_create(
                    instance=doc,
                    changes=json.dumps(
                        {
                            "Note Deleted": [note.id, "None"],
                        },
                    ),
                    action=LogEntry.Action.UPDATE,
                )

            note.delete()

            doc.modified = timezone.now()
            doc.save()

            from documents import index

            index.add_or_update_document(doc)

            return Response(self.getNotes(doc))

        return Response(
            {
                "error": "error",
            },
        )

    def get_approvals(self, doc: Document):
        approvals = Approval.objects.get(id=doc.pk)

        return approvals

    @action(methods=["get", "post"], detail=True)
    def approvals(self, request, pk=None):
        currentUser = request.user
        try:
            doc = Document.objects.get(pk=pk)
            if currentUser is not None and not has_perms_owner_aware(
                currentUser,
                "view_document",
                doc,
            ):
                return HttpResponseForbidden(
                    "Insufficient permissions to view approvals",
                )
        except Document.DoesNotExist:
            raise Http404

        if request.method == "GET":
            try:
                return Response(self.get_approvals(doc))
            except Exception as e:
                logger.warning(f"An error occurred retrieving approvals: {e!s}")
                return Response(
                    {
                        "error": "Error retrieving approvals, check logs for more detail.",
                    },
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
                serializer = ApprovalSerializer(data=request.data)
                existing_approval = False
                if serializer.is_valid(raise_exception=True):

                    existing_approval = Approval.objects.filter(
                        object_pk=serializer.validated_data.get("object_pk"),
                        access_type=serializer.validated_data.get("access_type"),
                        ctype=serializer.validated_data.get("ctype"),
                        submitted_by=serializer.validated_data.get("submitted_by"),
                    )

                    submitted_by_groups = serializer.validated_data.get(
                        "submitted_by_group",
                        None,
                    )
                    if submitted_by_groups:
                        existing_approval = existing_approval.filter(
                            Q(submitted_by_group__in=submitted_by_groups),
                        ).exists()

                if existing_approval:
                    return Response(
                        {"status": 400, "message": "Objects exist"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                content_type_id = ContentType.objects.get(
                    app_label="documents",
                    model="document",
                ).pk

                a = Approval.objects.create(
                    submitted_by=currentUser,
                    object_pk=str(doc.pk),
                    ctype_id=content_type_id,
                    access_type="VIEW",
                    expiration=serializer.validated_data.get("expiration"),
                    submitted_by_group=serializer.validated_data.get(
                        "submitted_by_group",
                        None,
                    ),
                )
                a.save()
                # If audit log is enabled make an entry in the log
                # about this note change
                if settings.AUDIT_LOG_ENABLED:
                    LogEntry.objects.log_create(
                        instance=doc,
                        changes=json.dumps(
                            {
                                "Approval Added": ["None", a.id],
                            },
                        ),
                        action=LogEntry.Action.UPDATE,
                    )

                # doc.modified = timezone.now()
                doc.save()

                from documents import index

                index.add_or_update_document(self.get_object())

                return Response(self.getNotes(doc))
            except Exception as e:
                logger.warning(f"An error occurred saving approval: {e!s}")
                return Response(
                    {
                        "error": "Error saving approval, check logs for more detail.",
                    },
                )

        return Response(
            {
                "error": "error",
            },
        )

    @action(methods=["get"], detail=True)
    def share_links(self, request, pk=None):
        currentUser = request.user
        try:
            doc = Document.objects.get(pk=pk)
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
            links = [
                {
                    "id": c.id,
                    "created": c.created,
                    "expiration": c.expiration,
                    "slug": c.slug,
                }
                for c in ShareLink.objects.filter(document=doc)
                .exclude(expiration__lt=now)
                .order_by("-created")
            ]
            return Response(links)

    def update_name_folder(self, instance, serializer):
        instance.folder.name = serializer.validated_data.get("title")
        instance.folder.save()

    def update_time_archive_font(self, instance):
        if instance.archive_font is None:
            return
        if instance.archive_font.last_upload is None:
            instance.archive_font.last_upload = instance.created
            instance.archive_font.first_upload = instance.created
        elif instance.created > instance.archive_font.last_upload:
            instance.archive_font.last_upload = instance.created
        elif instance.created < instance.archive_font.first_upload:
            instance.archive_font.first_upload = instance.created
        instance.archive_font.save()

    def update_folder_permisisons(self, instance, serializer):
        folder = instance.folder
        permissions = serializer.validated_data.get("set_permissions")
        owner = serializer.validated_data.get("owner")
        merge = serializer.validated_data.get("merge")
        try:
            if folder:
                # if merge is true, we dont want to remove the owner
                if "owner" in serializer.validated_data and (
                    not merge or (merge and owner is not None)
                ):
                    # if merge is true, we dont want to overwrite the owner
                    qs_owner_update = (
                        folder.filter(owner__isnull=True) if merge else folder
                    )
                    qs_owner_update.owner = owner
                    qs_owner_update.save()
                if "set_permissions" in serializer.validated_data:

                    set_permissions_for_object(
                        permissions=permissions,
                        object=folder,
                        merge=merge,
                    )

        except Exception as e:
            logger.warning(
                f"An error occurred performing bulk permissions edit: {e!s}",
            )
            return HttpResponseBadRequest(
                "Error performing bulk permissions edit, check logs for more detail.",
            )

    def update_dossier_permisisons(self, instance, serializer):
        dossier = instance.dossier
        permissions = serializer.validated_data.get("set_permissions")
        owner = serializer.validated_data.get("owner")
        merge = serializer.validated_data.get("merge")
        try:
            if dossier:
                # if merge is true, we dont want to remove the owner
                if "owner" in serializer.validated_data and (
                    not merge or (merge and owner is not None)
                ):
                    # if merge is true, we dont want to overwrite the owner
                    qs_owner_update = (
                        dossier.filter(owner__isnull=True) if merge else dossier
                    )
                    qs_owner_update.owner = owner
                    qs_owner_update.save()
                if "set_permissions" in serializer.validated_data:

                    set_permissions_for_object(
                        permissions=permissions,
                        object=dossier,
                        merge=merge,
                    )

        except Exception as e:
            logger.warning(
                f"An error occurred performing bulk permissions edit: {e!s}",
            )
            return HttpResponseBadRequest(
                "Error performing bulk permissions edit, check logs for more detail.",
            )


class SearchResultSerializer(DocumentSerializer, PassUserMixin):
    def to_representation(self, instance):
        # print(instance)

        doc = (
            Document.objects.select_related(
                "correspondent",
                "storage_path",
                "document_type",
                "warehouse",
                "folder",
                "owner",
            )
            .prefetch_related("tags", "custom_fields", "notes")
            .get(id=instance["id"])
        )
        notes = ",".join(
            [str(c.note) for c in doc.notes.all()],
        )
        r = super().to_representation(doc)
        r["__search_hit__"] = {
            # "score": instance.score,
            "highlights": instance.highlights("content", text=doc.content),
            "note_highlights": (
                instance.highlights("notes", text=notes) if doc else None
            ),
            "rank": instance.rank,
        }
        return r

class SearchResultElasticSearchSerializer(DocumentSerializer, PassUserMixin):

    def to_representation(self, instance):
        # print('instance',instance.doc_obj.__dict__)
        if getattr(instance, 'doc_obj', None)==None:
            return None
        instance.doc_obj.content = ""
        doc = (
            instance.doc_obj
        )

        notes = ",".join(
            [str(c.note) for c in doc.notes.all()],
        )
        r = super().to_representation(doc)
        highlight_content = None
        highlight_note = None
        if hasattr(instance.meta,'highlight'):
            highlight_content = instance.meta.highlight.content[0]
            # highlight_note = instance.meta.highlight.note[0]
        r["__search_hit__"] = {
            "score": None,
            "highlights": highlight_content,
            "note_highlights": (
                notes if doc else None
            ),
            "rank": None,
        }
        return r

class UnifiedSearchViewSet(DocumentViewSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.searcher = None

    def get_serializer_class(self):
        if self._is_search_request():
            # return SearchResultSerializer
            return SearchResultElasticSearchSerializer
        else:
            return DocumentSerializer

    def _is_search_request(self):
        return (
            "query" in self.request.query_params
            or "more_like_id" in self.request.query_params
        )


    def filter_queryset(self, queryset):
        if self._is_search_request():
            # docs=convert_elastic_search(self.request.query_params.get('query'),1 , self.paginator.get_page_size(self.request))
            # return docs
            from documents import index
            if "query" in self.request.query_params:
                # query_class = index.DelayedFullTextQuery
                query_class = index.DelayedElasticSearch
            elif "more_like_id" in self.request.query_params:
                # query_class = index.DelayedMoreLikeThisQuery
                query_class = index.DelayedElasticSearchLikeMore

            else:
                raise ValueError
            return query_class(
                self.searcher,
                self.request.query_params,
                self.paginator.get_page_size(self.request),
                self.request.user,
            )
        else:
            return super().filter_queryset(queryset)

    def list(self, request, *args, **kwargs):
        if self._is_search_request():
            # from documents import index

            try:
                with index.open_index_searcher() as s:
                    self.searcher = s
                    return super().list(request)
                # return super().list(request)
            except NotFound:
                raise
            except Exception as e:
                traceback.print_exc()
                logger.warning(f"An error occurred listing search results: {e!s}")
                return HttpResponseBadRequest(
                    "Error listing search results, check logs for more detail.",
                )
        else:
            # print('da vào list', request.__dict__)
            return super().list(request)

    @action(detail=False, methods=["GET"], name="Get Next ASN")
    def next_asn(self, request, *args, **kwargs):
        max_asn = Document.objects.aggregate(
            Max("archive_serial_number", default=0),
        ).get(
            "archive_serial_number__max",
        )
        return Response(max_asn + 1)


class LogViewSet(ViewSet):
    permission_classes = (IsAuthenticated, PaperlessAdminPermissions)

    log_files = ["paperless", "mail"]

    def get_log_filename(self, log):
        return os.path.join(settings.LOGGING_DIR, f"{log}.log")

    def retrieve(self, request, pk=None, *args, **kwargs):
        if pk not in self.log_files:
            raise Http404

        filename = self.get_log_filename(pk)

        if not os.path.isfile(filename):
            raise Http404

        with open(filename) as f:
            lines = [line.rstrip() for line in f.readlines()]

        return Response(lines)

    def list(self, request, *args, **kwargs):
        exist = [
            log for log in self.log_files if os.path.isfile(self.get_log_filename(log))
        ]
        return Response(exist)


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

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class BulkEditView(PassUserMixin):
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

        if not user.is_superuser:
            document_objs = Document.objects.filter(pk__in=documents)
            has_perms = (
                all((doc.owner == user or doc.owner is None) for doc in document_objs)
                if method
                in [bulk_edit.set_permissions, bulk_edit.delete, bulk_edit.rotate]
                else all(
                    has_perms_owner_aware(user, "change_document", doc)
                    for doc in document_objs
                )
            )

            if not has_perms:
                return HttpResponseForbidden("Insufficient permissions")

        try:
            # TODO: parameter validation
            result = method(documents, **parameters)
            return Response({"result": result})
        except Exception as e:
            logger.warning(f"An error occurred performing bulk edit: {e!s}")
            return HttpResponseBadRequest(
                "Error performing bulk edit, check logs for more detail.",
            )


class PostDocumentView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PostDocumentSerializer
    parser_classes = (parsers.MultiPartParser,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_name, doc_data = serializer.validated_data.get("document")
        correspondent_id = serializer.validated_data.get("correspondent")
        document_type_id = serializer.validated_data.get("document_type")
        storage_path_id = serializer.validated_data.get("storage_path")
        warehouse_id = serializer.validated_data.get("warehouse")
        folder_id = serializer.validated_data.get("folder")
        dossier_id = serializer.validated_data.get("dossier")
        tag_ids = serializer.validated_data.get("tags")
        title = serializer.validated_data.get("title")
        created = serializer.validated_data.get("created")
        archive_serial_number = serializer.validated_data.get("archive_serial_number")
        custom_field_ids = serializer.validated_data.get("custom_fields")

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
        )
        # print('dossier_id',dossier_id)
        input_doc_overrides = DocumentMetadataOverrides(
            filename=doc_name,
            title=title,
            correspondent_id=correspondent_id,
            document_type_id=document_type_id,
            storage_path_id=storage_path_id,
            warehouse_id=warehouse_id,
            folder_id=folder_id,
            dossier_id=dossier_id,
            tag_ids=tag_ids,
            created=created,
            asn=archive_serial_number,
            owner_id=request.user.id,
            custom_field_ids=custom_field_ids,
        )

        async_task = consume_file.apply(
            args=[input_doc, input_doc_overrides],
        )

        return Response(async_task.id)


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

        warehouses = Warehouse.objects.annotate(
            document_count=Count(
                Case(When(documents__id__in=ids, then=1), output_field=IntegerField()),
            ),
        )

        folders = Folder.objects.annotate(
            document_count=Count(
                Case(When(documents__id__in=ids, then=1), output_field=IntegerField()),
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
                "selected_warehouses": [
                    {"id": t.id, "document_count": t.document_count} for t in warehouses
                ],
                "selected_folders": [
                    {"id": t.id, "document_count": t.document_count} for t in folders
                ],
                "selected_storage_paths": [
                    {"id": t.id, "document_count": t.document_count}
                    for t in storage_paths
                ],
            },
        )

        return r


class SearchAutoCompleteView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        result = autocomplete_elastic_search(request.query_params["term"])
        return Response(result)
        # user = self.request.user if hasattr(self.request, "user") else None
        # if "term" in request.query_params:
        #     term = request.query_params["term"]
        # else:
        #     return HttpResponseBadRequest("Term required")
        #
        # if "limit" in request.query_params:
        #     limit = int(request.query_params["limit"])
        #     if limit <= 0:
        #         return HttpResponseBadRequest("Invalid limit")
        # else:
        #     limit = 10
        #
        # from documents import index
        #
        # ix = index.open_index()
        #
        # return Response(
        #     index.autocomplete(
        #         ix,
        #         term,
        #         limit,
        #         user,
        #     ),
        # )


class StatisticsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        user = request.user if request.user is not None else None

        documents = (
            Document.objects.all().annotate()
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
        )
        untagged_tags_count = (
            tags.annotate(num_docs=Count("documents")).filter(num_docs=0).count()
        )
        correspondent_count = (
            Correspondent.objects.count()
            if user is None
            else len(
                get_objects_for_user_owner_aware(
                    user,
                    "documents.view_correspondent",
                    Correspondent,
                ),
            )
        )

        document_types = (
            DocumentType.objects.all()
            if user is None
            else get_objects_for_user_owner_aware(
                user,
                "documents.view_documenttype",
                DocumentType,
            )
        )

        unassigned_document_types_count = (
            document_types.annotate(num_docs=Count("documents"))
            .filter(num_docs=0)
            .count()
        )

        warehouse_count = (
            Warehouse.objects.count()
            if user is None
            else len(
                get_objects_for_user_owner_aware(
                    user,
                    "documents.view_warehouse",
                    Warehouse,
                ),
            )
        )

        folder_count = (
            Folder.objects.count()
            if user is None
            else len(
                get_objects_for_user_owner_aware(
                    user,
                    "documents.view_folder",
                    Folder,
                ),
            )
        )

        storage_path_count = (
            StoragePath.objects.count()
            if user is None
            else len(
                get_objects_for_user_owner_aware(
                    user,
                    "documents.view_storagepath",
                    StoragePath,
                ),
            )
        )

        documents_total = documents.count()

        inbox_tag = tags.filter(is_inbox_tag=True)

        documents_inbox = (
            documents.filter(tags__is_inbox_tag=True).distinct().count()
            if inbox_tag.exists()
            else None
        )

        document_file_type_counts = (
            documents.values("mime_type")
            .annotate(mime_type_count=Count("mime_type"))
            .order_by("-mime_type_count")
            if documents_total > 0
            else []
        )

        character_count = (
            documents.annotate(
                characters=Length("content"),
            )
            .aggregate(Sum("characters"))
            .get("characters__sum")
        )

        request_count = (
            PaperlessTask.objects.aggregate(Sum("api_call_count"))["api_call_count__sum"] or 0        )

        pages_total = documents.aggregate(Sum("page_count")).get("page_count__sum")
        return Response(
            {
                "documents_total": documents_total,
                "pages_total": pages_total,
                "documents_inbox": documents_inbox,
                "inbox_tag": inbox_tag.first().pk if inbox_tag.exists() else None,
                "document_file_type_counts": document_file_type_counts,
                "character_count": character_count,
                "request_count": request_count,
                "tag_count": len(tags),
                "untagged_tags_count": untagged_tags_count,
                "correspondent_count": correspondent_count,
                "document_type_count": document_types.count(),
                "unassigned_document_types_count": unassigned_document_types_count,
                "storage_path_count": storage_path_count,
                "warehouse_count": warehouse_count,
                "folder_count": folder_count,
            },
        )


class StatisticsCustomView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        to_date = request.query_params.get("to_date")
        from_date = request.query_params.get("from_date")
        label_graph = []
        data_count_page_graph = []
        data_graph = []
        data_document_type_graph = []
        label_document_type_graph = []
        data_tag_graph = []
        label_tag_graph = []
        data_date_request_count_graph = []
        user = request.user if request.user is not None else None

        documents = (
            Document.objects.all().defer('content')
            if user is None
            else get_objects_for_user_owner_aware(
                user,
                "documents.view_document",
                Document,
            )
        )
        if from_date and to_date:
            from datetime import datetime

            timezone = pytz.UTC
            from_date = timezone.localize(datetime.strptime(from_date, "%Y-%m-%d"))
            to_date = timezone.localize(datetime.strptime(to_date, "%Y-%m-%d"))
            to_date = to_date + timedelta(
                hours=23,
                minutes=59,
                seconds=59,
                microseconds=999999,
            )
            date_value_dict = {}
            date_request_number_dict = dict()
            current_date = from_date

            while current_date <= to_date:
                date_key = current_date.strftime("%Y-%m-%d")  # Định dạng ngày
                date_value_dict[date_key] = (0, 0)  # Thêm vào dict
                date_request_number_dict[date_key] = 0
                current_date += timedelta(days=1)

            documents_count_by_day = (
                documents.filter(created__range=(from_date, to_date))
                .annotate(created_date=TruncDate("created"))
                .values("created_date")
                .annotate(
                    document_count=Count("id"),
                    total_page_number=Sum("page_count"),
                )
                .order_by("created_date")
            )

            request_count = (
                PaperlessTask.objects.filter(date_done__range=(from_date, to_date))
                .annotate(date_done_date=TruncDate("date_done"))
                .values("date_done_date")
                .annotate(
                    # document_count=Count("id"),
                    api_call_count=Sum("api_call_count"),
                )
                .order_by("date_done_date")
            )

            print(request_count)
            for entry in request_count:
                target_date_str = entry["date_done_date"].strftime("%Y-%m-%d")
                if target_date_str in date_request_number_dict:
                    date_request_number_dict[target_date_str] = entry["api_call_count"]
            for key, value in date_request_number_dict.items():
                data_date_request_count_graph.append(value)

            for entry in documents_count_by_day:
                target_date_str = entry["created_date"].strftime("%Y-%m-%d")
                if target_date_str in date_value_dict:
                    date_value_dict[target_date_str] = (
                        entry["document_count"],
                        entry["total_page_number"],
                    )
            for key, value in date_value_dict.items():
                label_graph.append(key)
                data_graph.append(value[0])
                data_count_page_graph.append(value[1])

        top_document_types = (
            documents.values("document_type__name")
            .annotate(document_count=Count("id"))
            .order_by("-document_count")[:10]
        )
        for entry in top_document_types:
            if entry["document_type__name"] is None:
                continue
            data_document_type_graph.append(entry["document_count"])
            label_document_type_graph.append(entry["document_type__name"])

        top_tags = (
            documents.values("tags__name")
            .annotate(document_count=Count("id"))
            .order_by("-document_count")[:10]
        )
        for entry in top_tags:
            if entry["tags__name"] is None:
                # entry['tags__name'] = _('Other')
                continue
            data_tag_graph.append(entry["document_count"])
            label_tag_graph.append(entry["tags__name"])



        return Response(
            {
                "labels_graph": label_graph,
                "data_count_page_graph": data_count_page_graph,
                'data_date_request_count_graph': data_date_request_count_graph,
                "data_graph": data_graph,
                "labels_document_type_pie_graph": label_document_type_graph,
                "data_document_type_pie_graph": data_document_type_graph,
                "labels_tags_pie_graph": label_tag_graph,
                "data_tags_pie_graph": data_tag_graph,
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
        compression = serializer.validated_data.get("compression")
        content = serializer.validated_data.get("content")
        follow_filename_format = serializer.validated_data.get("follow_formatting")

        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        temp = tempfile.NamedTemporaryFile(
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
            strategy = strategy_class(zipf, follow_filename_format)
            for id in ids:
                doc = Document.objects.get(id=id)
                strategy.add_document(doc)

        with open(temp.name, "rb") as f:
            response = HttpResponse(f, content_type="application/zip")
            response["Content-Disposition"] = '{}; filename="{}"'.format(
                "attachment",
                "documents.zip",
            )

            return response


class BulkExportExcelView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = BulkDownloadSerializer
    parser_classes = (parsers.JSONParser,)

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data.get("documents")

        try:

            documents = Document.objects.filter(id__in=ids)
            # fields = CustomFieldInstance.objects.filter(document__in=ids)
            data = []
            for document in documents:
                fields = CustomFieldInstance.objects.filter(document=document.pk)
                row_data = {
                    "Tên file": document.title,
                    "Nội dung": document.content,
                    "Ngày tạo": document.created.strftime("%d-%m-%Y"),
                }
                for f in fields:
                    row_data[f.field.name] = f.value_text
                data.append(row_data)

            df = pd.DataFrame(data)
            excel_file_name = "download.xlsx"
            # Tạo response để trả về file Excel
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{excel_file_name}"'
            )

            df.to_excel(response, index=False)

            return response
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404


class BulkExportExcelFromFolderView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ExportDocumentFromFolderSerializer

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data.get("folders")

        try:

            folder_ids = Folder.objects.filter(id__in=ids).values_list("id", flat=False)
            folder_ids = [x[0] for x in folder_ids]
            if len(ids) == 0:
                folder_ids = Folder.objects.all().values_list("id", flat=False)
                folder_ids = [x[0] for x in folder_ids]

            documents = Document.objects.filter(folder__in=ids)
            # fields = CustomFieldInstance.objects.filter(document__in=ids)
            data = []
            for document in documents:
                fields = CustomFieldInstance.objects.filter(document=document.pk)
                row_data = {
                    "Tên file": document.title,
                    "Nội dung": document.content,
                    "Ngày tạo": document.created.strftime("%d-%m-%Y"),
                }
                for f in fields:
                    row_data[f.field.name] = f.value_text
                data.append(row_data)

            df = pd.DataFrame(data)
            excel_file_name = "download.xlsx"
            # Tạo response để trả về file Excel
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{excel_file_name}"'
            )

            df.to_excel(response, index=False)

            return response
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404


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

    def destroy(self, request, *args, **kwargs):
        """
        When a storage path is deleted, see if documents
        using it require a rename/move
        """
        instance = self.get_object()
        doc_ids = [doc.id for doc in instance.documents.all()]

        # perform the deletion so renaming/moving can happen
        response = super().destroy(request, *args, **kwargs)

        if len(doc_ids):
            bulk_edit.bulk_update_documents.delay(doc_ids)

        return response


class UiSettingsView(GenericAPIView):
    queryset = UiSettings.objects.all()
    permission_classes = (IsAuthenticated, DjangoModelPermissions)
    serializer_class = UiSettingsViewSerializer

    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "POST": ["%(app_label)s.change_%(model_name)s"],
    }

    def get(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.get(pk=request.user.id)
        ui_settings = {}
        if hasattr(user, "ui_settings"):
            ui_settings = user.ui_settings.settings
        if "update_checking" in ui_settings:
            ui_settings["update_checking"][
                "backend_setting"
            ] = settings.ENABLE_UPDATE_CHECK
        else:
            ui_settings["update_checking"] = {
                "backend_setting": settings.ENABLE_UPDATE_CHECK,
            }

        general_config = GeneralConfig()

        ui_settings["app_title"] = settings.APP_TITLE
        if general_config.app_title is not None and len(general_config.app_title) > 0:
            ui_settings["app_title"] = general_config.app_title
        ui_settings["app_logo"] = settings.APP_LOGO
        if general_config.app_logo is not None and len(general_config.app_logo) > 0:
            ui_settings["app_logo"] = general_config.app_logo

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


class RemoteVersionView(GenericAPIView):
    def get(self, request, format=None):
        remote_version = "0.0.0"
        is_greater_than_current = False
        current_version = packaging_version.parse(version.__full_version_str__)
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/paperless-ngx/"
                "paperless-ngx/releases/latest",
            )
            # Ensure a JSON response
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req) as response:
                remote = response.read().decode("utf8")
            try:
                remote_json = json.loads(remote)
                remote_version = remote_json["tag_name"]
                # Basically PEP 616 but that only went in 3.9
                if remote_version.startswith("ngx-"):
                    remote_version = remote_version[len("ngx-") :]
            except ValueError:
                logger.debug("An error occurred parsing remote version json")
        except urllib.error.URLError:
            logger.debug("An error occurred checking for available updates")

        is_greater_than_current = (
            packaging_version.parse(
                remote_version,
            )
            > current_version
        )

        return Response(
            {
                "version": remote_version,
                "update_available": is_greater_than_current,
            },
        )


class TasksViewSet(ReadOnlyModelViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = TasksViewSerializer

    def get_queryset(self):
        queryset = (
            PaperlessTask.objects.filter(
                acknowledged=False,
            )
            .order_by("date_created")
            .reverse()
        )
        task_id = self.request.query_params.get("task_id")
        if task_id is not None:
            queryset = PaperlessTask.objects.filter(task_id=task_id)
        return queryset


class ApprovalViewSet(ModelViewSet):
    permission_classes = (IsAuthenticated,)

    serializer_class = ApprovalSerializer
    # pagination_class = StandardPagination
    queryset = Approval.objects.all()

    def get_queryset(self):
        # TODO: get user -> group -> document ->
        if self.request.user.is_superuser:
            documents_can_change = Document.objects.all()
        else:
            documents_can_change = get_objects_for_user(
                self.request.user,
                "documents.change_document",
                with_superuser=False,
                any_perm=True,
            )
        document_ids = [x.id for x in documents_can_change]
        # print(document_ids)
        approvals = (
            Approval.objects.filter(
                Q(object_pk__in=document_ids) | Q(submitted_by=self.request.user),
            )
            .order_by("created")
            .reverse()
        )

        approvals_ids = []
        for x in approvals:
            approvals_ids.append(x.object_pk)
        document_ids_queryset = Document.objects.filter(
            id__in=approvals_ids,
        ).values_list("id", flat=True)
        document_ids_set = set(document_ids_queryset)
        approval_new = []
        for approval in approvals:
            if int(approval.object_pk) in document_ids_set:
                approval_new.append(approval)

        return approval_new

    model = Approval

    def create(self, request, *args, **kwargs):
        serializer = ApprovalSerializer(data=request.data)
        existing_approval = False
        if serializer.is_valid(raise_exception=True):
            serializer.validated_data["submitted_by"] = request.user

            existing_approval = Approval.objects.filter(
                object_pk=serializer.validated_data.get("object_pk"),
                access_type=serializer.validated_data.get("access_type"),
                ctype=serializer.validated_data.get("ctype"),
                submitted_by=self.request.user,
                status__in=["SUCCESS", "PENDING"],
            )

            submitted_by_groups = serializer.validated_data.get(
                "submitted_by_group",
                None,
            )
            group_names = ""
            if submitted_by_groups:
                existing_approval = (
                    existing_approval.filter(
                        Q(submitted_by_group__in=submitted_by_groups),
                    )
                    .prefetch_related("submitted_by_group")
                    .values_list("submitted_by_group__name", flat=True)
                )
                group_names = ", ".join(group for group in existing_approval)

            if existing_approval:
                return Response(
                    {"status": 400, "message": f"{group_names} already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)

        approval_updated.send(
            sender=self.__class__,
            approval=self.get_object(),
        )

        return response


class ApprovalUpdateMutipleView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ApprovalViewSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approvals = serializer.validated_data.get("approvals")
        status = serializer.validated_data.get("status")

        try:
            approvals_match = Approval.objects.filter(
                id__in=approvals,
            ).prefetch_related("submitted_by_group")
            document_ids = []
            for approval in approvals_match:
                if self.request.user == approval.submitted_by:
                    return HttpResponseForbidden("Insufficient permissions")
                document_ids.append(int(approval.object_pk))
            documents = Document.objects.filter(id__in=document_ids)
            for document in documents:
                if not self.request.user.has_perm("change_document", document):
                    return HttpResponseForbidden("Insufficient permissions")

            result = approvals_match.update(
                status=status,
                modified=timezone.now(),
            )
            for approval in approvals_match:
                approval_updated.send(
                    sender=self.__class__,
                    approval=approval,
                )
            return Response({"result": result})
        except Exception:
            return HttpResponseBadRequest()


class AcknowledgeTasksView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = AcknowledgeTasksViewSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tasks = serializer.validated_data.get("tasks")

        try:
            result = PaperlessTask.objects.filter(id__in=tasks).update(
                acknowledged=True,
            )
            return Response({"result": result})
        except Exception:
            return HttpResponseBadRequest()


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


class SharedLinkView(View):
    authentication_classes = []
    permission_classes = []

    def get(self, request, slug):
        share_link = ShareLink.objects.filter(slug=slug).first()
        if share_link is None:
            return HttpResponseRedirect("/accounts/login/?sharelink_notfound=1")
        if share_link.expiration is not None and share_link.expiration < timezone.now():
            return HttpResponseRedirect("/accounts/login/?sharelink_expired=1")
        return serve_file(
            doc=share_link.document,
            use_archive=share_link.file_version == "archive",
            disposition="inline",
        )


def serve_file(doc: Document, use_archive: bool, disposition: str):
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

    if doc.storage_type == Document.STORAGE_TYPE_GPG:
        file_handle = GnuPG.decrypted(file_handle)

    response = HttpResponse(file_handle, content_type=mime_type)
    # Firefox is not able to handle unicode characters in filename field
    # RFC 5987 addresses this issue
    # see https://datatracker.ietf.org/doc/html/rfc5987#section-4.2
    # Chromium cannot handle commas in the filename
    filename_normalized = normalize("NFKD", filename.replace(",", "_")).encode(
        "ascii",
        "ignore",
    )
    filename_encoded = quote(filename)
    content_disposition = (
        f"{disposition}; "
        f'filename="{filename_normalized}"; '
        f"filename*=utf-8''{filename_encoded}"
    )
    response["Content-Disposition"] = content_disposition
    return response


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
        # parent_folder_id = serializer.validated_data.get("parent_folder")[0]

        objs = object_class.objects.filter(pk__in=object_ids)

        if not user.is_superuser:
            # model_name = object_class._meta.verbose_name
            model_name = object_class.__name__.lower()
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
                #  check owner each object
                for obj in qs:
                    if (
                        obj.owner == None
                        or user.is_superuser
                        or user.owner == obj.owner
                    ):
                        continue
                    elif obj.owner != self.request.user:
                        return HttpResponseForbidden("Insufficient permissions")

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

        elif operation == "update" and object_type == "folders":
            parent_folder_id = serializer.validated_data.get("parent_folder")

            new_parent_folder = (
                Folder.objects.filter(id=parent_folder_id).first()
                if parent_folder_id
                else None
            )
            parent_folder_obj = (
                Folder.objects.get(pk=parent_folder_id) if parent_folder_id else None
            )
            folder_list = Folder.objects.filter(id__in=object_ids)
            for folder in folder_list:
                if request.data.get("parent_folder") is None:
                    pass
                elif int(request.data["parent_folder"]) == folder.id:
                    return Response(status=status.HTTP_400_BAD_REQUEST)
                elif "parent_folder" in request.data:
                    if parent_folder_obj.owner != user:
                        return HttpResponseForbidden("Insufficient permissions")
                    if new_parent_folder.path.startswith(folder.path):
                        return Response(
                            status=status.HTTP_400_BAD_REQUEST,
                            data={
                                "error": "Cannot move a folder into one of its child folders.",
                            },
                        )
                    elif new_parent_folder.type == "file":
                        return Response(status=status.HTTP_400_BAD_REQUEST)
                else:
                    request.data["parent_folder"] = None

            for folder in folder_list:
                # folder.parent_folder = parent_folder_obj
                # folder.path = f"{folder.parent_folder.path}/{folder.id}"
                # folder.save()

                # print(folder.id)
                # print(int(request.data['parent_folder'][0]))
                old_parent_folder = folder.parent_folder
                folder.parent_folder = parent_folder_obj

                if old_parent_folder != folder.parent_folder:
                    if folder.parent_folder:
                        folder.path = f"{folder.parent_folder.path}/{folder.id}"
                        folder.parent_folder = parent_folder_obj

                    else:
                        folder.path = f"{folder.id}"

                    groups = get_groups_with_only_permission(folder, "view_folder")
                    users = get_users_with_perms(
                        folder,
                        attach_perms=False,
                        with_group_users=False,
                    )
                    # logger.debug("users", users, groups, folder)
                    permissions = {
                        "view": {
                            "users": users,
                            "groups": groups,
                        },
                        "change": {
                            "users": [],
                            "groups": [],
                        },
                    }

                    update_view_folder_parent_permissions(folder, permissions)
                    folder.save()
                    self.update_child_folder_paths(folder)

            return Response(status=status.HTTP_204_NO_CONTENT)
        # elif operation == "update" and object_type == "archive_fonts":

        elif operation == "delete" and object_type == "warehouses":
            warehouses_list = Warehouse.objects.filter(id__in=object_ids)
            for warehouse in warehouses_list:
                if (
                    warehouse.owner == self.request.user
                    or warehouse.owner == self.request.user.is_superuser
                    or warehouse.owner == None
                ):
                    continue
                elif warehouse.owner != self.request.user:
                    return HttpResponseForbidden("Insufficient permissions")

            for warehouse in warehouses_list:
                warehouses = Warehouse.objects.filter(path__startswith=warehouse.path)
                warehouses.delete()

            return Response(status=status.HTTP_204_NO_CONTENT)

        elif operation == "delete" and object_type == "folders":

            folder_list = Folder.objects.filter(id__in=object_ids)
            for f in folder_list:
                if f.owner == user or user.is_superuser or f.owner is None:
                    continue
                else:
                    return HttpResponseForbidden("Insufficient permissions")

            for f in folder_list:
                folders = Folder.objects.filter(path__startswith=f.path)
                documents = Document.objects.filter(folder__in=folders)
                dossier_ids = []
                for d in documents:
                    dossier_ids.append(d.dossier.id)
                documents.delete()
                documents.delete()
                Dossier.objects.filter(id__in=dossier_ids).delete()
                folders.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        elif operation == "delete" and object_type == "dossiers":
            for dossier_id in object_ids:
                dossier = Dossier.objects.get(id=int(dossier_id))
                dossiers = Dossier.objects.filter(path__startswith=dossier.path)
                documents = Document.objects.filter(dossier__in=dossier)
                documents.delete()
                dossiers.delete()

            return Response(status=status.HTTP_204_NO_CONTENT)

        elif operation == "delete" and object_type == "backup_records":
            backup_records = BackupRecord.objects.filter(id__in=object_ids)
            file_paths = []
            for b in backup_records:
                file_path = os.path.join(settings.BACKUP_DIR, b.filename)
                file_paths.append(file_path)
            task = deleted_backup.delay(file_paths)
            backup_records.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        elif operation == "delete":

            objs.delete()

        return Response({"result": "OK"})

    def update_child_folder_paths(self, folder):
        child_folders = Folder.objects.filter(parent_folder=folder)
        for child_folder in child_folders:
            if folder.path:
                child_folder.path = f"{folder.path}/{child_folder.id}"
            else:
                child_folder.path = f"{child_folder.id}"
            child_folder.save()
            self.update_child_folder_paths(child_folder)


class WorkflowTriggerViewSet(ModelViewSet):
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    serializer_class = WorkflowTriggerSerializer
    pagination_class = StandardPagination

    model = WorkflowTrigger

    queryset = WorkflowTrigger.objects.all()


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


class SystemStatusView(PassUserMixin):
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        if not request.user.has_perm("admin.view_logentry"):
            return HttpResponseForbidden("Insufficient permissions")

        current_version = version.__full_version_str__

        install_type = "bare-metal"
        if os.environ.get("KUBERNETES_SERVICE_HOST") is not None:
            install_type = "kubernetes"
        elif os.environ.get("PNGX_CONTAINERIZED") == "1":
            install_type = "docker"

        db_conn = connections["default"]
        db_url = db_conn.settings_dict["NAME"]
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

        try:
            celery_ping = celery_app.control.inspect().ping()
            first_worker_ping = celery_ping[next(iter(celery_ping.keys()))]
            if first_worker_ping["ok"] == "pong":
                celery_active = "OK"
        except Exception:
            celery_active = "ERROR"

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

        classifier_error = None
        classifier_status = None
        try:
            classifier = load_classifier()
            if classifier is None:
                # Make sure classifier should exist
                docs_queryset = Document.objects.exclude(
                    tags__is_inbox_tag=True,
                )
                if (
                    docs_queryset.count() > 0
                    and (
                        Tag.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
                        or DocumentType.objects.filter(
                            matching_algorithm=Tag.MATCH_AUTO,
                        ).exists()
                        or Correspondent.objects.filter(
                            matching_algorithm=Tag.MATCH_AUTO,
                        ).exists()
                        or Warehouse.objects.filter(
                            matching_algorithm=Tag.MATCH_AUTO,
                        ).exists()
                        or Folder.objects.filter(
                            matching_algorithm=Tag.MATCH_AUTO,
                        ).exists()
                        or StoragePath.objects.filter(
                            matching_algorithm=Tag.MATCH_AUTO,
                        ).exists()
                    )
                    and not os.path.isfile(settings.MODEL_FILE)
                ):
                    # if classifier file doesn't exist just classify as a warning
                    classifier_error = "Classifier file does not exist (yet). Re-training may be pending."
                    classifier_status = "WARNING"
                    raise FileNotFoundError(classifier_error)
            classifier_status = "OK"
            task_result_model = apps.get_model("django_celery_results", "taskresult")
            result = (
                task_result_model.objects.filter(
                    task_name="documents.tasks.train_classifier",
                    status="SUCCESS",
                )
                .order_by(
                    "-date_done",
                )
                .first()
            )
            classifier_last_trained = result.date_done if result else None
        except Exception as e:
            if classifier_status is None:
                classifier_status = "ERROR"
            classifier_last_trained = None
            if classifier_error is None:
                classifier_error = (
                    "Unable to load classifier, check logs for more detail."
                )
            logger.exception(
                f"System status detected a possible problem while loading the classifier: {e}",
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
                    "index_status": index_status,
                    "index_last_modified": index_last_modified,
                    "index_error": index_error,
                    "classifier_status": classifier_status,
                    "classifier_last_trained": classifier_last_trained,
                    "classifier_error": classifier_error,
                },
            },
        )


class SystemStorageStatusView(PassUserMixin):
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        if not request.user.has_perm("admin.view_logentry"):
            return HttpResponseForbidden("Insufficient permissions")
        media_stats = os.statvfs(settings.MEDIA_ROOT)
        backup_path = os.path.join(settings.MEDIA_ROOT, "backups/")
        document_path = os.path.join(settings.MEDIA_ROOT, "documents/")
        documents_size_total = get_directory_size(document_path)
        backups_size_total = get_directory_size(backup_path)
        media_size_total = get_directory_size(settings.MEDIA_ROOT)
        return Response(
            {
                "total": media_stats.f_frsize * media_stats.f_blocks,
                "available": media_stats.f_frsize * media_stats.f_bavail,
                "used": media_size_total,
                "backup": backups_size_total,
                "document": documents_size_total,
                "another": media_stats.f_frsize * media_stats.f_blocks
                - media_stats.f_frsize * media_stats.f_bavail
                - media_size_total,
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
            deleted_docs = Document.deleted_objects.filter(
                id__in=doc_ids,
            ).select_related("folder", "dossier")
            # folders = {doc.folder for doc in deleted_docs}
            # dossiers = {doc.dossier for doc in deleted_docs}
            folder_set = set()
            for doc in deleted_docs:
                folder_set.update(doc.folder.path.split("/"))
            # restore folder
            folders_restore = Folder.deleted_objects.filter(id__in=list(folder_set))
            for f in folders_restore:
                f.restore(strict=False)
            for doc in deleted_docs:
                doc.restore(strict=False)
                # if doc.folder is not None:
                #     doc.folder.restore(strict=False)
                #     if doc.folder.parent_folder is not None:
                #         doc.folder.parent_folder.restore(strict=False)
                if doc.dossier is not None:
                    doc.dossier.restore(strict=False)
        elif action == "empty":
            if doc_ids is None:
                doc_ids = [doc.id for doc in docs]
            empty_trash(doc_ids=doc_ids)
        return Response({"result": "OK", "doc_ids": doc_ids})


class WarehouseViewSet(ModelViewSet, PermissionsAwareDocumentCountMixin):
    model = Warehouse

    queryset = Warehouse.objects.select_related("owner").order_by(
        Lower("name"),
    )

    serializer_class = WarehouseSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = WarehouseFilterSet
    ordering_fields = ("name", "type", "parent_warehouse", "document_count")

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            ordering = request.query_params.get("ordering", None)
            # print('ordering',ordering)
            if ordering == "document_count":
                # print('-document_count')
                sorted_data = sorted(serializer.data, key=lambda x: x["document_count"])

            elif ordering == "-document_count":
                # print('+document_count')
                sorted_data = sorted(
                    serializer.data,
                    key=lambda x: x["document_count"],
                    reverse=True,
                )
            else:
                sorted_data = serializer.data
            # print(sorted_data)
            return self.get_paginated_response(sorted_data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        # try:
        serializer = WarehouseSerializer(data=request.data)
        parent_warehouse = None
        if serializer.is_valid(raise_exception=True):
            parent_warehouse = serializer.validated_data.get("parent_warehouse", None)

        parent_warehouse = Warehouse.objects.filter(
            id=parent_warehouse.id if parent_warehouse else None,
        ).first()
        # print(parent_warehouse, serializer.validated_data.get("type"))
        if (
            serializer.validated_data.get("type") == Warehouse.WAREHOUSE
            and not parent_warehouse
        ):
            warehouse = serializer.save(owner=request.user)
            warehouse.path = str(warehouse.id)
            warehouse.save()
        elif (
            serializer.validated_data.get("type", "") == Warehouse.SHELF
            and getattr(parent_warehouse, "type", "") == Warehouse.WAREHOUSE
        ):
            warehouse = serializer.save(
                type=Warehouse.SHELF,
                parent_warehouse=parent_warehouse,
                owner=request.user,
            )
            warehouse.path = f"{parent_warehouse.path}/{warehouse.id}"
            warehouse.save()
        elif (
            serializer.validated_data.get("type", "") == Warehouse.BOXCASE
            and getattr(parent_warehouse, "type", "") == Warehouse.SHELF
        ):
            warehouse = serializer.save(
                type=Warehouse.BOXCASE,
                parent_warehouse=parent_warehouse,
                owner=request.user,
            )
            warehouse.path = f"{parent_warehouse.path}/{warehouse.id}"
            warehouse.save()
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        old_parent_warehouse = instance.parent_warehouse

        self.perform_update(serializer)
        self.update_shelf_boxcase_permisisons(instance, serializer)
        if old_parent_warehouse != instance.parent_warehouse:

            if (
                instance.type == Warehouse.SHELF
                and getattr(instance.parent_warehouse, "type", "")
                == Warehouse.WAREHOUSE
                or instance.type == Warehouse.BOXCASE
                and getattr(instance.parent_warehouse, "type", "") == Warehouse.SHELF
            ):
                instance.path = f"{instance.parent_warehouse.path}/{instance.id}"
            elif instance.type == Warehouse.WAREHOUSE and not instance.parent_warehouse:
                instance.path = str(instance.id)
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            instance.save()

            boxcase_warehouses = Warehouse.objects.filter(
                type=Warehouse.BOXCASE,
                parent_warehouse=instance,
            )
            for boxcase_warehouse in boxcase_warehouses:
                boxcase_warehouse.path = f"{instance.path}/{boxcase_warehouse.id}"
                boxcase_warehouse.save()

        return Response(serializer.data)

    def update_shelf_boxcase_permisisons(self, warehouse, serializer):
        child_shelf_boxcase = Warehouse.objects.filter(path__startswith=warehouse.path)
        documents_list = Document.objects.select_related("dossier").filter(
            warehouse__in=child_shelf_boxcase,
        )
        # documents_list = []
        # for child in child_folders:
        #     if child.type == "file":
        #         documents_list._append(child.o)

        permissions = serializer.validated_data.get("set_permissions")
        permissions_copy = permissions.copy()
        update_view_warehouse_shelf_boxcase_permissions(warehouse, permissions_copy)
        owner = serializer.validated_data.get("owner")
        merge = False

        try:
            qs = child_shelf_boxcase

            # if merge is true, we dont want to remove the owner
            if "owner" in serializer.validated_data and (
                not merge or (merge and owner is not None)
            ):
                # if merge is true, we dont want to overwrite the owner
                qs_owner_update = qs.filter(owner__isnull=True) if merge else qs
                qs_owner_update.update(owner=owner)
            if "set_permissions" in serializer.validated_data:
                for obj in qs:
                    set_permissions_for_object(
                        permissions=permissions,
                        object=obj,
                        merge=merge,
                    )
                for obj in documents_list:
                    set_permissions_for_object(
                        permissions=permissions,
                        object=obj,
                        merge=merge,
                    )
                    set_permissions_for_object(
                        permissions=permissions,
                        object=obj.dossier,
                        merge=merge,
                    )

        except Exception as e:
            logger.warning(
                f"An error occurred performing bulk permissions edit: {e!s}",
            )
            return HttpResponseBadRequest(
                "Error performing bulk permissions edit, check logs for more detail.",
            )

    def partial_update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        old_parent_warehouse = instance.parent_warehouse

        self.perform_update(serializer)

        if old_parent_warehouse != instance.parent_warehouse:

            if (
                instance.type == Warehouse.SHELF
                and getattr(instance.parent_warehouse, "type", "")
                == Warehouse.WAREHOUSE
                or instance.type == Warehouse.BOXCASE
                and getattr(instance.parent_warehouse, "type", "") == Warehouse.SHELF
            ):
                instance.path = f"{instance.parent_warehouse.path}/{instance.id}"
            elif instance.type == Warehouse.WAREHOUSE and not instance.parent_warehouse:
                instance.path = str(instance.id)
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            instance.save()

            boxcase_warehouses = Warehouse.objects.filter(
                type=Warehouse.BOXCASE,
                parent_warehouse=instance,
            )
            for boxcase_warehouse in boxcase_warehouses:
                boxcase_warehouse.path = f"{instance.path}/{boxcase_warehouse.id}"
                boxcase_warehouse.save()

        return Response(serializer.data)

    def destroy(self, request, pk, *args, **kwargs):
        warehouse = Warehouse.objects.get(id=pk)
        warehouses = Warehouse.objects.filter(path__startswith=warehouse.path)
        # documents = Document.objects.filter(warex1house__in=warehouses)
        # documents.delete()
        warehouses.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["get"], detail=True)
    def warehouse_path(self, request, pk=None):
        if request.method == "GET":
            try:
                warehouse = Warehouse.objects.get(pk=pk)
                warehouse_path_ids = warehouse.path.split("/")
                warehouses = Warehouse.objects.filter(id__in=warehouse_path_ids)
                warehouse_dict = {}
                for f in warehouses:
                    warehouse_dict[f.id] = f
                warehouse_path_list = []
                for p in warehouse_path_ids:
                    value = warehouse_dict.get(int(p))
                    warehouse_path_list.append(value)
                warehouse_serializers = WarehouseSerializer(
                    warehouse_path_list,
                    many=True,
                )
                return Response(
                    {"results": warehouse_serializers.data},
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                logger.error(f"An error occurred retrieving warehouse: {e!s}")
                return Response(
                    {
                        "error": "Error retrieving warehouses, check logs for more detail.",
                    },
                )


class FolderViewSet(ModelViewSet, PermissionsAwareDocumentCountMixin):
    model = Folder

    queryset = (
        Folder.objects.annotate(
            type_order=Case(
                When(type="folder", then=0),  # Gán giá trị 0 cho folder
                When(type="file", then=1),  # Gán giá trị 1 cho file
                output_field=IntegerField(),
            ),
        )
        .order_by("type_order", Lower("name"))
        .prefetch_related("documents")
    )

    serializer_class = FolderSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = FolderFilterSet
    ordering_fields = ("name", "path", "parent_folder", "document_count")

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            ordering = request.query_params.get("ordering", None)
            if ordering == "document_count":
                sorted_data = sorted(serializer.data, key=lambda x: x["document_count"])
            elif ordering == "-document_count":

                sorted_data = sorted(
                    serializer.data,
                    key=lambda x: x["document_count"],
                    reverse=True,
                )
            else:
                sorted_data = serializer.data

            return self.get_paginated_response(sorted_data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def getFolderDoc(self, request):
        currentUser = request.user
        documents = list(
            Document.objects.filter(folder=None, owner=currentUser)
            .order_by("-created")
            .values(),
        )
        folders = list(
            Folder.objects.filter(parent_folder=None, owner=currentUser).order_by(
                "name",
            ),
        )
        folders_serialisers = FolderSerializer(folders, many=True)
        return {
            "documents": documents,
            "folders": folders_serialisers.data,
        }

    @action(methods=["get"], detail=False)
    def folders_documents(self, request):

        if request.method == "GET":
            try:
                return Response(self.getFolderDoc(request))
            except Exception as e:
                logger.warning(f"An error occurred retrieving folders: {e!s}")
                return Response(
                    {"error": "Error retrieving folders, check logs for more detail."},
                )

    @action(methods=["get"], detail=True)
    def bulk_export_excel(self, request, pk=None):
        try:
            folder = Folder.objects.get(pk=pk)
            list_folders = Folder.objects.filter(
                path__startswith=folder.path,
            ).values_list("id")
            folder_ids = [x[0] for x in list_folders]
            documents = Document.objects.filter(folder__id__in=folder_ids)
            data = []
            for document in documents:
                row_data = {
                    "Tên file": document.title,
                    "Nội dung": document.content,
                    "Ngày tạo": document.created.strftime("%d-%m-%Y"),
                }
                fields = CustomFieldInstance.objects.filter(document=document)
                for f in fields:
                    row_data[f.field.name] = f.value_text
                data.append(row_data)

            df = pd.DataFrame(data)
            excel_file_name = "download.xlsx"
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{excel_file_name}"'
            )
            df.to_excel(response, index=False)
            return response
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404

    @action(methods=["get"], detail=True)
    def folder_path(self, request, pk=None):
        if request.method == "GET":
            try:
                fol = Folder.objects.get(pk=pk)
                folder_path = fol.path.split("/")
                folders = Folder.objects.filter(id__in=folder_path)
                folders_dict = {}
                for f in folders:
                    folders_dict[f.id] = f
                    # print(f)
                new_folder_path = []
                for p in folder_path:
                    value = folders_dict.get(int(p))
                    new_folder_path.append(value)
                folders_serialisers = FolderSerializer(new_folder_path, many=True)
                return Response(
                    {"results": folders_serialisers.data},
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                logger.warning(f"An error occurred retrieving folders: {e!s}")
                return Response(
                    {"error": "Error retrieving folders, check logs for more detail."},
                )

    def getFolderDocById(self, fol):
        currentUser = self.request.user
        documents = list(
            Document.objects.filter(folder=fol, owner=currentUser)
            .order_by("-created")
            .values(),
        )
        child_folders = list(
            Folder.objects.filter(parent_folder=fol, owner=currentUser).order_by(
                "name",
            ),
        )
        folders_serialisers = FolderSerializer(child_folders, many=True)
        return {
            "documents": documents,
            "folders": folders_serialisers.data,
        }

    @action(methods=["get"], detail=True)
    def folders_documents_by_id(self, request, pk=None):
        currentUser = request.user
        try:
            fol = Folder.objects.get(pk=pk)
            if currentUser is not None and not has_perms_owner_aware(
                currentUser,
                "view_folder",
                fol,
            ):
                return HttpResponseForbidden("Insufficient permissions to view folders")
        except Folder.DoesNotExist:
            raise Http404

        if request.method == "GET":
            try:
                return Response(self.getFolderDocById(fol))
            except Exception as e:
                logger.warning(f"An error occurred retrieving folders: {e!s}")
                return Response(
                    {"error": "Error retrieving folders, check logs for more detail."},
                )

    def create(self, request, *args, **kwargs):
        # try:
        serializer = FolderSerializer(data=request.data)
        parent_folder = None
        if serializer.is_valid(raise_exception=True):
            parent_folder = serializer.validated_data.get("parent_folder", None)

        parent_folder = Folder.objects.filter(
            id=parent_folder.id if parent_folder else 0,
        ).first()

        if parent_folder == None:
            folder = serializer.save(owner=request.user)
            folder.path = str(folder.id)
            folder.checksum = hashlib.md5(
                f"{folder.id}.{folder.name}".encode(),
            ).hexdigest()
            folder.save()
        elif parent_folder:
            user_can_change = check_user_can_change_folder(request.user, parent_folder)
            if not user_can_change:
                return Response(
                    data={
                        "detail": "You do not have permission to perform this action.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            folder = serializer.save(parent_folder=parent_folder, owner=request.user)
            folder.path = f"{parent_folder.path}/{folder.id}"
            folder.checksum = hashlib.md5(
                f"{folder.id}.{folder.name}".encode(),
            ).hexdigest()
            folder.save()
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        if request.data.get("parent_folder") is None:
            pass
        elif (
            "parent_folder" in request.data
            and int(request.data["parent_folder"]) == instance.id
        ):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        elif "parent_folder" in request.data:
            new_parent_folder = Folder.objects.get(
                id=int(request.data["parent_folder"]),
            )
            if new_parent_folder.path.startswith(instance.path):
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data={
                        "error": "Cannot move a folder into one of its child folders.",
                    },
                )
            elif new_parent_folder.type == "file":
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            request.data["parent_folder"] = None

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data["updated"] = timezone.now()

        old_parent_folder = instance.parent_folder

        self.perform_update(serializer)
        self.update_document_name(instance, serializer)
        # update permission document
        # update permission folder child
        self.update_child_folder_permisisons(instance, serializer)
        if old_parent_folder != instance.parent_folder:
            if instance.parent_folder:
                instance.path = f"{instance.parent_folder.path}/{instance.id}"

            else:
                instance.path = f"{instance.id}"
            instance.save()

            self.update_child_folder_paths(instance)

        return Response(serializer.data)

    def update_document_name(self, instance, serializer):
        document = Document.objects.filter(folder_id=instance.id).first()
        if document is None:
            return
        document.title = serializer.validated_data.get("name")
        document.save()

    def partial_update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        if request.data.get("parent_folder") is None:
            pass
        elif (
            "parent_folder" in request.data
            and int(request.data["parent_folder"]) == instance.id
        ):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        elif "parent_folder" in request.data:
            new_parent_folder = Folder.objects.get(
                id=int(request.data["parent_folder"]),
            )
            if new_parent_folder.path.startswith(instance.path):
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data={
                        "error": "Cannot move a folder into one of its child folders.",
                    },
                )
            elif new_parent_folder.type == "file":
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            request.data["parent_folder"] = None

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        old_parent_folder = instance.parent_folder

        self.perform_update(serializer)

        if old_parent_folder != instance.parent_folder:
            if instance.parent_folder:
                instance.path = f"{instance.parent_folder.path}/{instance.id}"
            else:
                instance.path = f"{instance.id}"
            instance.save()

            self.update_child_folder_paths(instance)

        return Response(serializer.data)

    def update_child_folder_paths(self, folder):
        child_folders = Folder.objects.filter(parent_folder=folder)
        for child_folder in child_folders:
            if folder.path:
                child_folder.path = f"{folder.path}/{child_folder.id}"
            else:
                child_folder.path = f"{child_folder.id}"
            child_folder.save()
            self.update_child_folder_paths(child_folder)

    def update_child_folder_permisisons(self, folder, serializer):
        child_folders = Folder.objects.filter(path__startswith=folder.path)
        documents_list = Document.objects.select_related("dossier").filter(
            folder__in=child_folders,
        )
        # documents_list = []
        # for child in child_folders:
        #     if child.type == "file":
        #         documents_list._append(child.o)

        permissions = serializer.validated_data.get("set_permissions")
        permissions_copy = permissions.copy()
        update_view_folder_parent_permissions(folder, permissions_copy)
        owner = serializer.validated_data.get("owner")
        merge = serializer.validated_data.get("merge")

        try:
            qs = child_folders

            # if merge is true, we dont want to remove the owner
            if "owner" in serializer.validated_data and (
                not merge or (merge and owner is not None)
            ):
                # if merge is true, we dont want to overwrite the owner
                qs_owner_update = qs.filter(owner__isnull=True) if merge else qs
                qs_owner_update.update(owner=owner)
            if "set_permissions" in serializer.validated_data:
                for obj in qs:
                    set_permissions_for_object(
                        permissions=permissions,
                        object=obj,
                        merge=merge,
                    )
                for obj in documents_list:
                    set_permissions_for_object(
                        permissions=permissions,
                        object=obj,
                        merge=merge,
                    )
                    set_permissions_for_object(
                        permissions=permissions,
                        object=obj.dossier,
                        merge=merge,
                    )

        except Exception as e:
            logger.warning(
                f"An error occurred performing bulk permissions edit: {e!s}",
            )
            return HttpResponseBadRequest(
                "Error performing bulk permissions edit, check logs for more detail.",
            )

    def destroy(self, request, pk, *args, **kwargs):
        folder = Folder.objects.get(id=pk)
        folders = Folder.objects.filter(path__startswith=folder.path)
        documents = Document.objects.filter(folder__in=folders)
        dossier_ids = []
        for d in documents:
            dossier_ids.append(d.dossier.id)

        dossier = Dossier.objects.filter(id__in=dossier_ids)
        documents.delete()
        dossier.delete()
        folders.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class DossierViewSet(ModelViewSet, PermissionsAwareDocumentCountMixin):
    model = Dossier

    queryset = Dossier.objects.select_related("owner").order_by(
        Lower("name"),
    )

    serializer_class = DossierSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = DossierFilterSet
    ordering_fields = ("name", "type", "dossier_form")

    def create(self, request, *args, **kwargs):
        # try:
        serializer = DossierSerializer(data=request.data)
        parent_dossier = None
        set_permissions = None
        if serializer.is_valid(raise_exception=True):
            parent_dossier = serializer.validated_data.get("parent_dossier", None)
            set_permissions = serializer.validated_data.get("set_permissions", None)

        parent_dossier = Dossier.objects.filter(
            id=parent_dossier.id if parent_dossier else 0,
        ).first()

        if parent_dossier == None:
            dossier = serializer.save(owner=request.user)

            dossier.path = str(dossier.id)
            dossier.save()
        elif parent_dossier:
            # dossier = serializer.save(owner=request.user)
            dossier = serializer.save(parent_dossier=parent_dossier, owner=request.user)
            dossier.path = f"{parent_dossier.path}/{dossier.id}"
            dossier.save()
            #   assign permissions to dossier
            set_permissions_for_object(
                permissions=set_permissions,
                object=dossier,
                merge=True,
            )
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update_folder_permisisons(self, folder, serializer):
        permissions = serializer.validated_data.get("set_permissions")
        owner = serializer.validated_data.get("owner")
        merge = serializer.validated_data.get("merge")
        try:
            qs = folder

            # if merge is true, we dont want to remove the owner
            if "owner" in serializer.validated_data and (
                not merge or (merge and owner is not None)
            ):
                # if merge is true, we dont want to overwrite the owner
                qs_owner_update = qs.filter(owner__isnull=True) if merge else qs
                qs_owner_update.owner = owner
                qs_owner_update.save()

            if "set_permissions" in serializer.validated_data:
                set_permissions_for_object(
                    permissions=permissions,
                    object=folder,
                    merge=merge,
                )
        except Exception as e:
            logger.warning(
                f"An error occurred performing permissions edit: {e!s}",
            )
            return HttpResponseBadRequest(
                "Error performing permissions edit, check logs for more detail.",
            )

    def update_document_permisisons(self, document, serializer):
        permissions = serializer.validated_data.get("set_permissions")
        owner = serializer.validated_data.get("owner")
        merge = serializer.validated_data.get("merge")
        try:
            qs = document
            # if merge is true, we dont want to remove the owner
            if "owner" in serializer.validated_data and (
                not merge or (merge and owner is not None)
            ):
                # if merge is true, we dont want to overwrite the owner
                qs_owner_update = qs.filter(owner__isnull=True) if merge else qs
                qs_owner_update.owner = owner
                qs_owner_update.save()

            if "set_permissions" in serializer.validated_data:
                set_permissions_for_object(
                    permissions=permissions,
                    object=document,
                    merge=merge,
                )
        except Exception as e:
            logger.warning(
                f"An error occurred performing permissions edit: {e!s}",
            )
            return HttpResponseBadRequest(
                "Error performing permissions edit, check logs for more detail.",
            )

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=False)
        response = super().update(request, *args, **kwargs)
        instance = self.get_object()
        if instance.type == "FILE":
            document = Document.objects.select_related("folder").get(
                dossier=instance.id,
            )
            if document:
                self.update_folder_permisisons(document.folder, serializer)
                self.update_document_permisisons(document, serializer)

        return response

    # def update(self, request, *args, **kwargs):
    #     partial = kwargs.pop('partial', False)
    #     instance = self.get_object()
    #     if request.data.get('parent_dossier') is None:
    #         pass
    #     elif 'parent_dossier' in request.data and int(request.data['parent_dossier']) == instance.id:
    #         return Response(status=status.HTTP_400_BAD_REQUEST)

    #     elif 'parent_dossier' in request.data:
    #         new_parent_dossier = Dossier.objects.get(id=int(request.data['parent_dossier']))
    #         if new_parent_dossier.path.startswith(instance.path):
    #             return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'Cannot move a dossier into one of its child dossiers.'})
    #     else:
    #         request.data['parent_dossier'] = None

    #     serializer = self.get_serializer(instance, data=request.data, partial=partial)
    #     serializer.is_valid(raise_exception=True)

    #     old_parent_dossier = instance.parent_dossier

    #     self.perform_update(serializer)

    #     if old_parent_dossier != instance.parent_dossier:
    #         if instance.parent_dossier:
    #             instance.path = f"{instance.parent_dossier.path}/{instance.id}"

    #         else:
    #             instance.path = f"{instance.id}"
    #         instance.save()

    #         self.update_child_dossier_paths(instance)

    #     return Response(serializer.data)

    @action(methods=["get"], detail=True)
    def dossier_path(self, request, pk=None):
        if request.method == "GET":
            try:
                fol = Dossier.objects.get(pk=pk)
                dossier_path = fol.path.split("/")
                dossiers = Dossier.objects.filter(id__in=dossier_path)
                dossiers_dict = {}
                for f in dossiers:
                    dossiers_dict[f.id] = f
                    # print(f)
                new_dossier_path = []
                for p in dossier_path:
                    value = dossiers_dict.get(int(p))
                    new_dossier_path.append(value)
                dossiers_serialisers = DossierSerializer(new_dossier_path, many=True)
                return Response(
                    {"results": dossiers_serialisers.data},
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                logger.warning(f"An error occurred retrieving dossiers: {e!s}")
                return Response(
                    {"error": "Error retrieving dossiers, check logs for more detail."},
                )

    def destroy(self, request, pk, *args, **kwargs):
        dossier = Dossier.objects.get(id=pk)
        dossiers = Dossier.objects.filter(path__startswith=dossier.path)
        documents = Document.objects.filter(dossier__in=dossiers)
        folders = Folder.objects.filter(
            id__in=documents.select_related("folder")
            .all()
            .values_list("folder", flat=True),
        )
        folders.delete()
        documents.delete()
        dossiers.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class DossierFormViewSet(ModelViewSet, PermissionsAwareDocumentCountMixin):
    model = DossierForm

    queryset = DossierForm.objects.select_related("owner").order_by(
        Lower("name"),
    )

    serializer_class = DossierFormSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = DossierFormFilterSet
    ordering_fields = ("name", "type")

    def create(self, request, *args, **kwargs):
        serializer = DossierFormSerializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            permissions = serializer.validated_data.get("set_permissions")
            # owner = serializer.validated_data.get("owner")
            # merge = serializer.validated_data.get("merge")
            dossier_form = serializer.save(owner=request.user)
            set_permissions_for_object(
                permissions=permissions,
                object=dossier_form,
                merge=True,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # def create(self, request, *args, **kwargs):
    #     # try:
    #     serializer = DossierFormSerializer(data=request.data)
    #     parent_dossier = None
    #     if serializer.is_valid(raise_exception=True):
    #         parent_dossier = serializer.validated_data.get('parent_dossier',None)

    #     parent_dossier = Dossier.objects.filter(id=parent_dossier.id if parent_dossier else 0).first()

    #     if parent_dossier == None:
    #         dossier = serializer.save(owner=request.user)

    #         dossier.path = str(dossier.id)
    #         dossier.save()
    #     elif parent_dossier:
    #         dossier = serializer.save(owner=request.user)
    #         if parent_dossier.is_form == True and dossier.is_form == False:
    #             dossier.path = str(dossier.id)
    #         elif parent_dossier.is_form == True and dossier.is_form == True:
    #             dossier = serializer.save(parent_dossier=None,owner=request.user)
    #             dossier.path = f"{parent_dossier.path}/{dossier.id}"
    #         else:
    #             dossier = serializer.save(parent_dossier=parent_dossier,owner=request.user)
    #             dossier.path = f"{parent_dossier.path}/{dossier.id}"
    #         dossier.save()
    #     else:
    #         return Response(status=status.HTTP_400_BAD_REQUEST)

    #     return Response(serializer.data,status=status.HTTP_201_CREATED)

    # def update_child_dossier_paths(self, dossier):
    #     child_dossiers = Dossier.objects.filter(parent_dossier=dossier)
    #     for child_dossier in child_dossiers:
    #         if dossier.path:
    #             child_dossier.path = f"{dossier.path}/{child_dossier.id}"
    #         else:
    #             child_dossier.path = f"{child_dossier.id}"
    #         child_dossier.save()
    #         self.update_child_dossier_paths(child_dossier)

    # def update(self, request, *args, **kwargs):
    #     partial = kwargs.pop('partial', False)
    #     instance = self.get_object()
    #     if request.data.get('parent_dossier') is None:
    #         pass
    #     elif 'parent_dossier' in request.data and int(request.data['parent_dossier']) == instance.id:
    #         return Response(status=status.HTTP_400_BAD_REQUEST)

    #     elif 'parent_dossier' in request.data:
    #         new_parent_dossier = Dossier.objects.get(id=int(request.data['parent_dossier']))
    #         if new_parent_dossier.path.startswith(instance.path):
    #             return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'Cannot move a dossier into one of its child dossiers.'})
    #     else:
    #         request.data['parent_dossier'] = None

    #     serializer = self.get_serializer(instance, data=request.data, partial=partial)
    #     serializer.is_valid(raise_exception=True)

    #     old_parent_dossier = instance.parent_dossier

    #     self.perform_update(serializer)

    #     if old_parent_dossier != instance.parent_dossier:
    #         if instance.parent_dossier:
    #             instance.path = f"{instance.parent_dossier.path}/{instance.id}"

    #         else:
    #             instance.path = f"{instance.id}"
    #         instance.save()

    #         self.update_child_dossier_paths(instance)

    #     return Response(serializer.data)

    # @action(methods=["get"], detail=True)
    # def dossier_path(self, request, pk=None):
    #     if request.method == "GET":
    #         try:
    #             fol = Dossier.objects.get(pk=pk)
    #             dossier_path = fol.path.split('/')
    #             dossiers = Dossier.objects.filter(id__in = dossier_path)
    #             dossiers_dict = {}
    #             for f in dossiers:
    #                 dossiers_dict[f.id] = f
    #                 # print(f)
    #             new_dossier_path = []
    #             for p in dossier_path:
    #                 value = dossiers_dict.get(int(p))
    #                 new_dossier_path.append(value)
    #             dossiers_serialisers = DossierSerializer(new_dossier_path, many=True)
    #             return Response({"results":dossiers_serialisers.data},status=status.HTTP_200_OK)
    #         except Exception as e:
    #             logger.warning(f"An error occurred retrieving dossiers: {e!s}")
    #             return Response(
    #                 {"error": "Error retrieving dossiers, check logs for more detail."},
    #             )


class BackupRecordViewSet(ModelViewSet):
    model = BackupRecord

    queryset = BackupRecord.objects.all()

    serializer_class = BackupRecordSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        ObjectOwnedOrGrantedPermissionsFilter,
    )
    filterset_class = BackupRecordFilterSet
    ordering_fields = "created_at"

    def create(self, request, *args, **kwargs):
        try:

            backup_exist = BackupRecord.objects.filter(
                Q(is_backup=True) | Q(is_restore=True),
            )
            if backup_exist.count() > 0:
                return Response(
                    {"message": _("Backup and restore are in progress")},
                    status=status.HTTP_409_CONFLICT,
                )
            path_document_media = settings.MEDIA_ROOT / "documents"

            if not check_storage([path_document_media], settings.MEDIA_ROOT):
                return Response(
                    {"message": _("Insufficient capacity for backup/restore")},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            used_size = get_directory_size(path_document_media)
            documents = Document.objects.all()
            documents_deleted = Document.deleted_objects.all()
            folders = Folder.objects.all()
            dossiers = Dossier.objects.all()
            detail = {"documents": documents.count(), "size": used_size}
            from datetime import datetime

            current_date = datetime.now().strftime("%Y_%m_%d")

            # Tạo thư mục sao lưu theo ngày tháng năm
            backups_name = (
                BackupRecord.objects.filter(filename__startswith=current_date)
                .order_by("filename")
                .values_list("filename", flat=True)
            )
            name = current_date
            if backups_name.count() > 0:
                name = generate_unique_name(current_date, backups_name)
            backup = BackupRecord.objects.create(filename=name, detail=detail)
            backup.is_backup = True
            backup.save()

            async_task_backup = backup_documents.delay(
                backup,
                documents,
                documents_deleted,
                folders,
                dossiers,
                name,
            )
            return Response(async_task_backup.id)
        except Exception as e:
            return Response(
                {"error": e},
            )

    # def backup(self, request, pk=None):
    #     try:
    #         async_task_backup = backup_documents.apply(
    #             args=[]
    #         )
    #         return Response(async_task_backup.id)
    #     except Exception as e:
    #         raise Http404

    @action(methods=["post"], detail=True)
    def restore(self, request, pk=None):
        try:
            backup_exist = BackupRecord.objects.filter(
                Q(is_backup=True) | Q(is_restore=True),
            )
            if backup_exist.count() > 0:
                return Response(
                    {"message": _("Backup and restore are in progress")},
                    status=status.HTTP_409_CONFLICT,
                )
            backup = BackupRecord.objects.get(id=pk)
            path_document_media = settings.MEDIA_ROOT / "documents"
            backup_root_dir = os.path.join(settings.BACKUP_DIR, backup.filename)
            if not check_storage(
                [backup_root_dir, path_document_media],
                settings.MEDIA_ROOT,
            ):
                return Response(
                    {"message": _("Insufficient capacity for backup/restore")},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            backup.is_restore = True
            backup.restore_at = timezone.now()
            backup.save()
            if request.user is not None and not has_perms_owner_aware(
                request.user,
                "view_backup_record",
                backup,
            ):
                return HttpResponseForbidden("Insufficient permissions")
            async_task_restore = restore_documents.delay(backup)

            return Response(async_task_restore.id)
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404
