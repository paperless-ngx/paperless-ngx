from django.apps import AppConfig


class DocumentsConfig(AppConfig):

    name = "documents"

    def ready(self):
        from .signals import document_consumption_finished
        from .signals.handlers import (
            add_inbox_tags,
            set_log_entry,
            set_correspondent,
            set_document_type,
            set_tags,
            add_to_index
        )

        document_consumption_finished.connect(add_inbox_tags)
        document_consumption_finished.connect(set_correspondent)
        document_consumption_finished.connect(set_document_type)
        document_consumption_finished.connect(set_tags)
        document_consumption_finished.connect(set_log_entry)
        document_consumption_finished.connect(add_to_index)

        AppConfig.ready(self)
