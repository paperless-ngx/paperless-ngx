from collections import deque
from pathlib import Path

from django.conf import settings
from django.http import Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from documents.permissions import PaperlessAdminPermissions


@extend_schema_view(
    list=extend_schema(
        description="Logs view",
        responses={
            (200, "application/json"): serializers.ListSerializer(
                child=serializers.CharField(),
            ),
        },
    ),
    retrieve=extend_schema(
        description="Single log view",
        operation_id="retrieve_log",
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Return only the last N entries from the log file",
                required=False,
            ),
        ],
        responses={
            (200, "application/json"): serializers.ListSerializer(
                child=serializers.CharField(),
            ),
            (404, "application/json"): None,
        },
    ),
)
class LogViewSet(ViewSet):
    permission_classes = (IsAuthenticated, PaperlessAdminPermissions)

    ALLOWED_LOG_FILES = {
        "paperless": "paperless.log",
        "mail": "mail.log",
        "celery": "celery.log",
    }

    def get_log_file(self, log_key: str) -> Path:
        return Path(settings.LOGGING_DIR) / self.ALLOWED_LOG_FILES[log_key]

    def retrieve(self, request, *args, **kwargs):
        log_key = kwargs.get("pk")
        if log_key not in self.ALLOWED_LOG_FILES:
            raise Http404

        log_file = self.get_log_file(log_key)

        if not log_file.is_file():
            raise Http404

        limit_param = request.query_params.get("limit")
        if limit_param is not None:
            try:
                limit = int(limit_param)
            except (TypeError, ValueError):
                raise ValidationError({"limit": "Must be a positive integer"})
            if limit < 1:
                raise ValidationError({"limit": "Must be a positive integer"})
        else:
            limit = None

        with log_file.open() as f:
            if limit is None:
                lines = [line.rstrip() for line in f.readlines()]
            else:
                lines = [line.rstrip() for line in deque(f, maxlen=limit)]

        return Response(lines)

    def list(self, request, *args, **kwargs):
        existing_logs = [
            log_key
            for log_key in self.ALLOWED_LOG_FILES
            if self.get_log_file(log_key).is_file()
        ]
        return Response(existing_logs)
