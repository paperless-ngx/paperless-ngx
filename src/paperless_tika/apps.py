from django.apps import AppConfig
from django.conf import settings
from paperless_tika.signals import tika_consumer_declaration
from paperless_tika.signals import tika_consumer_declaration_eml


class PaperlessTikaConfig(AppConfig):
    name = "paperless_tika"

    def ready(self):
        from documents.signals import document_consumer_declaration

        if settings.PAPERLESS_TIKA_ENABLED:
            document_consumer_declaration.connect(tika_consumer_declaration)
            document_consumer_declaration.connect(tika_consumer_declaration_eml)
        AppConfig.ready(self)
