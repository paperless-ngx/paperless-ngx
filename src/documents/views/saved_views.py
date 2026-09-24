from drf_spectacular.utils import extend_schema_view
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from documents.filters import PermittedObjectsFilter
from documents.models import SavedView
from documents.permissions import PaperlessObjectPermissions
from documents.schema import generate_object_with_permissions_schema
from documents.serialisers.saved_views import SavedViewSerializer
from paperless.views import StandardPagination

from .base import BulkPermissionMixin
from .base import PassUserMixin


@extend_schema_view(**generate_object_with_permissions_schema(SavedViewSerializer))
class SavedViewViewSet(BulkPermissionMixin, PassUserMixin, ModelViewSet[SavedView]):
    model = SavedView

    queryset = SavedView.objects.select_related("owner").prefetch_related(
        "filter_rules",
    )
    serializer_class = SavedViewSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    filter_backends = (
        OrderingFilter,
        PermittedObjectsFilter,
    )
    ordering_fields = ("name",)
