from django.apps import AppConfig

from paperless_zip.signals import zip_consumer_declaration


class PaperlessZipConfig(AppConfig):
    name = "paperless_zip"

    def ready(self):
        from documents.signals import document_consumer_declaration

        document_consumer_declaration.connect(zip_consumer_declaration)
        AppConfig.ready(self)
