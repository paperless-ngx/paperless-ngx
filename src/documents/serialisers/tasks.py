from __future__ import annotations

import logging
from typing import Any

from rest_framework import serializers

from documents.models import Document
from documents.models import PaperlessTask
from documents.permissions import permitted_document_ids

from .base import OwnedObjectSerializer

logger = logging.getLogger("paperless.serializers")


class TaskSerializerV10(OwnedObjectSerializer):
    """Task serializer for API v10+ using new field names."""

    related_document_ids = serializers.ListField(
        child=serializers.IntegerField(),
        read_only=True,
    )
    task_type_display = serializers.CharField(
        source="get_task_type_display",
        read_only=True,
    )
    trigger_source_display = serializers.CharField(
        source="get_trigger_source_display",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = PaperlessTask
        fields = (
            "id",
            "task_id",
            "task_type",
            "task_type_display",
            "trigger_source",
            "trigger_source_display",
            "status",
            "status_display",
            "date_created",
            "date_started",
            "date_done",
            "duration_seconds",
            "wait_time_seconds",
            "input_data",
            "result_data",
            "related_document_ids",
            "acknowledged",
            "owner",
        )
        read_only_fields = fields


class TaskSerializerV9(serializers.ModelSerializer[PaperlessTask]):
    """Task serializer for API v9 backwards compatibility.

    Maps old field names to the new model fields so existing clients continue
    to work unchanged.
    """

    # v9 field: task_name -> task_type (with value remapping for renamed tasks)
    task_name = serializers.SerializerMethodField()

    # v9 field: task_file_name -> input_data.filename
    task_file_name = serializers.SerializerMethodField()

    # v9 field: type -> trigger_source (mapped to old enum labels)
    type = serializers.SerializerMethodField()

    # v9 field: status -> uppercase Celery state strings
    status = serializers.SerializerMethodField()

    # v9 field: result -> derived from result_data
    result = serializers.SerializerMethodField()

    # v9 field: related_document -> first document ID from result_data
    related_document = serializers.SerializerMethodField()

    # v9 field: duplicate_documents -> list of duplicate IDs from result_data
    duplicate_documents = serializers.SerializerMethodField()

    class Meta:
        model = PaperlessTask
        fields = (
            "id",
            "task_id",
            "task_name",
            "task_file_name",
            "type",
            "status",
            "date_created",
            "date_done",
            "result",
            "acknowledged",
            "related_document",
            "duplicate_documents",
            "owner",
        )
        read_only_fields = fields

    _TASK_TYPE_TO_V9_NAME = {
        PaperlessTask.TaskType.SANITY_CHECK: "check_sanity",
        PaperlessTask.TaskType.LLM_INDEX: "llmindex_update",
    }

    def get_result(self, obj: PaperlessTask) -> str | None:
        """Reconstruct a human-readable result string from result_data for v9 clients."""
        if not obj.result_data:
            return None
        if doc_id := obj.result_data.get("document_id"):
            return f"Success. New document id {doc_id} created"
        if reason := obj.result_data.get("reason"):
            return reason
        if dup_id := obj.result_data.get("duplicate_of"):
            return f"Not consuming: It is a duplicate of document #{dup_id}"
        if error := obj.result_data.get("error_message"):
            return error
        return None

    def get_task_name(self, obj: PaperlessTask) -> str:
        return self._TASK_TYPE_TO_V9_NAME.get(obj.task_type, obj.task_type)

    def get_task_file_name(self, obj: PaperlessTask) -> str | None:
        if not obj.input_data:
            return None
        return obj.input_data.get("filename")

    _STATUS_TO_V9 = {
        PaperlessTask.Status.PENDING: "PENDING",
        PaperlessTask.Status.STARTED: "STARTED",
        PaperlessTask.Status.SUCCESS: "SUCCESS",
        PaperlessTask.Status.FAILURE: "FAILURE",
        PaperlessTask.Status.REVOKED: "REVOKED",
    }

    def get_status(self, obj: PaperlessTask) -> str:
        return self._STATUS_TO_V9.get(obj.status, obj.status.upper())

    _TRIGGER_SOURCE_TO_V9_TYPE = {
        PaperlessTask.TriggerSource.SCHEDULED: "scheduled_task",
        PaperlessTask.TriggerSource.SYSTEM: "auto_task",
        # Email and folder-consumer documents are system-initiated, not manually triggered
        PaperlessTask.TriggerSource.EMAIL_CONSUME: "auto_task",
        PaperlessTask.TriggerSource.FOLDER_CONSUME: "auto_task",
    }

    def get_type(self, obj: PaperlessTask) -> str:
        return self._TRIGGER_SOURCE_TO_V9_TYPE.get(obj.trigger_source, "manual_task")

    def get_related_document(self, obj: PaperlessTask) -> int | None:
        ids = obj.related_document_ids
        return ids[0] if ids else None

    def get_duplicate_documents(
        self,
        obj: PaperlessTask,
    ) -> list[dict[str, Any]]:
        if not obj.result_data:
            return []
        dup_of = obj.result_data.get("duplicate_of")
        if dup_of is None:
            return []
        request = self.context.get("request")
        if request is None:
            return []
        user = request.user
        qs = Document.global_objects.filter(pk=dup_of)
        if not user.is_staff:
            allowed_ids = permitted_document_ids(user, include_deleted=True)
            qs = qs.filter(pk__in=allowed_ids)
        return list(qs.values("id", "title", "deleted_at"))


class TaskSummarySerializer(serializers.Serializer[dict[str, Any]]):
    task_type = serializers.CharField()
    total_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    failure_count = serializers.IntegerField()
    avg_duration_seconds = serializers.FloatField(allow_null=True)
    avg_wait_time_seconds = serializers.FloatField(allow_null=True)
    last_run = serializers.DateTimeField(allow_null=True)
    last_success = serializers.DateTimeField(allow_null=True)
    last_failure = serializers.DateTimeField(allow_null=True)


class RunTaskSerializer(serializers.Serializer[dict[str, str]]):
    task_type = serializers.ChoiceField(
        choices=PaperlessTask.TaskType.choices,
        label="Task Type",
        write_only=True,
    )


class AcknowledgeTasksViewSerializer(serializers.Serializer[dict[str, Any]]):
    tasks = serializers.ListField(
        required=False,
        label="Tasks",
        write_only=True,
        child=serializers.IntegerField(),
    )
    all = serializers.BooleanField(
        required=False,
        default=False,
        label="All",
        write_only=True,
    )

    def _validate_task_id_list(self, tasks, name="tasks") -> None:
        if not isinstance(tasks, list):
            raise serializers.ValidationError(f"{name} must be a list")
        if not all(isinstance(i, int) for i in tasks):
            raise serializers.ValidationError(f"{name} must be a list of integers")
        queryset = self.context.get("queryset", PaperlessTask.objects.all())
        count = queryset.filter(id__in=tasks).count()
        if not count == len(tasks):
            raise serializers.ValidationError(
                f"Some tasks in {name} don't exist or were specified twice.",
            )

    def validate_tasks(self, tasks):
        self._validate_task_id_list(tasks)
        return tasks

    def validate(self, attrs):
        acknowledge_all = attrs.get("all", False)
        task_ids = attrs.get("tasks")

        if acknowledge_all and task_ids is not None:
            raise serializers.ValidationError(
                "Set either all or tasks, not both.",
            )
        if not acknowledge_all and task_ids is None:
            raise serializers.ValidationError(
                "Either all must be true or tasks must be provided.",
            )

        return attrs
