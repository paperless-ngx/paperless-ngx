from django.apps import AppConfig
from django.conf import settings


class PaperlessBimConfig(AppConfig):
    name = "paperless_bim"

    def ready(self):
        from documents.signals import document_consumer_declaration

        from paperless_bim.signals import bim_consumer_declaration

        if getattr(settings, "PAPERLESS_BIM_ENABLED", False):
            document_consumer_declaration.connect(bim_consumer_declaration)
        AppConfig.ready(self)
