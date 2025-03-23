from django.apps import AppConfig

from paperless_mistralocr.signals import mistral_ocr_consumer_declaration


class PaperlessMistralOcrConfig(AppConfig):
    name = "paperless_mistralocr"

    def ready(self):
        from documents.signals import document_consumer_declaration

        document_consumer_declaration.connect(mistral_ocr_consumer_declaration)

        AppConfig.ready(self)
