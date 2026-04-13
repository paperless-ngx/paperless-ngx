"""Serializers for OCR template models."""

from rest_framework import serializers

from documents.models_ocr_templates import OcrTemplate
from documents.models_ocr_templates import OcrTemplateZone


class OcrTemplateZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = OcrTemplateZone
        fields = [
            "id",
            "name",
            "custom_field",
            "page",
            "x",
            "y",
            "width",
            "height",
            "ocr_language",
            "transform",
            "order",
        ]


class OcrTemplateSerializer(serializers.ModelSerializer):
    zones = OcrTemplateZoneSerializer(many=True, required=False)

    class Meta:
        model = OcrTemplate
        fields = [
            "id",
            "name",
            "document_type",
            "default_page",
            "source_width",
            "source_height",
            "enabled",
            "created",
            "updated",
            "zones",
        ]
        read_only_fields = ["created", "updated"]

    def create(self, validated_data):
        zones_data = validated_data.pop("zones", [])
        template = OcrTemplate.objects.create(**validated_data)
        for zone_data in zones_data:
            OcrTemplateZone.objects.create(template=template, **zone_data)
        return template

    def update(self, instance, validated_data):
        zones_data = validated_data.pop("zones", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if zones_data is not None:
            # Replace all zones with the new set
            instance.zones.all().delete()
            for zone_data in zones_data:
                OcrTemplateZone.objects.create(template=instance, **zone_data)

        return instance
