from django.apps import AppConfig
from django.conf import settings

from edoc_tika.signals import tika_consumer_declaration


class EdocTikaConfig(AppConfig):
    name = "edoc_tika"

    def ready(self):
        from documents.signals import document_consumer_declaration

        if settings.TIKA_ENABLED:
            document_consumer_declaration.connect(tika_consumer_declaration)
        AppConfig.ready(self)
