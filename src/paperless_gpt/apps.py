from django.apps import AppConfig
from django.conf import settings

from paperless_gpt.signals import llm_consumer_declaration


class PaperlessGPTConfig(AppConfig):
    name = "paperless_gpt"

    def ready(self):
        from documents.signals import document_consumer_declaration

        if settings.GPT_ENABLED:
            document_consumer_declaration.connect(llm_consumer_declaration)
        AppConfig.ready(self)
