from http import HTTPStatus
from pathlib import Path

from django.conf import settings
from django.db.models import Max
from django.db.models.functions import Lower
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from documents import bulk_edit
from documents.file_handling import format_filename
from documents.filters import CorrespondentFilterSet
from documents.filters import CustomFieldFilterSet
from documents.filters import DocumentTypeFilterSet
from documents.filters import PermittedObjectsFilter
from documents.filters import StoragePathFilterSet
from documents.filters import TagFilterSet
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import PaperlessTask
from documents.models import StoragePath
from documents.models import Tag
from documents.permissions import PaperlessObjectPermissions
from documents.permissions import ViewDocumentsPermissions
from documents.permissions import annotate_document_count_for_related_queryset
from documents.permissions import permitted_object_ids
from documents.schema import generate_object_with_permissions_schema
from documents.serialisers.metadata import CorrespondentSerializer
from documents.serialisers.metadata import CustomFieldSerializer
from documents.serialisers.metadata import DocumentTypeSerializer
from documents.serialisers.metadata import StoragePathSerializer
from documents.serialisers.metadata import StoragePathTestSerializer
from documents.serialisers.metadata import TagSerializer
from documents.tasks import update_document_parent_tags
from paperless.views import StandardPagination

from .base import PermissionsAwareDocumentCountMixin


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
        PermittedObjectsFilter,
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
                last_correspondence=Max(
                    "documents__created",
                    filter=self.get_document_count_filter(),
                ),
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        self.queryset = self.queryset.annotate(
            last_correspondence=Max(
                "documents__created",
                filter=self.get_document_count_filter(),
            ),
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
        PermittedObjectsFilter,
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
                    )
                    .filter(pk__in=permitted_object_ids(user, Tag, "view_tag"))
                    .select_related("owner"),
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
        PermittedObjectsFilter,
    )
    filterset_class = DocumentTypeFilterSet
    ordering_fields = ("name", "matching_algorithm", "match", "document_count")


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
        PermittedObjectsFilter,
    )
    filterset_class = StoragePathFilterSet
    ordering_fields = ("name", "path", "matching_algorithm", "match", "document_count")

    def get_permissions(self):
        if self.action == "test":
            # Test action does not require object level permissions
            self.permission_classes = (IsAuthenticated, ViewDocumentsPermissions)
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
