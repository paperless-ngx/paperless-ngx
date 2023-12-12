from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from paperless_tesseract.models import OcrSettings
from paperless_tesseract.serialisers import OcrSettingsSerializer


class OcrSettingsViewSet(ModelViewSet):
    model = OcrSettings

    queryset = OcrSettings.objects

    serializer_class = OcrSettingsSerializer
    permission_classes = (IsAuthenticated,)
