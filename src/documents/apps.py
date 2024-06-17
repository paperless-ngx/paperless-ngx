from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DocumentsConfig(AppConfig):
    name = "documents"

    verbose_name = _("Documents")

    def ready(self):
        from documents.signals import document_consumption_finished
        from documents.signals import document_updated
        from documents.signals import approval_added
        from documents.signals import approval_updated
        from documents.signals.handlers import add_inbox_tags
        from documents.signals.handlers import add_to_index
        from documents.signals.handlers import run_workflow_added
        from documents.signals.handlers import run_workflow_updated
        from documents.signals.handlers import set_correspondent
        from documents.signals.handlers import set_warehouse
        from documents.signals.handlers import set_folder
        from documents.signals.handlers import set_document_type
        from documents.signals.handlers import set_log_entry
        from documents.signals.handlers import set_storage_path
        from documents.signals.handlers import set_tags
        from documents.signals.handlers import run_workflow_approval_added
        from documents.signals.handlers import run_workflow_approval_updated

        document_consumption_finished.connect(add_inbox_tags)
        document_consumption_finished.connect(set_correspondent)
        document_consumption_finished.connect(set_folder)
        document_consumption_finished.connect(set_warehouse)
        document_consumption_finished.connect(set_document_type)
        document_consumption_finished.connect(set_tags)
        document_consumption_finished.connect(set_storage_path)
        document_consumption_finished.connect(set_log_entry)
        document_consumption_finished.connect(add_to_index)
        document_consumption_finished.connect(run_workflow_added)
        document_updated.connect(run_workflow_updated)
        approval_added.connect(run_workflow_approval_added)
        approval_updated.connect(run_workflow_approval_updated)

        AppConfig.ready(self)
