from django.apps import AppConfig

from edoc_ocr_custom.signals import tesseract_consumer_declaration


class EdocTesseractConfig(AppConfig):
    name = "edoc_ocr_custom"

    def ready(self):
        from documents.signals import document_consumer_declaration

        document_consumer_declaration.connect(tesseract_consumer_declaration)

        AppConfig.ready(self)
