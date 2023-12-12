from rest_framework import serializers

from paperless_tesseract.models import OcrSettings


class OcrSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OcrSettings
        fields = ["all"]
