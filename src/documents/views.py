import os

from django.db.models import Count, Max
from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.views.decorators.cache import cache_control
from django.views.generic import TemplateView
from django_filters.rest_framework import DjangoFilterBackend
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
from .forms import UploadForm
from .models import Correspondent, Document, Log, Tag, DocumentType
from .serialisers import (
    CorrespondentSerializer,
    DocumentSerializer,
    LogSerializer,
    TagSerializer,
    DocumentTypeSerializer
)


class IndexView(TemplateView):
    template_name = "index.html"


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
            filename = doc.archive_file_name
            mime_type = 'application/pdf'
        else:
            file_handle = doc.source_file
            filename = doc.file_name
            mime_type = doc.mime_type

        if doc.storage_type == Document.STORAGE_TYPE_GPG:
            file_handle = GnuPG.decrypted(file_handle)

        response = HttpResponse(file_handle, content_type=mime_type)
        response["Content-Disposition"] = '{}; filename="{}"'.format(
            disposition, filename)
        return response

    @action(methods=['post'], detail=False)
    def post_document(self, request, pk=None):
        # TODO: is this a good implementation?
        form = UploadForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            form.save()
            return Response("OK")
        else:
            return HttpResponseBadRequest(str(form.errors))

    @action(methods=['get'], detail=True)
    def metadata(self, request, pk=None):
        try:
            doc = Document.objects.get(pk=pk)
            return Response({
                "paperless__checksum": doc.checksum,
                "paperless__mime_type": doc.mime_type,
                "paperless__filename": doc.filename,
                "paperless__has_archive_version":
                    os.path.isfile(doc.archive_path)
            })
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
            return HttpResponse(Document.objects.get(id=pk).thumbnail_file,
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


class SearchView(APIView):

    permission_classes = (IsAuthenticated,)

    ix = index.open_index()

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
        if 'query' in request.query_params:
            query = request.query_params['query']
            try:
                page = int(request.query_params.get('page', 1))
            except (ValueError, TypeError):
                page = 1

            with index.query_page(self.ix, query, page) as result_page:
                return Response(
                    {'count': len(result_page),
                     'page': result_page.pagenum,
                     'page_count': result_page.pagecount,
                     'results': list(map(self.add_infos_to_hit, result_page))})

        else:
            return Response({
                'count': 0,
                'page': 0,
                'page_count': 0,
                'results': []})


class SearchAutoCompleteView(APIView):

    permission_classes = (IsAuthenticated,)

    ix = index.open_index()

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
