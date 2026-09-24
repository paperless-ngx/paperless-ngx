from __future__ import annotations

import logging

from django.db.models import Count
from rest_framework import fields
from rest_framework import serializers

from documents.data_models import DocumentSource
from documents.filters import CustomFieldQueryParser
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowActionEmail
from documents.models import WorkflowActionWebhook
from documents.models import WorkflowTrigger
from documents.templating.workflows import validate_workflow_template
from documents.validators import url_validator

from .metadata import CorrespondentField
from .metadata import DocumentTypeField
from .metadata import StoragePathField
from .metadata import TagsField

logger = logging.getLogger("paperless.serializers")


class WorkflowTriggerSerializer(serializers.ModelSerializer[WorkflowTrigger]):
    id = serializers.IntegerField(required=False, allow_null=True)
    sources = fields.MultipleChoiceField(
        choices=WorkflowTrigger.DocumentSourceChoices.choices,
        allow_empty=True,
        default={
            DocumentSource.ConsumeFolder,
            DocumentSource.ApiUpload,
            DocumentSource.MailFetch,
        },
    )

    type = serializers.ChoiceField(
        choices=WorkflowTrigger.WorkflowTriggerType.choices,
        label="Trigger Type",
    )

    class Meta:
        model = WorkflowTrigger
        fields = [
            "id",
            "sources",
            "type",
            "filter_path",
            "filter_filename",
            "filter_mailrule",
            "matching_algorithm",
            "match",
            "is_insensitive",
            "filter_has_tags",
            "filter_has_all_tags",
            "filter_has_not_tags",
            "filter_custom_field_query",
            "filter_has_any_correspondents",
            "filter_has_not_correspondents",
            "filter_has_any_document_types",
            "filter_has_not_document_types",
            "filter_has_any_storage_paths",
            "filter_has_not_storage_paths",
            "filter_has_correspondent",
            "filter_has_document_type",
            "filter_has_storage_path",
            "schedule_offset_days",
            "schedule_is_recurring",
            "schedule_recurring_interval_days",
            "schedule_date_field",
            "schedule_date_custom_field",
        ]

    def validate(self, attrs):
        # Empty strings treated as None to avoid unexpected behavior
        if (
            "filter_filename" in attrs
            and attrs["filter_filename"] is not None
            and len(attrs["filter_filename"]) == 0
        ):
            attrs["filter_filename"] = None
        if (
            "filter_path" in attrs
            and attrs["filter_path"] is not None
            and len(attrs["filter_path"]) == 0
        ):
            attrs["filter_path"] = None

        if (
            "filter_custom_field_query" in attrs
            and attrs["filter_custom_field_query"] is not None
            and len(attrs["filter_custom_field_query"]) == 0
        ):
            attrs["filter_custom_field_query"] = None

        if (
            "filter_custom_field_query" in attrs
            and attrs["filter_custom_field_query"] is not None
        ):
            parser = CustomFieldQueryParser("filter_custom_field_query")
            parser.parse(attrs["filter_custom_field_query"])

        trigger_type = attrs.get("type", getattr(self.instance, "type", None))
        if (
            trigger_type == WorkflowTrigger.WorkflowTriggerType.CONSUMPTION
            and "filter_mailrule" not in attrs
            and ("filter_filename" not in attrs or attrs["filter_filename"] is None)
            and ("filter_path" not in attrs or attrs["filter_path"] is None)
        ):
            raise serializers.ValidationError(
                "File name, path or mail rule filter are required",
            )

        return attrs

    @staticmethod
    def normalize_workflow_trigger_sources(trigger) -> None:
        """
        Convert sources to strings to handle django-multiselectfield v1.0 changes
        """
        if trigger and "sources" in trigger:
            trigger["sources"] = [
                str(s.value if hasattr(s, "value") else s) for s in trigger["sources"]
            ]

    def create(self, validated_data):
        WorkflowTriggerSerializer.normalize_workflow_trigger_sources(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        WorkflowTriggerSerializer.normalize_workflow_trigger_sources(validated_data)
        return super().update(instance, validated_data)


class WorkflowActionEmailSerializer(serializers.ModelSerializer[WorkflowActionEmail]):
    id = serializers.IntegerField(allow_null=True, required=False)

    class Meta:
        model = WorkflowActionEmail
        fields = [
            "id",
            "subject",
            "body",
            "to",
            "include_document",
        ]


class WorkflowActionWebhookSerializer(
    serializers.ModelSerializer[WorkflowActionWebhook],
):
    id = serializers.IntegerField(allow_null=True, required=False)

    def validate_url(self, url):
        url_validator(url)
        return url

    class Meta:
        model = WorkflowActionWebhook
        fields = [
            "id",
            "url",
            "use_params",
            "as_json",
            "params",
            "body",
            "headers",
            "include_document",
        ]


class WorkflowActionSerializer(serializers.ModelSerializer[WorkflowAction]):
    id = serializers.IntegerField(required=False, allow_null=True)
    assign_correspondent = CorrespondentField(allow_null=True, required=False)
    assign_tags = TagsField(many=True, allow_null=True, required=False)
    assign_document_type = DocumentTypeField(allow_null=True, required=False)
    assign_storage_path = StoragePathField(allow_null=True, required=False)
    email = WorkflowActionEmailSerializer(allow_null=True, required=False)
    webhook = WorkflowActionWebhookSerializer(allow_null=True, required=False)

    class Meta:
        model = WorkflowAction
        fields = [
            "id",
            "type",
            "assign_title",
            "assign_tags",
            "assign_correspondent",
            "assign_document_type",
            "assign_storage_path",
            "assign_owner",
            "assign_view_users",
            "assign_view_groups",
            "assign_change_users",
            "assign_change_groups",
            "assign_custom_fields",
            "assign_custom_fields_values",
            "remove_all_tags",
            "remove_tags",
            "remove_all_correspondents",
            "remove_correspondents",
            "remove_all_document_types",
            "remove_document_types",
            "remove_all_storage_paths",
            "remove_storage_paths",
            "remove_custom_fields",
            "remove_all_custom_fields",
            "remove_all_owners",
            "remove_owners",
            "remove_all_permissions",
            "remove_view_users",
            "remove_view_groups",
            "remove_change_users",
            "remove_change_groups",
            "email",
            "webhook",
            "passwords",
            "ai_suggestion_fields",
            "ai_create_missing",
            "ai_overwrite_existing",
        ]

    def validate(self, attrs):
        if "assign_title" in attrs and attrs["assign_title"] is not None:
            if len(attrs["assign_title"]) == 0:
                # Empty strings treated as None to avoid unexpected behavior
                attrs["assign_title"] = None
            else:
                try:
                    validate_workflow_template(attrs["assign_title"])
                except (ValueError, KeyError) as e:
                    raise serializers.ValidationError(
                        {"assign_title": f"{e.args[0]}"},
                    )

        if attrs.get("assign_custom_fields_values"):
            # Empty strings treated as None to avoid unexpected behavior
            attrs["assign_custom_fields_values"] = {
                field_id: (None if value == "" else value)
                for field_id, value in attrs["assign_custom_fields_values"].items()
            }

        if (
            "type" in attrs
            and attrs["type"] == WorkflowAction.WorkflowActionType.EMAIL
            and "email" not in attrs
        ):
            raise serializers.ValidationError(
                "Email data is required for email actions",
            )

        if (
            "type" in attrs
            and attrs["type"] == WorkflowAction.WorkflowActionType.WEBHOOK
            and "webhook" not in attrs
        ):
            raise serializers.ValidationError(
                "Webhook data is required for webhook actions",
            )

        if (
            "type" in attrs
            and attrs["type"] == WorkflowAction.WorkflowActionType.PASSWORD_REMOVAL
        ):
            passwords = attrs.get("passwords")
            # ensure passwords is a non-empty list of non-empty strings
            if (
                passwords is None
                or not isinstance(passwords, list)
                or len(passwords) == 0
                or any(not isinstance(pw, str) for pw in passwords)
                or any(len(pw.strip()) == 0 for pw in passwords)
            ):
                raise serializers.ValidationError(
                    "Passwords are required for password removal actions",
                )

        if (
            "type" in attrs
            and attrs["type"] == WorkflowAction.WorkflowActionType.APPLY_AI_SUGGESTIONS
        ):
            fields = attrs.get("ai_suggestion_fields")
            valid_fields = set(WorkflowAction.AISuggestionField.values)
            if (
                fields is None
                or not isinstance(fields, list)
                or len(fields) == 0
                or any(field not in valid_fields for field in fields)
            ):
                raise serializers.ValidationError(
                    "At least one valid field is required for apply AI "
                    f"suggestions actions, options are: {sorted(valid_fields)}",
                )

        return attrs


class WorkflowSerializer(serializers.ModelSerializer[Workflow]):
    order = serializers.IntegerField(required=False)

    triggers = WorkflowTriggerSerializer(many=True)
    actions = WorkflowActionSerializer(many=True)

    class Meta:
        model = Workflow
        fields = [
            "id",
            "name",
            "order",
            "enabled",
            "triggers",
            "actions",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if "actions" in attrs:
            has_remote_ocr_action = any(
                action.get("type") == WorkflowAction.WorkflowActionType.REMOTE_OCR
                for action in attrs["actions"]
            )
            has_ai_suggestions_action = any(
                action.get("type")
                == WorkflowAction.WorkflowActionType.APPLY_AI_SUGGESTIONS
                for action in attrs["actions"]
            )
        else:
            has_remote_ocr_action = self.instance is not None and (
                self.instance.actions.filter(
                    type=WorkflowAction.WorkflowActionType.REMOTE_OCR,
                ).exists()
            )
            has_ai_suggestions_action = self.instance is not None and (
                self.instance.actions.filter(
                    type=WorkflowAction.WorkflowActionType.APPLY_AI_SUGGESTIONS,
                ).exists()
            )

        if "triggers" in attrs:
            has_consumption_trigger = any(
                trigger.get("type") == WorkflowTrigger.WorkflowTriggerType.CONSUMPTION
                for trigger in attrs["triggers"]
            )
            has_non_consumption_trigger = any(
                trigger.get("type") != WorkflowTrigger.WorkflowTriggerType.CONSUMPTION
                for trigger in attrs["triggers"]
            )
        else:
            has_consumption_trigger = self.instance is not None and (
                self.instance.triggers.filter(
                    type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                ).exists()
            )
            has_non_consumption_trigger = self.instance is not None and (
                self.instance.triggers.exclude(
                    type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
                ).exists()
            )

        # Remote OCR can only work with consumption triggers
        if has_remote_ocr_action and not has_consumption_trigger:
            raise serializers.ValidationError(
                "Remote OCR actions require a consumption started trigger",
            )

        # Suggestions are made from the document content, which does not exist
        # until after consumption has finished
        if has_ai_suggestions_action and not has_non_consumption_trigger:
            raise serializers.ValidationError(
                "Apply AI suggestions actions require a trigger other than "
                "consumption started",
            )

        return attrs

    def update_triggers_and_actions(
        self,
        instance: Workflow,
        triggers,
        actions,
    ) -> None:
        set_triggers = []
        set_actions = []

        if triggers is not None and triggers is not serializers.empty:
            for trigger in triggers:
                filter_has_tags = trigger.pop("filter_has_tags", None)
                filter_has_all_tags = trigger.pop("filter_has_all_tags", None)
                filter_has_not_tags = trigger.pop("filter_has_not_tags", None)
                filter_has_any_correspondents = trigger.pop(
                    "filter_has_any_correspondents",
                    None,
                )
                filter_has_not_correspondents = trigger.pop(
                    "filter_has_not_correspondents",
                    None,
                )
                filter_has_any_document_types = trigger.pop(
                    "filter_has_any_document_types",
                    None,
                )
                filter_has_not_document_types = trigger.pop(
                    "filter_has_not_document_types",
                    None,
                )
                filter_has_any_storage_paths = trigger.pop(
                    "filter_has_any_storage_paths",
                    None,
                )
                filter_has_not_storage_paths = trigger.pop(
                    "filter_has_not_storage_paths",
                    None,
                )
                # Convert sources to strings to handle django-multiselectfield v1.0 changes
                WorkflowTriggerSerializer.normalize_workflow_trigger_sources(trigger)
                trigger_instance, _ = WorkflowTrigger.objects.update_or_create(
                    id=trigger.get("id"),
                    defaults=trigger,
                )
                if filter_has_tags is not None:
                    trigger_instance.filter_has_tags.set(filter_has_tags)
                if filter_has_all_tags is not None:
                    trigger_instance.filter_has_all_tags.set(filter_has_all_tags)
                if filter_has_not_tags is not None:
                    trigger_instance.filter_has_not_tags.set(filter_has_not_tags)
                if filter_has_any_correspondents is not None:
                    trigger_instance.filter_has_any_correspondents.set(
                        filter_has_any_correspondents,
                    )
                if filter_has_not_correspondents is not None:
                    trigger_instance.filter_has_not_correspondents.set(
                        filter_has_not_correspondents,
                    )
                if filter_has_any_document_types is not None:
                    trigger_instance.filter_has_any_document_types.set(
                        filter_has_any_document_types,
                    )
                if filter_has_not_document_types is not None:
                    trigger_instance.filter_has_not_document_types.set(
                        filter_has_not_document_types,
                    )
                if filter_has_any_storage_paths is not None:
                    trigger_instance.filter_has_any_storage_paths.set(
                        filter_has_any_storage_paths,
                    )
                if filter_has_not_storage_paths is not None:
                    trigger_instance.filter_has_not_storage_paths.set(
                        filter_has_not_storage_paths,
                    )
                set_triggers.append(trigger_instance)

        if actions is not None and actions is not serializers.empty:
            for index, action in enumerate(actions):
                action["order"] = index
                assign_tags = action.pop("assign_tags", None)
                assign_view_users = action.pop("assign_view_users", None)
                assign_view_groups = action.pop("assign_view_groups", None)
                assign_change_users = action.pop("assign_change_users", None)
                assign_change_groups = action.pop("assign_change_groups", None)
                assign_custom_fields = action.pop("assign_custom_fields", None)
                remove_tags = action.pop("remove_tags", None)
                remove_correspondents = action.pop("remove_correspondents", None)
                remove_document_types = action.pop("remove_document_types", None)
                remove_storage_paths = action.pop("remove_storage_paths", None)
                remove_custom_fields = action.pop("remove_custom_fields", None)
                remove_owners = action.pop("remove_owners", None)
                remove_view_users = action.pop("remove_view_users", None)
                remove_view_groups = action.pop("remove_view_groups", None)
                remove_change_users = action.pop("remove_change_users", None)
                remove_change_groups = action.pop("remove_change_groups", None)

                email_data = action.pop("email", None)
                webhook_data = action.pop("webhook", None)

                action_instance, _ = WorkflowAction.objects.update_or_create(
                    id=action.get("id"),
                    defaults=action,
                )

                if email_data is not None:
                    serializer = WorkflowActionEmailSerializer(data=email_data)
                    serializer.is_valid(raise_exception=True)
                    email, _ = WorkflowActionEmail.objects.update_or_create(
                        id=email_data.get("id"),
                        defaults=serializer.validated_data,
                    )
                    action_instance.email = email
                    action_instance.save()

                if webhook_data is not None:
                    serializer = WorkflowActionWebhookSerializer(data=webhook_data)
                    serializer.is_valid(raise_exception=True)
                    webhook, _ = WorkflowActionWebhook.objects.update_or_create(
                        id=webhook_data.get("id"),
                        defaults=serializer.validated_data,
                    )
                    action_instance.webhook = webhook
                    action_instance.save()

                if assign_tags is not None:
                    action_instance.assign_tags.set(assign_tags)
                if assign_view_users is not None:
                    action_instance.assign_view_users.set(assign_view_users)
                if assign_view_groups is not None:
                    action_instance.assign_view_groups.set(assign_view_groups)
                if assign_change_users is not None:
                    action_instance.assign_change_users.set(assign_change_users)
                if assign_change_groups is not None:
                    action_instance.assign_change_groups.set(assign_change_groups)
                if assign_custom_fields is not None:
                    action_instance.assign_custom_fields.set(assign_custom_fields)
                if remove_tags is not None:
                    action_instance.remove_tags.set(remove_tags)
                if remove_correspondents is not None:
                    action_instance.remove_correspondents.set(remove_correspondents)
                if remove_document_types is not None:
                    action_instance.remove_document_types.set(remove_document_types)
                if remove_storage_paths is not None:
                    action_instance.remove_storage_paths.set(remove_storage_paths)
                if remove_custom_fields is not None:
                    action_instance.remove_custom_fields.set(remove_custom_fields)
                if remove_owners is not None:
                    action_instance.remove_owners.set(remove_owners)
                if remove_view_users is not None:
                    action_instance.remove_view_users.set(remove_view_users)
                if remove_view_groups is not None:
                    action_instance.remove_view_groups.set(remove_view_groups)
                if remove_change_users is not None:
                    action_instance.remove_change_users.set(remove_change_users)
                if remove_change_groups is not None:
                    action_instance.remove_change_groups.set(remove_change_groups)

                set_actions.append(action_instance)

        if triggers is not serializers.empty:
            instance.triggers.set(set_triggers)
        if actions is not serializers.empty:
            instance.actions.set(set_actions)
        instance.save()

    def prune_triggers_and_actions(self) -> None:
        """
        ManyToMany fields dont support e.g. on_delete so we need to discard unattached
        triggers and actions manually
        """
        WorkflowTrigger.objects.annotate(
            workflow_count=Count("workflows"),
        ).filter(workflow_count=0).delete()

        WorkflowAction.objects.annotate(
            workflow_count=Count("workflows"),
        ).filter(workflow_count=0).delete()

        WorkflowActionEmail.objects.filter(action=None).delete()
        WorkflowActionWebhook.objects.filter(action=None).delete()

    def create(self, validated_data) -> Workflow:
        if "triggers" in validated_data:
            triggers = validated_data.pop("triggers")

        if "actions" in validated_data:
            actions = validated_data.pop("actions")
            for action in actions:
                action.pop("id", None)

        instance = super().create(validated_data)

        self.update_triggers_and_actions(instance, triggers, actions)

        return instance

    def update(self, instance: Workflow, validated_data) -> Workflow:
        triggers = validated_data.pop("triggers", serializers.empty)
        actions = validated_data.pop("actions", serializers.empty)

        instance = super().update(instance, validated_data)

        self.update_triggers_and_actions(instance, triggers, actions)
        self.prune_triggers_and_actions()

        return instance
