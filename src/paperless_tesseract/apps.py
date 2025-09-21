from django.apps import AppConfig

from paperless_tesseract.signals import tesseract_consumer_declaration


class PaperlessTesseractConfig(AppConfig):
    name = "paperless_tesseract"

    def ready(self) -> None:
        from documents.signals import document_consumer_declaration

        document_consumer_declaration.connect(tesseract_consumer_declaration)

        AppConfig.ready(self)
