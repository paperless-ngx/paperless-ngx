from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DocumentsConfig(AppConfig):

    name = "documents"

    verbose_name = _("Documents")

    def ready(self):
        from .signals import document_consumption_finished
        from .signals.handlers import add_inbox_tags
        from .signals.handlers import add_to_index
        from .signals.handlers import set_correspondent
        from .signals.handlers import set_document_type
        from .signals.handlers import set_log_entry
        from .signals.handlers import set_storage_path
        from .signals.handlers import set_tags

        document_consumption_finished.connect(add_inbox_tags)
        document_consumption_finished.connect(set_correspondent)
        document_consumption_finished.connect(set_document_type)
        document_consumption_finished.connect(set_tags)
        document_consumption_finished.connect(set_storage_path)
        document_consumption_finished.connect(set_log_entry)
        document_consumption_finished.connect(add_to_index)

        AppConfig.ready(self)
