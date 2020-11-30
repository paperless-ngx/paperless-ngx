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

    def file_response(self, pk, disposition):
        doc = Document.objects.get(id=pk)

        if doc.storage_type == Document.STORAGE_TYPE_UNENCRYPTED:
            file_handle = doc.source_file
        else:
            file_handle = GnuPG.decrypted(doc.source_file)

        response = HttpResponse(file_handle, content_type=doc.mime_type)
        response["Content-Disposition"] = '{}; filename="{}"'.format(
            disposition, doc.file_name)
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
            })
        except Document.DoesNotExist:
            raise Http404()

    @action(methods=['get'], detail=True)
    def preview(self, request, pk=None):
        try:
            response = self.file_response(pk, "inline")
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
            return self.file_response(pk, "attachment")
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
