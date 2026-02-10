from django.apps import AppConfig

from paperless_remote.signals import remote_consumer_declaration


class PaperlessRemoteParserConfig(AppConfig):
    name = "paperless_remote"

    def ready(self) -> None:
        from documents.signals import document_consumer_declaration

        document_consumer_declaration.connect(remote_consumer_declaration)

        AppConfig.ready(self)
