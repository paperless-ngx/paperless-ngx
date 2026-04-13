"""Serializers for OCR template models."""

from rest_framework import serializers

from documents.models import CustomField
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
            "zone_source_width",
            "zone_source_height",
        ]

    def validate_width(self, value):
        if value < 1:
            raise serializers.ValidationError("Width must be at least 1.")
        return value

    def validate_height(self, value):
        if value < 1:
            raise serializers.ValidationError("Height must be at least 1.")
        return value

    def validate_custom_field(self, value):
        unsupported = {
            CustomField.FieldDataType.DOCUMENTLINK,
            CustomField.FieldDataType.SELECT,
        }
        if value.data_type in unsupported:
            raise serializers.ValidationError(
                f"Custom field type '{value.data_type}' is not supported for OCR extraction. "
                f"Use string, integer, float, date, monetary, boolean, URL, or long text."
            )
        return value


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

    def validate_source_width(self, value):
        if value < 1:
            raise serializers.ValidationError("Source width must be at least 1.")
        return value

    def validate_source_height(self, value):
        if value < 1:
            raise serializers.ValidationError("Source height must be at least 1.")
        return value

    def validate_zones(self, zones_data):
        """Validate zone coordinates are within the source dimensions."""
        # source_width/height may not be in initial_data during partial updates
        source_width = (
            self.initial_data.get("source_width")
            or (self.instance.source_width if self.instance else None)
        )
        source_height = (
            self.initial_data.get("source_height")
            or (self.instance.source_height if self.instance else None)
        )

        if source_width and source_height:
            for zone in zones_data:
                x = zone.get("x", 0)
                y = zone.get("y", 0)
                w = zone.get("width", 0)
                h = zone.get("height", 0)
                if x + w > int(source_width):
                    raise serializers.ValidationError(
                        f"Zone '{zone.get('name', '?')}' extends beyond source width "
                        f"({x + w} > {source_width})."
                    )
                if y + h > int(source_height):
                    raise serializers.ValidationError(
                        f"Zone '{zone.get('name', '?')}' extends beyond source height "
                        f"({y + h} > {source_height})."
                    )

        return zones_data

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
