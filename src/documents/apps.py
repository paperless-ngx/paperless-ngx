import logging

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger("paperless.documents")


class DocumentsConfig(AppConfig):
    name = "documents"

    verbose_name = _("Documents")

    def ready(self):
        from documents.signals import document_consumption_finished
        from documents.signals import document_updated
        from documents.signals.handlers import add_inbox_tags
        from documents.signals.handlers import add_or_update_document_in_llm_index
        from documents.signals.handlers import add_to_index
        from documents.signals.handlers import run_workflows_added
        from documents.signals.handlers import run_workflows_updated
        from documents.signals.handlers import set_correspondent
        from documents.signals.handlers import set_document_type
        from documents.signals.handlers import set_storage_path
        from documents.signals.handlers import set_tags

        document_consumption_finished.connect(add_inbox_tags)
        document_consumption_finished.connect(set_correspondent)
        document_consumption_finished.connect(set_document_type)
        document_consumption_finished.connect(set_tags)
        document_consumption_finished.connect(set_storage_path)
        document_consumption_finished.connect(add_to_index)
        document_consumption_finished.connect(run_workflows_added)
        document_consumption_finished.connect(add_or_update_document_in_llm_index)
        document_updated.connect(run_workflows_updated)

        import documents.schema  # noqa: F401

        self._check_content_length_backfill()

        AppConfig.ready(self)

    def _check_content_length_backfill(self):
        """
        Warn if there are documents missing content_length.
        This can happen after upgrading from a version without content_length
        on a database with more than 1000 documents.
        """
        try:
            from documents.models import Document

            missing_count = Document.objects.filter(content_length__isnull=True).count()
            if missing_count > 0:
                logger.warning(
                    f"{missing_count} documents are missing the content_length field. "
                    "Statistics performance may be degraded. "
                    "Run 'python manage.py backfill_content_length' to fix this.",
                )
        except Exception:
            # Table might not exist yet during migrations
            pass
