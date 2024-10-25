from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DocumentsConfig(AppConfig):
    name = "documents"

    verbose_name = _("Documents")

    def ready(self):
        from documents.signals import document_consumption_finished
        from documents.signals import document_updated
        from documents.signals.handlers import add_inbox_tags
        from documents.signals.handlers import add_to_index
        from documents.signals.handlers import run_workflows_added
        from documents.signals.handlers import run_workflows_updated
        from documents.signals.handlers import set_correspondent
        from documents.signals.handlers import set_document_type
        from documents.signals.handlers import set_log_entry
        from documents.signals.handlers import set_storage_path
        from documents.signals.handlers import set_tags

        document_consumption_finished.connect(add_inbox_tags)
        document_consumption_finished.connect(set_correspondent)
        document_consumption_finished.connect(set_document_type)
        document_consumption_finished.connect(set_tags)
        document_consumption_finished.connect(set_storage_path)
        document_consumption_finished.connect(set_log_entry)
        document_consumption_finished.connect(add_to_index)
        document_consumption_finished.connect(run_workflows_added)
        document_updated.connect(run_workflows_updated)

        AppConfig.ready(self)
