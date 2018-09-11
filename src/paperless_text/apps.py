from django.apps import AppConfig


class PaperlessTextConfig(AppConfig):

    name = "paperless_text"

    def ready(self):

        from documents.signals import document_consumer_declaration

        from .signals import ConsumerDeclaration

        document_consumer_declaration.connect(ConsumerDeclaration.handle)

        AppConfig.ready(self)
