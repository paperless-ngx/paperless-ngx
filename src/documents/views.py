import json
import logging
import os
import tempfile
import urllib
import uuid
import zipfile
from datetime import datetime
from time import mktime
from unicodedata import normalize
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Case
from django.db.models import Count
from django.db.models import IntegerField
from django.db.models import Max
from django.db.models import When
from django.db.models.functions import Lower
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.utils.translation import get_language
from django.views.decorators.cache import cache_control
from django.views.generic import TemplateView
from django_filters.rest_framework import DjangoFilterBackend
from django_q.tasks import async_task
from packaging import version as packaging_version
from paperless import version
from paperless.db import GnuPG
from paperless.views import StandardPagination
from rest_framework import parsers
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter
from rest_framework.filters import SearchFilter
from rest_framework.generics import GenericAPIView
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

from .bulk_download import ArchiveOnlyStrategy
from .bulk_download import OriginalAndArchiveStrategy
from .bulk_download import OriginalsOnlyStrategy
from .classifier import load_classifier
from .filters import CorrespondentFilterSet
from .filters import DocumentFilterSet
from .filters import DocumentTypeFilterSet
from .filters import StoragePathFilterSet
from .filters import TagFilterSet
from .matching import match_correspondents
from .matching import match_document_types
from .matching import match_storage_paths
from .matching import match_tags
from .models import Correspondent
from .models import Document
from .models import DocumentType
from .models import PaperlessTask
from .models import SavedView
from .models import StoragePath
from .models import Tag
from .parsers import get_parser_class_for_mime_type
from .serialisers import AcknowledgeTasksViewSerializer
from .serialisers import BulkDownloadSerializer
from .serialisers import BulkEditSerializer
from .serialisers import CorrespondentSerializer
from .serialisers import DocumentListSerializer
from .serialisers import DocumentSerializer
from .serialisers import DocumentTypeSerializer
from .serialisers import PostDocumentSerializer
from .serialisers import SavedViewSerializer
from .serialisers import StoragePathSerializer
from .serialisers import TagSerializer
from .serialisers import TagSerializerVersion1
from .serialisers import TasksViewSerializer
from .serialisers import UiSettingsViewSerializer

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
        context[
            "polyfills_js"
        ] = f"frontend/{self.get_frontend_language()}/polyfills.js"
        context["main_js"] = f"frontend/{self.get_frontend_language()}/main.js"
        context[
            "webmanifest"
        ] = f"frontend/{self.get_frontend_language()}/manifest.webmanifest"  # noqa: E501
        context[
            "apple_touch_icon"
        ] = f"frontend/{self.get_frontend_language()}/apple-touch-icon.png"  # noqa: E501
        return context


class CorrespondentViewSet(ModelViewSet):
    model = Correspondent

    queryset = Correspondent.objects.annotate(
        document_count=Count("documents"),
        last_correspondence=Max("documents__created"),
    ).order_by(Lower("name"))

    serializer_class = CorrespondentSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = CorrespondentFilterSet
    ordering_fields = (
        "name",
        "matching_algorithm",
        "match",
        "document_count",
        "last_correspondence",
    )


class TagViewSet(ModelViewSet):
    model = Tag

    queryset = Tag.objects.annotate(document_count=Count("documents")).order_by(
        Lower("name"),
    )

    def get_serializer_class(self):
        if int(self.request.version) == 1:
            return TagSerializerVersion1
        else:
            return TagSerializer

    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = TagFilterSet
    ordering_fields = ("name", "matching_algorithm", "match", "document_count")


class DocumentTypeViewSet(ModelViewSet):
    model = DocumentType

    queryset = DocumentType.objects.annotate(
        document_count=Count("documents"),
    ).order_by(Lower("name"))

    serializer_class = DocumentTypeSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = DocumentTypeFilterSet
    ordering_fields = ("name", "matching_algorithm", "match", "document_count")


class DocumentViewSet(
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    GenericViewSet,
):
    model = Document
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
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
    )

    def get_queryset(self):
        return Document.objects.distinct()

    def get_serializer(self, *args, **kwargs):
        fields_param = self.request.query_params.get("fields", None)
        if fields_param:
            fields = fields_param.split(",")
        else:
            fields = None
        serializer_class = self.get_serializer_class()
        kwargs.setdefault("context", self.get_serializer_context())
        kwargs.setdefault("fields", fields)
        return serializer_class(*args, **kwargs)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        from documents import index

        index.add_or_update_document(self.get_object())
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
        if not self.original_requested(request) and doc.has_archive_version:
            file_handle = doc.archive_file
            filename = doc.get_public_filename(archive=True)
            mime_type = "application/pdf"
        else:
            file_handle = doc.source_file
            filename = doc.get_public_filename()
            mime_type = doc.mime_type

        if doc.storage_type == Document.STORAGE_TYPE_GPG:
            file_handle = GnuPG.decrypted(file_handle)

        response = HttpResponse(file_handle, content_type=mime_type)
        # Firefox is not able to handle unicode characters in filename field
        # RFC 5987 addresses this issue
        # see https://datatracker.ietf.org/doc/html/rfc5987#section-4.2
        filename_normalized = normalize("NFKD", filename).encode("ascii", "ignore")
        filename_encoded = quote(filename)
        content_disposition = (
            f"{disposition}; "
            f'filename="{filename_normalized}"; '
            f"filename*=utf-8''{filename_encoded}"
        )
        response["Content-Disposition"] = content_disposition
        return response

    def get_metadata(self, file, mime_type):
        if not os.path.isfile(file):
            return None

        parser_class = get_parser_class_for_mime_type(mime_type)
        if parser_class:
            parser = parser_class(progress_callback=None, logging_group=None)

            try:
                return parser.extract_metadata(file, mime_type)
            except Exception:
                # TODO: cover GPG errors, remove later.
                return []
        else:
            return []

    def get_filesize(self, filename):
        if os.path.isfile(filename):
            return os.stat(filename).st_size
        else:
            return None

    @action(methods=["get"], detail=True)
    def metadata(self, request, pk=None):
        try:
            doc = Document.objects.get(pk=pk)
        except Document.DoesNotExist:
            raise Http404()

        meta = {
            "original_checksum": doc.checksum,
            "original_size": self.get_filesize(doc.source_path),
            "original_mime_type": doc.mime_type,
            "media_filename": doc.filename,
            "has_archive_version": doc.has_archive_version,
            "original_metadata": self.get_metadata(doc.source_path, doc.mime_type),
            "archive_checksum": doc.archive_checksum,
            "archive_media_filename": doc.archive_filename,
        }

        if doc.has_archive_version:
            meta["archive_size"] = self.get_filesize(doc.archive_path)
            meta["archive_metadata"] = self.get_metadata(
                doc.archive_path,
                "application/pdf",
            )
        else:
            meta["archive_size"] = None
            meta["archive_metadata"] = None

        return Response(meta)

    @action(methods=["get"], detail=True)
    def suggestions(self, request, pk=None):
        try:
            doc = Document.objects.get(pk=pk)
        except Document.DoesNotExist:
            raise Http404()

        classifier = load_classifier()

        return Response(
            {
                "correspondents": [c.id for c in match_correspondents(doc, classifier)],
                "tags": [t.id for t in match_tags(doc, classifier)],
                "document_types": [
                    dt.id for dt in match_document_types(doc, classifier)
                ],
                "storage_paths": [dt.id for dt in match_storage_paths(doc, classifier)],
            },
        )

    @action(methods=["get"], detail=True)
    def preview(self, request, pk=None):
        try:
            response = self.file_response(pk, request, "inline")
            return response
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404()

    @action(methods=["get"], detail=True)
    @method_decorator(cache_control(public=False, max_age=315360000))
    def thumb(self, request, pk=None):
        try:
            doc = Document.objects.get(id=pk)
            if doc.storage_type == Document.STORAGE_TYPE_GPG:
                handle = GnuPG.decrypted(doc.thumbnail_file)
            else:
                handle = doc.thumbnail_file
            # TODO: Send ETag information and use that to send new thumbnails
            #  if available

            return HttpResponse(handle, content_type="image/webp")
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404()

    @action(methods=["get"], detail=True)
    def download(self, request, pk=None):
        try:
            return self.file_response(pk, request, "attachment")
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404()


class SearchResultSerializer(DocumentSerializer):
    def to_representation(self, instance):
        doc = Document.objects.get(id=instance["id"])
        r = super().to_representation(doc)
        r["__search_hit__"] = {
            "score": instance.score,
            "highlights": instance.highlights("content", text=doc.content)
            if doc
            else None,
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
                raise ValueError()

            return query_class(
                self.searcher,
                self.request.query_params,
                self.paginator.get_page_size(self.request),
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
                return HttpResponseBadRequest(str(e))
        else:
            return super().list(request)


class LogViewSet(ViewSet):

    permission_classes = (IsAuthenticated,)

    log_files = ["paperless", "mail"]

    def retrieve(self, request, pk=None, *args, **kwargs):
        if pk not in self.log_files:
            raise Http404()

        filename = os.path.join(settings.LOGGING_DIR, f"{pk}.log")

        if not os.path.isfile(filename):
            raise Http404()

        with open(filename) as f:
            lines = [line.rstrip() for line in f.readlines()]

        return Response(lines)

    def list(self, request, *args, **kwargs):
        return Response(self.log_files)


class SavedViewViewSet(ModelViewSet):
    model = SavedView

    queryset = SavedView.objects.all()
    serializer_class = SavedViewSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return SavedView.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BulkEditView(GenericAPIView):

    permission_classes = (IsAuthenticated,)
    serializer_class = BulkEditSerializer
    parser_classes = (parsers.JSONParser,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        method = serializer.validated_data.get("method")
        parameters = serializer.validated_data.get("parameters")
        documents = serializer.validated_data.get("documents")

        try:
            # TODO: parameter validation
            result = method(documents, **parameters)
            return Response({"result": result})
        except Exception as e:
            return HttpResponseBadRequest(str(e))


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
        tag_ids = serializer.validated_data.get("tags")
        title = serializer.validated_data.get("title")
        created = serializer.validated_data.get("created")

        t = int(mktime(datetime.now().timetuple()))

        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            prefix="paperless-upload-",
            dir=settings.SCRATCH_DIR,
            delete=False,
        ) as f:
            f.write(doc_data)
            os.utime(f.name, times=(t, t))
            temp_filename = f.name

        task_id = str(uuid.uuid4())

        async_task(
            "documents.tasks.consume_file",
            temp_filename,
            override_filename=doc_name,
            override_title=title,
            override_correspondent_id=correspondent_id,
            override_document_type_id=document_type_id,
            override_tag_ids=tag_ids,
            task_id=task_id,
            task_name=os.path.basename(doc_name)[:100],
            override_created=created,
        )

        return Response("OK")


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

        return Response(index.autocomplete(ix, term, limit))


class StatisticsView(APIView):

    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        documents_total = Document.objects.all().count()
        if Tag.objects.filter(is_inbox_tag=True).exists():
            documents_inbox = (
                Document.objects.filter(tags__is_inbox_tag=True).distinct().count()
            )
        else:
            documents_inbox = None

        return Response(
            {
                "documents_total": documents_total,
                "documents_inbox": documents_inbox,
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

        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)
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
            strategy = strategy_class(zipf)
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


class RemoteVersionView(GenericAPIView):
    def get(self, request, format=None):
        remote_version = "0.0.0"
        is_greater_than_current = False
        current_version = packaging_version.parse(version.__full_version_str__)
        # TODO: this can likely be removed when frontend settings are saved to DB
        feature_is_set = settings.ENABLE_UPDATE_CHECK != "default"
        if feature_is_set and settings.ENABLE_UPDATE_CHECK:
            try:
                req = urllib.request.Request(
                    "https://api.github.com/repos/paperless-ngx/"
                    "paperless-ngx/releases/latest",
                )
                # Ensure a JSON response
                req.add_header("Accept", "application/json")

                with urllib.request.urlopen(req) as response:
                    remote = response.read().decode("utf-8")
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
                "feature_is_set": feature_is_set,
            },
        )


class StoragePathViewSet(ModelViewSet):
    model = StoragePath

    queryset = StoragePath.objects.annotate(document_count=Count("documents")).order_by(
        Lower("name"),
    )

    serializer_class = StoragePathSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = StoragePathFilterSet
    ordering_fields = ("name", "path", "matching_algorithm", "match", "document_count")


class UiSettingsView(GenericAPIView):

    permission_classes = (IsAuthenticated,)
    serializer_class = UiSettingsViewSerializer

    def get(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.get(pk=request.user.id)
        displayname = user.username
        if user.first_name or user.last_name:
            displayname = " ".join([user.first_name, user.last_name])
        settings = {}
        if hasattr(user, "ui_settings"):
            settings = user.ui_settings.settings
        return Response(
            {
                "user_id": user.id,
                "username": user.username,
                "display_name": displayname,
                "settings": settings,
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


class TasksViewSet(ReadOnlyModelViewSet):

    permission_classes = (IsAuthenticated,)
    serializer_class = TasksViewSerializer

    queryset = (
        PaperlessTask.objects.filter(
            acknowledged=False,
        )
        .order_by("created")
        .reverse()
    )


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
