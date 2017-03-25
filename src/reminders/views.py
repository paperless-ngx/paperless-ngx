from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import (
    ModelViewSet,
)

from .filters import ReminderFilterSet
from .models import Reminder
from .serialisers import ReminderSerializer
from paperless.views import StandardPagination


class ReminderViewSet(ModelViewSet):
    model = Reminder
    queryset = Reminder.objects
    serializer_class = ReminderSerializer
    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_class = ReminderFilterSet
    ordering_fields = ("date", "document")
