import logging
from datetime import timedelta

from django.db.models import Avg
from django.db.models import Count
from django.db.models import Max
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.http import HttpResponseServerError
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from documents.filters import PaperlessTaskFilterSet
from documents.models import PaperlessTask
from documents.permissions import AcknowledgeTasksPermissions
from documents.permissions import PaperlessObjectPermissions
from documents.permissions import has_system_status_permission
from documents.serialisers.tasks import AcknowledgeTasksViewSerializer
from documents.serialisers.tasks import RunTaskSerializer
from documents.serialisers.tasks import TaskSerializerV9
from documents.serialisers.tasks import TaskSerializerV10
from documents.serialisers.tasks import TaskSummarySerializer
from documents.tasks import llmindex_index
from documents.tasks import sanity_check
from documents.tasks import train_classifier
from paperless.views import StandardPagination

logger = logging.getLogger("paperless.api")


class _TasksViewSetSchema(AutoSchema):
    _UNPAGINATED_ACTIONS = frozenset({"summary", "active", "status_counts"})

    def _get_paginator(self):
        if getattr(self.view, "action", None) in self._UNPAGINATED_ACTIONS:
            return None
        return super()._get_paginator()


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="task_id",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter tasks by Celery UUID",
            ),
        ],
    ),
    acknowledge=extend_schema(
        operation_id="acknowledge_tasks",
        description="Acknowledge a list of tasks, or all visible unacknowledged tasks",
        request=AcknowledgeTasksViewSerializer,
        responses={
            (200, "application/json"): inline_serializer(
                name="AcknowledgeTasks",
                fields={
                    "result": serializers.IntegerField(),
                },
            ),
        },
    ),
    run=extend_schema(
        operation_id="run_task",
        description="Manually dispatch a background task. Superuser only.",
        request=RunTaskSerializer,
        responses={
            (200, "application/json"): inline_serializer(
                name="RunTask",
                fields={"task_id": serializers.CharField()},
            ),
            (400, "application/json"): inline_serializer(
                name="RunTaskError",
                fields={"error": serializers.CharField()},
            ),
        },
    ),
    summary=extend_schema(
        responses={200: TaskSummarySerializer(many=True)},
        parameters=[
            OpenApiParameter(
                name="days",
                type={"type": "integer", "minimum": 1, "maximum": 365, "default": 30},
                location=OpenApiParameter.QUERY,
                required=False,
                description="Number of days to include in aggregation (default 30, min 1, max 365)",
            ),
        ],
    ),
    status_counts=extend_schema(
        responses={
            200: inline_serializer(
                name="TaskStatusCounts",
                fields={
                    "all": serializers.IntegerField(),
                    "needs_attention": serializers.IntegerField(),
                    "in_progress": serializers.IntegerField(),
                    "completed": serializers.IntegerField(),
                },
            ),
        },
    ),
    active=extend_schema(
        description="Currently pending and running tasks (capped at 50).",
        responses={200: TaskSerializerV10(many=True)},
    ),
)
class TasksViewSet(ReadOnlyModelViewSet[PaperlessTask]):
    schema = _TasksViewSetSchema()
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    pagination_class = StandardPagination
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )
    filterset_class = PaperlessTaskFilterSet
    ordering_fields = [
        "date_created",
        "date_done",
        "status",
        "task_type",
        "duration_seconds",
        "wait_time_seconds",
    ]
    ordering = ["-date_created"]
    # Needed for drf-spectacular schema generation (get_queryset touches request.user)
    queryset = PaperlessTask.objects.none()

    # v9 backwards compat: maps old task_name values to new task_type values
    _V9_TASK_NAME_TO_TYPE = {
        "check_sanity": PaperlessTask.TaskType.SANITY_CHECK,
        "llmindex_update": PaperlessTask.TaskType.LLM_INDEX,
    }

    # v9 backwards compat: maps old "type" query param values to new TriggerSource.
    # Must match the reverse of TaskSerializerV9._TRIGGER_SOURCE_TO_V9_TYPE.
    _V9_TYPE_TO_TRIGGER_SOURCES = {
        "auto_task": [
            PaperlessTask.TriggerSource.SYSTEM,
            PaperlessTask.TriggerSource.EMAIL_CONSUME,
            PaperlessTask.TriggerSource.FOLDER_CONSUME,
        ],
        "scheduled_task": [PaperlessTask.TriggerSource.SCHEDULED],
        "manual_task": [
            PaperlessTask.TriggerSource.MANUAL,
            PaperlessTask.TriggerSource.WEB_UI,
            PaperlessTask.TriggerSource.API_UPLOAD,
        ],
    }

    _RUNNABLE_TASKS = {
        PaperlessTask.TaskType.TRAIN_CLASSIFIER: (train_classifier, {}),
        PaperlessTask.TaskType.SANITY_CHECK: (sanity_check, {"raise_on_error": False}),
        PaperlessTask.TaskType.LLM_INDEX: (llmindex_index, {"rebuild": False}),
    }
    _STATUS_COUNT_EXCLUDED_FILTERS = frozenset({"status", "is_complete"})

    def get_serializer_class(self):
        # v9: use backwards-compatible serializer with old field names
        if self.request.version and int(self.request.version) < 10:
            return TaskSerializerV9
        return TaskSerializerV10

    def paginate_queryset(self, queryset):
        # v9: tasks endpoint was not paginated; preserve plain-list response
        if self.request.version and int(self.request.version) < 10:
            return None
        return super().paginate_queryset(queryset)

    def get_queryset(self):
        is_v9 = self.request.version and int(self.request.version) < 10
        if self.request.user.is_staff:
            queryset = PaperlessTask.objects.all()
        else:
            # Own tasks + unowned (system/scheduled) tasks. Tasks owned by other
            # users are never visible to non-staff regardless of API version.
            queryset = PaperlessTask.objects.filter(
                Q(owner=self.request.user) | Q(owner__isnull=True),
            )
        # v9 backwards compat: map old query params to new field names
        if is_v9:
            task_name = self.request.query_params.get("task_name")
            if task_name is not None:
                mapped = self._V9_TASK_NAME_TO_TYPE.get(task_name, task_name)
                queryset = queryset.filter(task_type=mapped)
            task_type_old = self.request.query_params.get("type")
            if task_type_old is not None:
                sources = self._V9_TYPE_TO_TRIGGER_SOURCES.get(task_type_old)
                if sources:
                    queryset = queryset.filter(trigger_source__in=sources)
        # v10+: direct task_id param for backwards compat
        task_id = self.request.query_params.get("task_id")
        if task_id is not None:
            queryset = queryset.filter(task_id=task_id)
        return queryset

    def get_status_count_queryset(self):
        """Apply task filters except the status dimensions represented by the counts."""
        query_params = self.request.query_params.copy()
        for param in self._STATUS_COUNT_EXCLUDED_FILTERS:
            query_params.pop(param, None)

        filterset = self.filterset_class(
            data=query_params,
            queryset=self.get_queryset(),
            request=self.request,
        )
        if not filterset.is_valid():
            raise ValidationError(filterset.errors)
        return filterset.qs

    @action(
        methods=["post"],
        detail=False,
        permission_classes=[IsAuthenticated, AcknowledgeTasksPermissions],
    )
    def acknowledge(self, request):
        queryset = self.get_queryset()
        serializer = AcknowledgeTasksViewSerializer(
            data=request.data,
            context={"queryset": queryset},
        )
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("all", False):
            tasks = queryset.filter(acknowledged=False)
        else:
            task_ids = serializer.validated_data.get("tasks")
            tasks = queryset.filter(id__in=task_ids)
        count = tasks.update(acknowledged=True)
        return Response({"result": count})

    def get_permissions(self):
        if self.action == "summary" and has_system_status_permission(
            getattr(self.request, "user", None),
        ):
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(methods=["get"], detail=False)
    def summary(self, request):
        """Aggregated task statistics per task_type over the last N days (default 30)."""
        try:
            days = min(365, max(1, int(request.query_params.get("days", 30))))
        except (TypeError, ValueError):
            return Response(
                {"days": "Must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cutoff = timezone.now() - timedelta(days=days)
        if has_system_status_permission(request.user):
            queryset = PaperlessTask.objects.filter(date_created__gte=cutoff)
        else:
            queryset = self.get_queryset().filter(date_created__gte=cutoff)

        data = queryset.values("task_type").annotate(
            total_count=Count("id"),
            pending_count=Count("id", filter=Q(status=PaperlessTask.Status.PENDING)),
            success_count=Count("id", filter=Q(status=PaperlessTask.Status.SUCCESS)),
            failure_count=Count("id", filter=Q(status=PaperlessTask.Status.FAILURE)),
            avg_duration_seconds=Avg(
                "duration_seconds",
                filter=Q(duration_seconds__isnull=False),
            ),
            avg_wait_time_seconds=Avg(
                "wait_time_seconds",
                filter=Q(wait_time_seconds__isnull=False),
            ),
            last_run=Max("date_created"),
            last_success=Max(
                "date_done",
                filter=Q(status=PaperlessTask.Status.SUCCESS),
            ),
            last_failure=Max(
                "date_done",
                filter=Q(status=PaperlessTask.Status.FAILURE),
            ),
        )
        serializer = TaskSummarySerializer(data, many=True)
        return Response(serializer.data)

    @action(methods=["get"], detail=False)
    def status_counts(self, request):
        """Aggregated task counts for task UI sections."""
        queryset = self.get_status_count_queryset()
        counts = queryset.aggregate(
            all=Count("id"),
            needs_attention=Count(
                "id",
                filter=Q(
                    status__in=[
                        PaperlessTask.Status.FAILURE,
                        PaperlessTask.Status.REVOKED,
                    ],
                ),
            ),
            in_progress=Count(
                "id",
                filter=Q(
                    status__in=[
                        PaperlessTask.Status.PENDING,
                        PaperlessTask.Status.STARTED,
                    ],
                ),
            ),
            completed=Count("id", filter=Q(status=PaperlessTask.Status.SUCCESS)),
        )
        return Response(counts)

    @action(methods=["get"], detail=False)
    def active(self, request):
        """Currently pending and running tasks (capped at 50)."""
        queryset = (
            self.get_queryset()
            .filter(
                status__in=[PaperlessTask.Status.PENDING, PaperlessTask.Status.STARTED],
            )
            .order_by("-date_created")[:50]
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=["post"], detail=False)
    def run(self, request):
        """Manually dispatch a background task. Superuser only."""
        if not request.user.is_superuser:
            return HttpResponseForbidden("Insufficient permissions")
        serializer = RunTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task_type = serializer.validated_data.get("task_type")

        if task_type not in self._RUNNABLE_TASKS:
            return Response(
                {"error": f"Task type '{task_type}' cannot be manually triggered"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task_func, task_kwargs = self._RUNNABLE_TASKS[task_type]
            async_result = task_func.apply_async(
                kwargs=task_kwargs,
                headers={"trigger_source": PaperlessTask.TriggerSource.MANUAL},
            )
            return Response({"task_id": async_result.id})
        except Exception as e:
            logger.warning(f"Error running task: {e!s}")
            return HttpResponseServerError(
                "Error running task, check logs for more detail.",
            )
