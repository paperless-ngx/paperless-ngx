from django.db.models import Count, Max
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.cache import cache_control
from django.views.generic import TemplateView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from paperless.db import GnuPG
from paperless.views import StandardPagination
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.mixins import (
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import (
    GenericViewSet,
    ModelViewSet,
    ReadOnlyModelViewSet
)

from .filters import (
    CorrespondentFilterSet,
    DocumentFilterSet,
    TagFilterSet,
    DocumentTypeFilterSet
)

import documents.index as index
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
    queryset = Correspondent.objects.annotate(document_count=Count('documents'), last_correspondence=Max('documents__created'))
    serializer_class = CorrespondentSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_class = CorrespondentFilterSet
    ordering_fields = ("name", "document_count", "last_correspondence")


class TagViewSet(ModelViewSet):
    model = Tag
    queryset = Tag.objects.annotate(document_count=Count('documents'))
    serializer_class = TagSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_class = TagFilterSet
    ordering_fields = ("name", "document_count")


class DocumentTypeViewSet(ModelViewSet):
    model = DocumentType
    queryset = DocumentType.objects.annotate(document_count=Count('documents'))
    serializer_class = DocumentTypeSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_class = DocumentTypeFilterSet
    ordering_fields = ("name", "document_count")


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
    filter_class = DocumentFilterSet
    search_fields = ("title", "correspondent__name", "content")
    ordering_fields = (
        "id", "title", "correspondent__name", "created", "modified", "added", "archive_serial_number")

    def file_response(self, pk, disposition):
        #TODO: this should not be necessary here.
        content_types = {
            Document.TYPE_PDF: "application/pdf",
            Document.TYPE_PNG: "image/png",
            Document.TYPE_JPG: "image/jpeg",
            Document.TYPE_GIF: "image/gif",
            Document.TYPE_TIF: "image/tiff",
            Document.TYPE_CSV: "text/csv",
            Document.TYPE_MD:  "text/markdown",
            Document.TYPE_TXT: "text/plain"
        }

        doc = Document.objects.get(id=pk)

        if doc.storage_type == Document.STORAGE_TYPE_UNENCRYPTED:
            file_handle = doc.source_file
        else:
            file_handle = GnuPG.decrypted(doc.source_file)

        response = HttpResponse(file_handle, content_type=content_types[doc.file_type])
        response["Content-Disposition"] = '{}; filename="{}"'.format(
            disposition, doc.file_name)
        return response

    @action(methods=['post'], detail=False)
    def post_document(self, request, pk=None):
        #TODO: is this a good implementation?
        form = UploadForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            form.save()
            return Response("OK")
        else:
            return HttpResponseBadRequest(str(form.errors))

    @action(methods=['get'], detail=True)
    def preview(self, request, pk=None):
        response = self.file_response(pk, "inline")
        return response

    @action(methods=['get'], detail=True)
    @cache_control(public=False, max_age=315360000)
    def thumb(self, request, pk=None):
        return HttpResponse(Document.objects.get(id=pk).thumbnail_file, content_type='image/png')

    @action(methods=['get'], detail=True)
    def download(self, request, pk=None):
        return self.file_response(pk, "attachment")


class LogViewSet(ReadOnlyModelViewSet):
    model = Log
    queryset = Log.objects.all().by_group()
    serializer_class = LogSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    ordering_fields = ("time",)


class SearchView(APIView):

    permission_classes = (IsAuthenticated,)

    ix = index.open_index()

    def get(self, request, format=None):
        if 'query' in request.query_params:
            query = request.query_params['query']
            query_results = index.query_index(self.ix, query)
            for r in query_results:
                r['document'] = DocumentSerializer(Document.objects.get(id=r['id'])).data

            return Response(query_results)
        else:
            return Response([])


class SearchAutoCompleteView(APIView):

    permission_classes = (IsAuthenticated,)

    ix = index.open_index()

    def get(self, request, format=None):
        if 'term' in request.query_params:
            term = request.query_params['term']
        else:
            term = None

        if 'limit' in request.query_params:
            limit = int(request.query_params['limit'])
        else:
            limit = 10

        if term is not None:
            return Response(index.autocomplete(self.ix, term, limit))
        else:
            return Response([])


class StatisticsView(APIView):

    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        return Response({
            'documents_total': Document.objects.all().count(),
            'documents_inbox': Document.objects.filter(tags__is_inbox_tag=True).distinct().count()
        })
