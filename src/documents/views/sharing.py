from http import HTTPStatus
from unicodedata import normalize
from urllib.parse import quote

from django.db.models import Count
from django.http import FileResponse
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.viewsets import ModelViewSet

from documents.filters import PermittedObjectsFilter
from documents.filters import ShareLinkBundleFilterSet
from documents.filters import ShareLinkFilterSet
from documents.models import Document
from documents.models import PaperlessTask
from documents.models import ShareLink
from documents.models import ShareLinkBundle
from documents.permissions import PaperlessObjectPermissions
from documents.permissions import ViewDocumentsPermissions
from documents.permissions import permitted_document_ids
from documents.serialisers.sharing import ShareLinkBundleSerializer
from documents.serialisers.sharing import ShareLinkSerializer
from documents.tasks import build_share_link_bundle
from paperless.views import StandardPagination

from .base import PassUserMixin
from .base import serve_file


class ShareLinkViewSet(
    PassUserMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    GenericViewSet,
):
    model = ShareLink

    queryset = ShareLink.objects.select_related("document")

    serializer_class = ShareLinkSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        PermittedObjectsFilter,
    )
    filterset_class = ShareLinkFilterSet
    ordering_fields = ("created", "expiration", "document__title")


@extend_schema_view(
    rebuild=extend_schema(
        operation_id="share_link_bundles_rebuild",
        description="Reset and re-queue a share link bundle for processing.",
        responses={
            HTTPStatus.OK: ShareLinkBundleSerializer,
            (HTTPStatus.BAD_REQUEST, "application/json"): inline_serializer(
                name="RebuildBundleError",
                fields={"detail": serializers.CharField()},
            ),
        },
    ),
)
class ShareLinkBundleViewSet(PassUserMixin, ModelViewSet[ShareLinkBundle]):
    model = ShareLinkBundle

    # Bundles are immutable once created; rebuild via the dedicated action
    # rather than PUT/PATCH.
    http_method_names = ["get", "post", "delete", "head", "options"]

    queryset = ShareLinkBundle.objects.all()

    serializer_class = ShareLinkBundleSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        PermittedObjectsFilter,
    )
    filterset_class = ShareLinkBundleFilterSet
    ordering_fields = ("created", "expiration", "status")

    def get_permissions(self):
        permissions = super().get_permissions()
        if self.action == "create":
            permissions.append(ViewDocumentsPermissions())
        return permissions

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
        permitted_ids = set(permitted_document_ids(request.user))
        for document in documents:
            if document.pk not in permitted_ids:
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
        build_share_link_bundle.apply_async(
            kwargs={"bundle_id": bundle.pk},
            headers={"trigger_source": PaperlessTask.TriggerSource.MANUAL},
        )
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
        build_share_link_bundle.apply_async(
            kwargs={"bundle_id": bundle.pk},
            headers={"trigger_source": PaperlessTask.TriggerSource.MANUAL},
        )
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
            try:
                return serve_file(
                    doc=share_link.document,
                    use_archive=share_link.file_version == ShareLink.FileVersion.ARCHIVE
                    and share_link.document.has_archive_version,
                    disposition="inline",
                )
            except FileNotFoundError:
                return HttpResponseRedirect("/accounts/login/?sharelink_notfound=1")

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

        if (
            bundle.status == ShareLinkBundle.Status.FAILED
            or file_path is None
            or not file_path.exists()
        ):
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
