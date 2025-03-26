from django.apps import AppConfig

from edoc_text.signals import text_consumer_declaration


class EdocTextConfig(AppConfig):
    name = "edoc_text"

    def ready(self):
        from documents.signals import document_consumer_declaration

        document_consumer_declaration.connect(text_consumer_declaration)

        AppConfig.ready(self)
