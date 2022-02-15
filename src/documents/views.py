import logging
import os
import tempfile
import uuid
import zipfile
from datetime import datetime
from time import mktime

from django.conf import settings
from django.db.models import Count, Max, Case, When, IntegerField
from django.db.models.functions import Lower
from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.utils.translation import get_language
from django.views.decorators.cache import cache_control
from django.views.generic import TemplateView
from django_filters.rest_framework import DjangoFilterBackend
from django_q.tasks import async_task
from rest_framework import parsers
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import (
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import (
    GenericViewSet,
    ModelViewSet,
    ViewSet
)

from paperless.db import GnuPG
from paperless.views import StandardPagination
from .bulk_download import OriginalAndArchiveStrategy, OriginalsOnlyStrategy, \
    ArchiveOnlyStrategy
from .classifier import load_classifier
from .filters import (
    CorrespondentFilterSet,
    DocumentFilterSet,
    TagFilterSet,
    DocumentTypeFilterSet
)
from .matching import match_correspondents, match_tags, match_document_types
from .models import Correspondent, Document, Tag, DocumentType, SavedView
from .parsers import get_parser_class_for_mime_type
from .serialisers import (
    CorrespondentSerializer,
    DocumentSerializer,
    TagSerializerVersion1,
    TagSerializer,
    DocumentTypeSerializer,
    PostDocumentSerializer,
    SavedViewSerializer,
    BulkEditSerializer,
    DocumentListSerializer,
    BulkDownloadSerializer
)


logger = logging.getLogger("paperless.api")


class IndexView(TemplateView):
    template_name = "index.html"

    def get_language(self):
        # This is here for the following reason:
        # Django identifies languages in the form "en-us"
        # However, angular generates locales as "en-US".
        # this translates between these two forms.
        lang = get_language()
        if "-" in lang:
            first = lang[:lang.index("-")]
            second = lang[lang.index("-")+1:]
            return f"{first}-{second.upper()}"
        else:
            return lang

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cookie_prefix'] = settings.COOKIE_PREFIX
        context['username'] = self.request.user.username
        context['full_name'] = self.request.user.get_full_name()
        context['styles_css'] = f"frontend/{self.get_language()}/styles.css"
        context['runtime_js'] = f"frontend/{self.get_language()}/runtime.js"
        context['polyfills_js'] = f"frontend/{self.get_language()}/polyfills.js"  # NOQA: E501
        context['main_js'] = f"frontend/{self.get_language()}/main.js"
        context['webmanifest'] = f"frontend/{self.get_language()}/manifest.webmanifest"  # NOQA: E501
        context['apple_touch_icon'] = f"frontend/{self.get_language()}/apple-touch-icon.png"  # NOQA: E501
        return context


class CorrespondentViewSet(ModelViewSet):
    model = Correspondent

    queryset = Correspondent.objects.annotate(
        document_count=Count('documents'),
        last_correspondence=Max('documents__created')).order_by(Lower('name'))

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
        "last_correspondence")


class TagViewSet(ModelViewSet):
    model = Tag

    queryset = Tag.objects.annotate(
        document_count=Count('documents')).order_by(Lower('name'))

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
        document_count=Count('documents')).order_by(Lower('name'))

    serializer_class = DocumentTypeSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = DocumentTypeFilterSet
    ordering_fields = ("name", "matching_algorithm", "match", "document_count")


class DocumentViewSet(RetrieveModelMixin,
                      UpdateModelMixin,
                      DestroyModelMixin,
                      ListModelMixin,
                      GenericViewSet):
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
        "archive_serial_number")

    def get_queryset(self):
        return Document.objects.distinct()

    def get_serializer(self, *args, **kwargs):
        fields_param = self.request.query_params.get('fields', None)
        if fields_param:
            fields = fields_param.split(",")
        else:
            fields = None
        serializer_class = self.get_serializer_class()
        kwargs.setdefault('context', self.get_serializer_context())
        kwargs.setdefault('fields', fields)
        return serializer_class(*args, **kwargs)

    def update(self, request, *args, **kwargs):
        response = super(DocumentViewSet, self).update(
            request, *args, **kwargs)
        from documents import index
        index.add_or_update_document(self.get_object())
        return response

    def destroy(self, request, *args, **kwargs):
        from documents import index
        index.remove_document_from_index(self.get_object())
        return super(DocumentViewSet, self).destroy(request, *args, **kwargs)

    @staticmethod
    def original_requested(request):
        return (
            'original' in request.query_params and
            request.query_params['original'] == 'true'
        )

    def file_response(self, pk, request, disposition):
        doc = Document.objects.get(id=pk)
        if not self.original_requested(request) and doc.has_archive_version:  # NOQA: E501
            file_handle = doc.archive_file
            filename = doc.get_public_filename(archive=True)
            mime_type = 'application/pdf'
        else:
            file_handle = doc.source_file
            filename = doc.get_public_filename()
            mime_type = doc.mime_type

        if doc.storage_type == Document.STORAGE_TYPE_GPG:
            file_handle = GnuPG.decrypted(file_handle)

        response = HttpResponse(file_handle, content_type=mime_type)
        response["Content-Disposition"] = '{}; filename="{}"'.format(
            disposition, filename)
        return response

    def get_metadata(self, file, mime_type):
        if not os.path.isfile(file):
            return None

        parser_class = get_parser_class_for_mime_type(mime_type)
        if parser_class:
            parser = parser_class(progress_callback=None, logging_group=None)

            try:
                return parser.extract_metadata(file, mime_type)
            except Exception as e:
                # TODO: cover GPG errors, remove later.
                return []
        else:
            return []

    def get_filesize(self, filename):
        if os.path.isfile(filename):
            return os.stat(filename).st_size
        else:
            return None

    @action(methods=['get'], detail=True)
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
            "original_metadata": self.get_metadata(
                doc.source_path, doc.mime_type),
            "archive_checksum": doc.archive_checksum,
            "archive_media_filename": doc.archive_filename
        }

        if doc.has_archive_version:
            meta['archive_size'] = self.get_filesize(doc.archive_path)
            meta['archive_metadata'] = self.get_metadata(
                doc.archive_path, "application/pdf")
        else:
            meta['archive_size'] = None
            meta['archive_metadata'] = None

        return Response(meta)

    @action(methods=['get'], detail=True)
    def suggestions(self, request, pk=None):
        try:
            doc = Document.objects.get(pk=pk)
        except Document.DoesNotExist:
            raise Http404()

        classifier = load_classifier()

        return Response({
            "correspondents": [
                c.id for c in match_correspondents(doc, classifier)
            ],
            "tags": [t.id for t in match_tags(doc, classifier)],
            "document_types": [
                dt.id for dt in match_document_types(doc, classifier)
            ]
        })

    @action(methods=['get'], detail=True)
    def preview(self, request, pk=None):
        try:
            response = self.file_response(
                pk, request, "inline")
            return response
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404()

    @action(methods=['get'], detail=True)
    @cache_control(public=False, max_age=315360000)
    def thumb(self, request, pk=None):
        try:
            doc = Document.objects.get(id=pk)
            if doc.storage_type == Document.STORAGE_TYPE_GPG:
                handle = GnuPG.decrypted(doc.thumbnail_file)
            else:
                handle = doc.thumbnail_file
            # TODO: Send ETag information and use that to send new thumbnails
            #  if available
            return HttpResponse(handle,
                                content_type='image/png')
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404()

    @action(methods=['get'], detail=True)
    def download(self, request, pk=None):
        try:
            return self.file_response(
                pk, request, "attachment")
        except (FileNotFoundError, Document.DoesNotExist):
            raise Http404()


class SearchResultSerializer(DocumentSerializer):

    def to_representation(self, instance):
        doc = Document.objects.get(id=instance['id'])
        r = super(SearchResultSerializer, self).to_representation(doc)
        r['__search_hit__'] = {
            "score": instance.score,
            "highlights": instance.highlights("content",
                                   text=doc.content) if doc else None,  # NOQA: E501
            "rank": instance.rank
        }

        return r


class UnifiedSearchViewSet(DocumentViewSet):

    def __init__(self, *args, **kwargs):
        super(UnifiedSearchViewSet, self).__init__(*args, **kwargs)
        self.searcher = None

    def get_serializer_class(self):
        if self._is_search_request():
            return SearchResultSerializer
        else:
            return DocumentSerializer

    def _is_search_request(self):
        return ("query" in self.request.query_params or
                "more_like_id" in self.request.query_params)

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
                self.paginator.get_page_size(self.request))
        else:
            return super(UnifiedSearchViewSet, self).filter_queryset(queryset)

    def list(self, request, *args, **kwargs):
        if self._is_search_request():
            from documents import index
            try:
                with index.open_index_searcher() as s:
                    self.searcher = s
                    return super(UnifiedSearchViewSet, self).list(request)
            except NotFound:
                raise
            except Exception as e:
                return HttpResponseBadRequest(str(e))
        else:
            return super(UnifiedSearchViewSet, self).list(request)


class LogViewSet(ViewSet):

    permission_classes = (IsAuthenticated,)

    log_files = ["paperless", "mail"]

    def retrieve(self, request, pk=None, *args, **kwargs):
        if pk not in self.log_files:
            raise Http404()

        filename = os.path.join(settings.LOGGING_DIR, f"{pk}.log")

        if not os.path.isfile(filename):
            raise Http404()

        with open(filename, "r") as f:
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

        doc_name, doc_data = serializer.validated_data.get('document')
        correspondent_id = serializer.validated_data.get('correspondent')
        document_type_id = serializer.validated_data.get('document_type')
        tag_ids = serializer.validated_data.get('tags')
        title = serializer.validated_data.get('title')

        t = int(mktime(datetime.now().timetuple()))

        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)

        with tempfile.NamedTemporaryFile(prefix="paperless-upload-",
                                         dir=settings.SCRATCH_DIR,
                                         delete=False) as f:
            f.write(doc_data)
            os.utime(f.name, times=(t, t))
            temp_filename = f.name

        task_id = str(uuid.uuid4())

        async_task("documents.tasks.consume_file",
                   temp_filename,
                   override_filename=doc_name,
                   override_title=title,
                   override_correspondent_id=correspondent_id,
                   override_document_type_id=document_type_id,
                   override_tag_ids=tag_ids,
                   task_id=task_id,
                   task_name=os.path.basename(doc_name)[:100])

        return Response("OK")


class SelectionDataView(GenericAPIView):

    permission_classes = (IsAuthenticated,)
    serializer_class = DocumentListSerializer
    parser_classes = (parsers.MultiPartParser, parsers.JSONParser)

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data.get('documents')

        correspondents = Correspondent.objects.annotate(
            document_count=Count(Case(
                When(documents__id__in=ids, then=1),
                output_field=IntegerField()
            )))

        tags = Tag.objects.annotate(document_count=Count(Case(
            When(documents__id__in=ids, then=1),
            output_field=IntegerField()
        )))

        types = DocumentType.objects.annotate(document_count=Count(Case(
            When(documents__id__in=ids, then=1),
            output_field=IntegerField()
        )))

        r = Response({
            "selected_correspondents": [{
                "id": t.id,
                "document_count": t.document_count
            } for t in correspondents],
            "selected_tags": [{
                "id": t.id,
                "document_count": t.document_count
            } for t in tags],
            "selected_document_types": [{
                "id": t.id,
                "document_count": t.document_count
            } for t in types]
        })

        return r


class SearchAutoCompleteView(APIView):

    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        if 'term' in request.query_params:
            term = request.query_params['term']
        else:
            return HttpResponseBadRequest("Term required")

        if 'limit' in request.query_params:
            limit = int(request.query_params['limit'])
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
            documents_inbox = Document.objects.filter(
                tags__is_inbox_tag=True).distinct().count()
        else:
            documents_inbox = None

        return Response({
            'documents_total': documents_total,
            'documents_inbox': documents_inbox,
        })


class BulkDownloadView(GenericAPIView):

    permission_classes = (IsAuthenticated,)
    serializer_class = BulkDownloadSerializer
    parser_classes = (parsers.JSONParser,)

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data.get('documents')
        compression = serializer.validated_data.get('compression')
        content = serializer.validated_data.get('content')

        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)
        temp = tempfile.NamedTemporaryFile(
            dir=settings.SCRATCH_DIR,
            suffix="-compressed-archive",
            delete=False)

        if content == 'both':
            strategy_class = OriginalAndArchiveStrategy
        elif content == 'originals':
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
                "attachment", "documents.zip")

            return response
