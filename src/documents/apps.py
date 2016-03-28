from django.apps import AppConfig


class DocumentsConfig(AppConfig):

    name = "documents"

    def ready(self):

        from .signals import document_consumption_finished
        from .signals.handlers import set_correspondent, set_tags

        document_consumption_finished.connect(set_tags)
        document_consumption_finished.connect(set_correspondent)

        AppConfig.ready(self)
