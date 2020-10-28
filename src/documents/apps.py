from django.apps import AppConfig
from django.db.models.signals import post_delete


class DocumentsConfig(AppConfig):

    name = "documents"

    def ready(self):

        from .signals import document_consumption_started
        from .signals import document_consumption_finished
        from .signals.handlers import (
            add_inbox_tags,
            run_pre_consume_script,
            run_post_consume_script,
            cleanup_document_deletion,
            set_log_entry,
            index_document,
            set_correspondent,
            set_document_type,
            set_tags

        )

        document_consumption_started.connect(run_pre_consume_script)

        document_consumption_finished.connect(index_document)
        document_consumption_finished.connect(add_inbox_tags)
        document_consumption_finished.connect(set_correspondent)
        document_consumption_finished.connect(set_document_type)
        document_consumption_finished.connect(set_tags)
        document_consumption_finished.connect(set_log_entry)
        document_consumption_finished.connect(run_post_consume_script)

        post_delete.connect(cleanup_document_deletion)

        AppConfig.ready(self)
