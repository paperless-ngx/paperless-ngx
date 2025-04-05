from django.apps import AppConfig
from django.conf import settings

from paperless_mistralocr.signals import mistral_ocr_consumer_declaration


class PaperlessMistralOcrConfig(AppConfig):
    name = "paperless_mistralocr"

    def ready(self):
        from documents.signals import document_consumer_declaration

        document_consumer_declaration.connect(mistral_ocr_consumer_declaration)

        # Ensure OCR images directory exists
        settings.OCR_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        AppConfig.ready(self)
