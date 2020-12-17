import os
import tempfile
from datetime import datetime
from time import mktime

from django.conf import settings
from django.db.models import Count, Max
from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.views.decorators.cache import cache_control
from django.views.generic import TemplateView
from django_filters.rest_framework import DjangoFilterBackend
from django_q.tasks import async_task
from rest_framework import parsers
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
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
    ReadOnlyModelViewSet
)

import documents.index as index
from paperless.db import GnuPG
from paperless.views import StandardPagination
from .filters import (
    CorrespondentFilterSet,
    DocumentFilterSet,
    TagFilterSet,
    DocumentTypeFilterSet,
    LogFilterSet
)
from .models import Correspondent, Document, Log, Tag, DocumentType, SavedView
from .parsers import get_parser_class_for_mime_type
from .serialisers import (
    CorrespondentSerializer,
    DocumentSerializer,
    LogSerializer,
    TagSerializer,
    DocumentTypeSerializer,
    PostDocumentSerializer,
    SavedViewSerializer
)


class IndexView(TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cookie_prefix'] = settings.COOKIE_PREFIX
        return context


class CorrespondentViewSet(ModelViewSet):
    model = Correspondent

    queryset = Correspondent.objects.annotate(
        document_count=Count('documents'),
        last_correspondence=Max('documents__created')).order_by('name')

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
        document_count=Count('documents')).order_by('name')

    serializer_class = TagSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = TagFilterSet
    ordering_fields = ("name", "matching_algorithm", "match", "document_count")


class DocumentTypeViewSet(ModelViewSet):
    model = DocumentType

    queryset = DocumentType.objects.annotate(
        document_count=Count('documents')).order_by('name')

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

    def update(self, request, *args, **kwargs):
        response = super(DocumentViewSet, self).update(
            request, *args, **kwargs)
        index.add_or_update_document(self.get_object())
        return response

    def destroy(self, request, *args, **kwargs):
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
        if not self.original_requested(request) and os.path.isfile(doc.archive_path):  # NOQA: E501
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
            parser = parser_class(logging_group=None)

            try:
                return parser.extract_metadata(file, mime_type)
            except Exception as e:
                # TODO: cover GPG errors, remove later.
                return []
        else:
            return []

    @action(methods=['get'], detail=True)
    def metadata(self, request, pk=None):
        try:
            doc = Document.objects.get(pk=pk)

            meta = {
                "original_checksum": doc.checksum,
                "original_size": os.stat(doc.source_path).st_size,
                "original_mime_type": doc.mime_type,
                "media_filename": doc.filename,
                "has_archive_version": os.path.isfile(doc.archive_path),
                "original_metadata": self.get_metadata(
                    doc.source_path, doc.mime_type)
            }

            if doc.archive_checksum and os.path.isfile(doc.archive_path):
                meta['archive_checksum'] = doc.archive_checksum
                meta['archive_size'] = os.stat(doc.archive_path).st_size,
                meta['archive_metadata'] = self.get_metadata(
                    doc.archive_path, "application/pdf")
            else:
                meta['archive_checksum'] = None
                meta['archive_size'] = None
                meta['archive_metadata'] = None

            return Response(meta)
        except Document.DoesNotExist:
            raise Http404()

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


class LogViewSet(ReadOnlyModelViewSet):
    model = Log

    queryset = Log.objects.all()
    serializer_class = LogSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = LogFilterSet
    ordering_fields = ("created",)


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


class PostDocumentView(APIView):

    permission_classes = (IsAuthenticated,)
    serializer_class = PostDocumentSerializer
    parser_classes = (parsers.MultiPartParser,)

    def get_serializer_context(self):
        return {
            'request': self.request,
            'format': self.format_kwarg,
            'view': self
        }

    def get_serializer(self, *args, **kwargs):
        kwargs['context'] = self.get_serializer_context()
        return self.serializer_class(*args, **kwargs)

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

            async_task("documents.tasks.consume_file",
                       f.name,
                       override_filename=doc_name,
                       override_title=title,
                       override_correspondent_id=correspondent_id,
                       override_document_type_id=document_type_id,
                       override_tag_ids=tag_ids,
                       task_name=os.path.basename(doc_name)[:100])
        return Response("OK")


class SearchView(APIView):

    permission_classes = (IsAuthenticated,)

    def __init__(self, *args, **kwargs):
        super(SearchView, self).__init__(*args, **kwargs)
        self.ix = index.open_index()

    def add_infos_to_hit(self, r):
        doc = Document.objects.get(id=r['id'])
        return {'id': r['id'],
                'highlights': r.highlights("content", text=doc.content),
                'score': r.score,
                'rank': r.rank,
                'document': DocumentSerializer(doc).data,
                'title': r['title']
                }

    def get(self, request, format=None):
        if 'query' not in request.query_params:
            return Response({
                'count': 0,
                'page': 0,
                'page_count': 0,
                'results': []})

        query = request.query_params['query']
        try:
            page = int(request.query_params.get('page', 1))
        except (ValueError, TypeError):
            page = 1

        if page < 1:
            page = 1

        try:
            with index.query_page(self.ix, query, page) as (result_page,
                                                            corrected_query):
                return Response(
                    {'count': len(result_page),
                     'page': result_page.pagenum,
                     'page_count': result_page.pagecount,
                     'corrected_query': corrected_query,
                     'results': list(map(self.add_infos_to_hit, result_page))})
        except Exception as e:
            return HttpResponseBadRequest(str(e))


class SearchAutoCompleteView(APIView):

    permission_classes = (IsAuthenticated,)

    def __init__(self, *args, **kwargs):
        super(SearchAutoCompleteView, self).__init__(*args, **kwargs)
        self.ix = index.open_index()

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

        return Response(index.autocomplete(self.ix, term, limit))


class StatisticsView(APIView):

    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        return Response({
            'documents_total': Document.objects.all().count(),
            'documents_inbox': Document.objects.filter(
                tags__is_inbox_tag=True).distinct().count()
        })
