from django.apps import AppConfig

from edoc_tesseract.signals import tesseract_consumer_declaration


class EdocTesseractConfig(AppConfig):
    name = "edoc_tesseract"

    def ready(self):
        from documents.signals import document_consumer_declaration

        document_consumer_declaration.connect(tesseract_consumer_declaration)

        AppConfig.ready(self)
