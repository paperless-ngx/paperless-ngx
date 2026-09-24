from __future__ import annotations

import logging

from rest_framework import serializers

from documents.models import Document
from documents.models import UiSettings

from .base import SerializerWithPerms

logger = logging.getLogger("paperless.serializers")


class UiSettingsViewSerializer(serializers.ModelSerializer[UiSettings]):
    settings = serializers.DictField(required=False, allow_null=True)

    class Meta:
        model = UiSettings
        depth = 1
        fields = [
            "id",
            "settings",
        ]

    def validate_settings(self, settings):
        # we never save update checking backend setting
        if "update_checking" in settings:
            try:
                settings["update_checking"].pop("backend_setting")
            except KeyError:
                pass
        return settings

    def create(self, validated_data):
        ui_settings = UiSettings.objects.update_or_create(
            user=validated_data.get("user"),
            defaults={"settings": validated_data.get("settings", None)},
        )
        return ui_settings


class TrashSerializer(SerializerWithPerms):
    documents = serializers.ListField(
        required=False,
        label="Documents",
        write_only=True,
        child=serializers.IntegerField(),
    )

    action = serializers.ChoiceField(
        choices=["restore", "empty"],
        label="Action",
        write_only=True,
    )

    def validate_documents(self, documents: list[int]) -> list[int]:
        count = Document.deleted_objects.filter(id__in=documents).count()
        if not count == len(documents):
            raise serializers.ValidationError(
                "Some documents in the list have not yet been deleted.",
            )
        return documents
