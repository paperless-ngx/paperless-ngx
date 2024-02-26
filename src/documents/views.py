import itertools
import json
import logging
import os
import re
import tempfile
import urllib
import zipfile
from datetime import datetime
from pathlib import Path
from time import mktime
from unicodedata import normalize
from urllib.parse import quote

import pathvalidate
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Case
from django.db.models import Count
from django.db.models import IntegerField
from django.db.models import Max
from django.db.models import Sum
from django.db.models import When
from django.db.models.functions import Length
from django.db.models.functions import Lower
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import get_language
from django.views import View
from django.views.decorators.cache import cache_control
from django.views.decorators.http import condition
from django.views.decorators.http import last_modified
from django.views.generic import TemplateView
from django_filters.rest_framework import DjangoFilterBackend
from langdetect import detect
from packaging import version as packaging_version
from rest_framework import parsers
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter
from rest_framework.filters import SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework.viewsets import ModelViewSet
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.viewsets import ViewSet

from documents import bulk_edit
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
from documents.filters import CorrespondentFilterSet
from documents.filters import CustomFieldFilterSet
from documents.filters import DocumentFilterSet
from documents.filters import DocumentTypeFilterSet
from documents.filters import ObjectOwnedOrGrantedPermissionsFilter
from documents.filters import ShareLinkFilterSet
from documents.filters import StoragePathFilterSet
from documents.filters import TagFilterSet
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
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.parsers import get_parser_class_for_mime_type
from documents.parsers import parse_date_generator
from documents.permissions import PaperlessAdminPermissions
from documents.permissions import PaperlessObjectPermissions
from documents.permissions import get_objects_for_user_owner_aware
from documents.permissions import has_perms_owner_aware
from documents.permissions import set_permissions_for_object
from documents.serialisers import AcknowledgeTasksViewSerializer
from documents.serialisers import BulkDownloadSerializer
from documents.serialisers import BulkEditObjectsSerializer
from documents.serialisers import BulkEditSerializer
from documents.serialisers import CorrespondentSerializer
from documents.serialisers import CustomFieldSerializer
from documents.serialisers import DocumentListSerializer
from documents.serialisers import DocumentSerializer
from documents.serialisers import DocumentTypeSerializer
from documents.serialisers import PostDocumentSerializer
from documents.serialisers import SavedViewSerializer
from documents.serialisers import ShareLinkSerializer
from documents.serialisers import StoragePathSerializer
from documents.serialisers import TagSerializer
from documents.serialisers import TagSerializerVersion1
from documents.serialisers import TasksViewSerializer
from documents.serialisers import UiSettingsViewSerializer
from documents.serialisers import WorkflowActionSerializer
from documents.serialisers import WorkflowSerializer
from documents.serialisers import WorkflowTriggerSerializer
from documents.signals import document_updated
from documents.tasks import consume_file
from paperless import version
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


class PassUserMixin(CreateModelMixin):
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


class CorrespondentViewSet(ModelViewSet, PassUserMixin):
    model = Correspondent

    queryset = (
        Correspondent.objects.annotate(
            document_count=Count("documents"),
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


class TagViewSet(ModelViewSet, PassUserMixin):
    model = Tag

    queryset = (
        Tag.objects.annotate(document_count=Count("documents"))
        .select_related("owner")
        .order_by(
            Lower("name"),
        )
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


class DocumentTypeViewSet(ModelViewSet, PassUserMixin):
    model = DocumentType

    queryset = (
        DocumentType.objects.annotate(
            document_count=Count("documents"),
        )
        .select_related("owner")
        .order_by(Lower("name"))
    )

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
    search_fields = ("title", "correspondent__name", "content")
    ordering_fields = (
        "id",
        "title",
        "correspondent__name",
        "document_type__name",
        "created",
        "modified",
        "added",
        "archive_serial_number",
        "num_notes",
        "owner",
    )

    def get_queryset(self):
        return (
            Document.objects.distinct()
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
        kwargs.setdefault(
            "full_perms",
            self.request.query_params.get("full_perms", False),
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
            if request.user is not None and not has_perms_owner_aware(
                request.user,
                "view_document",
                doc,
            ):
                return HttpResponseForbidden("Insufficient permissions")
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


class SearchResultSerializer(DocumentSerializer, PassUserMixin):
    def to_representation(self, instance):
        doc = (
            Document.objects.select_related(
                "correspondent",
                "storage_path",
                "document_type",
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
            "score": instance.score,
            "highlights": instance.highlights("content", text=doc.content),
            "note_highlights": (
                instance.highlights("notes", text=notes) if doc else None
            ),
            "rank": instance.rank,
        }

        return r


class UnifiedSearchViewSet(DocumentViewSet):
    def __init__(self, *args, **kwargs):
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
                self.request.user,
            )
        else:
            return super().filter_queryset(queryset)

    def list(self, request, *args, **kwargs):
        if self._is_search_request():
            from documents import index

            try:
                with index.open_index_searcher() as s:
                    self.searcher = s
                    return super().list(request)
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


class BulkEditView(GenericAPIView, PassUserMixin):
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
                if method == bulk_edit.set_permissions
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
        tag_ids = serializer.validated_data.get("tags")
        title = serializer.validated_data.get("title")
        created = serializer.validated_data.get("created")
        archive_serial_number = serializer.validated_data.get("archive_serial_number")

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
        )

        async_task = consume_file.delay(
            input_doc,
            input_doc_overrides,
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
            },
        )

        return r


class SearchAutoCompleteView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        user = self.request.user if hasattr(self.request, "user") else None

        if "term" in request.query_params:
            term = request.query_params["term"]
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


class StatisticsView(APIView):
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
        document_type_count = (
            DocumentType.objects.count()
            if user is None
            else len(
                get_objects_for_user_owner_aware(
                    user,
                    "documents.view_documenttype",
                    DocumentType,
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

        return Response(
            {
                "documents_total": documents_total,
                "documents_inbox": documents_inbox,
                "inbox_tag": inbox_tag.first().pk if inbox_tag.exists() else None,
                "document_file_type_counts": document_file_type_counts,
                "character_count": character_count,
                "tag_count": len(tags),
                "correspondent_count": correspondent_count,
                "document_type_count": document_type_count,
                "storage_path_count": storage_path_count,
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


class StoragePathViewSet(ModelViewSet, PassUserMixin):
    model = StoragePath

    queryset = (
        StoragePath.objects.annotate(document_count=Count("documents"))
        .select_related("owner")
        .order_by(
            Lower("name"),
        )
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


class UiSettingsView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = UiSettingsViewSerializer

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


class BulkEditObjectsView(GenericAPIView, PassUserMixin):
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

        objs = object_class.objects.filter(pk__in=object_ids)

        if not user.is_superuser:
            model_name = object_class._meta.verbose_name
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
