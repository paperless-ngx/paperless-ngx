"""
Serializers for AI Suggestions API.

This module provides serializers for exposing AI scanner results
and handling user feedback on AI suggestions.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from documents.models import AISuggestionFeedback
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Workflow

# Suggestion type choices - used across multiple serializers
SUGGESTION_TYPE_CHOICES = [
    "tag",
    "correspondent",
    "document_type",
    "storage_path",
    "custom_field",
    "workflow",
    "title",
]

# Types that require value_id
ID_REQUIRED_TYPES = [
    "tag",
    "correspondent",
    "document_type",
    "storage_path",
    "workflow",
]
# Types that require value_text
TEXT_REQUIRED_TYPES = ["title"]
# Types that can use either (custom_field can be ID or text)


class TagSuggestionSerializer(serializers.Serializer):
    """Serializer for tag suggestions."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    color = serializers.CharField()
    confidence = serializers.FloatField()


class CorrespondentSuggestionSerializer(serializers.Serializer):
    """Serializer for correspondent suggestions."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    confidence = serializers.FloatField()


class DocumentTypeSuggestionSerializer(serializers.Serializer):
    """Serializer for document type suggestions."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    confidence = serializers.FloatField()


class StoragePathSuggestionSerializer(serializers.Serializer):
    """Serializer for storage path suggestions."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    path = serializers.CharField()
    confidence = serializers.FloatField()


class CustomFieldSuggestionSerializer(serializers.Serializer):
    """Serializer for custom field suggestions."""

    field_id = serializers.IntegerField()
    field_name = serializers.CharField()
    value = serializers.CharField()
    confidence = serializers.FloatField()


class WorkflowSuggestionSerializer(serializers.Serializer):
    """Serializer for workflow suggestions."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    confidence = serializers.FloatField()


class TitleSuggestionSerializer(serializers.Serializer):
    """Serializer for title suggestions."""

    title = serializers.CharField()


class AISuggestionsSerializer(serializers.Serializer):
    """
    Main serializer for AI scan results.

    Converts AIScanResult objects to JSON format for API responses.
    """

    tags = TagSuggestionSerializer(many=True, required=False)
    correspondent = CorrespondentSuggestionSerializer(required=False, allow_null=True)
    document_type = DocumentTypeSuggestionSerializer(required=False, allow_null=True)
    storage_path = StoragePathSuggestionSerializer(required=False, allow_null=True)
    custom_fields = CustomFieldSuggestionSerializer(many=True, required=False)
    workflows = WorkflowSuggestionSerializer(many=True, required=False)
    title_suggestion = TitleSuggestionSerializer(required=False, allow_null=True)

    @staticmethod
    def from_scan_result(scan_result, document_id: int) -> dict[str, Any]:
        """
        Convert an AIScanResult object to serializer data.

        Args:
            scan_result: AIScanResult instance from ai_scanner
            document_id: Document ID for reference

        Returns:
            Dictionary ready for serialization
        """
        data = {}

        # Tags
        if scan_result.tags:
            tag_suggestions = []
            for tag_id, confidence in scan_result.tags:
                try:
                    tag = Tag.objects.get(pk=tag_id)
                    tag_suggestions.append(
                        {
                            "id": tag.id,
                            "name": tag.name,
                            "color": getattr(tag, "color", "#000000"),
                            "confidence": confidence,
                        },
                    )
                except Tag.DoesNotExist:
                    # Tag no longer exists in database; skip this suggestion
                    pass
            data["tags"] = tag_suggestions

        # Correspondent
        if scan_result.correspondent:
            corr_id, confidence = scan_result.correspondent
            try:
                correspondent = Correspondent.objects.get(pk=corr_id)
                data["correspondent"] = {
                    "id": correspondent.id,
                    "name": correspondent.name,
                    "confidence": confidence,
                }
            except Correspondent.DoesNotExist:
                # Correspondent no longer exists in database; omit from suggestions
                pass

        # Document Type
        if scan_result.document_type:
            type_id, confidence = scan_result.document_type
            try:
                doc_type = DocumentType.objects.get(pk=type_id)
                data["document_type"] = {
                    "id": doc_type.id,
                    "name": doc_type.name,
                    "confidence": confidence,
                }
            except DocumentType.DoesNotExist:
                # Document type no longer exists in database; omit from suggestions
                pass

        # Storage Path
        if scan_result.storage_path:
            path_id, confidence = scan_result.storage_path
            try:
                storage_path = StoragePath.objects.get(pk=path_id)
                data["storage_path"] = {
                    "id": storage_path.id,
                    "name": storage_path.name,
                    "path": storage_path.path,
                    "confidence": confidence,
                }
            except StoragePath.DoesNotExist:
                # Storage path no longer exists in database; omit from suggestions
                pass

        # Custom Fields
        if scan_result.custom_fields:
            field_suggestions = []
            for field_id, (value, confidence) in scan_result.custom_fields.items():
                try:
                    field = CustomField.objects.get(pk=field_id)
                    field_suggestions.append(
                        {
                            "field_id": field.id,
                            "field_name": field.name,
                            "value": str(value),
                            "confidence": confidence,
                        },
                    )
                except CustomField.DoesNotExist:
                    # Custom field no longer exists in database; skip this suggestion
                    pass
            data["custom_fields"] = field_suggestions

        # Workflows
        if scan_result.workflows:
            workflow_suggestions = []
            for workflow_id, confidence in scan_result.workflows:
                try:
                    workflow = Workflow.objects.get(pk=workflow_id)
                    workflow_suggestions.append(
                        {
                            "id": workflow.id,
                            "name": workflow.name,
                            "confidence": confidence,
                        },
                    )
                except Workflow.DoesNotExist:
                    # Workflow no longer exists in database; skip this suggestion
                    pass
            data["workflows"] = workflow_suggestions

        # Title suggestion
        if scan_result.title_suggestion:
            data["title_suggestion"] = {
                "title": scan_result.title_suggestion,
            }

        return data


class SuggestionSerializerMixin:
    """
    Mixin to provide validation logic for suggestion serializers.
    """

    def validate(self, attrs):
        """Validate that the correct value field is provided for the suggestion type."""
        suggestion_type = attrs.get("suggestion_type")
        value_id = attrs.get("value_id")
        value_text = attrs.get("value_text")

        # Types that require value_id
        if suggestion_type in ID_REQUIRED_TYPES and not value_id:
            raise serializers.ValidationError(
                f"value_id is required for suggestion_type '{suggestion_type}'",
            )

        # Types that require value_text
        if suggestion_type in TEXT_REQUIRED_TYPES and not value_text:
            raise serializers.ValidationError(
                f"value_text is required for suggestion_type '{suggestion_type}'",
            )

        # For custom_field, either is acceptable
        if suggestion_type == "custom_field" and not value_id and not value_text:
            raise serializers.ValidationError(
                "Either value_id or value_text must be provided for custom_field",
            )

        return attrs


class ApplySuggestionSerializer(SuggestionSerializerMixin, serializers.Serializer):
    """
    Serializer for applying AI suggestions.
    """

    suggestion_type = serializers.ChoiceField(
        choices=SUGGESTION_TYPE_CHOICES,
        required=True,
    )

    value_id = serializers.IntegerField(required=False, allow_null=True)
    value_text = serializers.CharField(required=False, allow_blank=True)
    confidence = serializers.FloatField(required=True)


class RejectSuggestionSerializer(SuggestionSerializerMixin, serializers.Serializer):
    """
    Serializer for rejecting AI suggestions.
    """

    suggestion_type = serializers.ChoiceField(
        choices=SUGGESTION_TYPE_CHOICES,
        required=True,
    )

    value_id = serializers.IntegerField(required=False, allow_null=True)
    value_text = serializers.CharField(required=False, allow_blank=True)
    confidence = serializers.FloatField(required=True)


class AISuggestionFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for AI suggestion feedback model."""

    class Meta:
        model = AISuggestionFeedback
        fields = [
            "id",
            "document",
            "suggestion_type",
            "suggested_value_id",
            "suggested_value_text",
            "confidence",
            "status",
            "user",
            "created_at",
            "applied_at",
            "metadata",
        ]
        read_only_fields = ["id", "created_at", "applied_at"]


class AISuggestionStatsSerializer(serializers.Serializer):
    """
    Serializer for AI suggestion accuracy statistics.
    """

    total_suggestions = serializers.IntegerField()
    total_applied = serializers.IntegerField()
    total_rejected = serializers.IntegerField()
    accuracy_rate = serializers.FloatField()

    by_type = serializers.DictField(
        child=serializers.DictField(),
        help_text="Statistics broken down by suggestion type",
    )

    average_confidence_applied = serializers.FloatField()
    average_confidence_rejected = serializers.FloatField()

    recent_suggestions = AISuggestionFeedbackSerializer(many=True, required=False)
