from django.apps import AppConfig

from paperless_embeddings.signals import handle_document_deletion
from paperless_embeddings.signals import handle_document_save


class PaperlessMistralOcrConfig(AppConfig):
    name = "paperless_mistralocr"

    def ready(self):
        from django.db.models.signals import post_delete
        from django.db.models.signals import post_save

        from documents.models import Document

        # Connect document signals for embedding management
        post_delete.connect(handle_document_deletion, sender=Document)
        post_save.connect(handle_document_save, sender=Document)

        AppConfig.ready(self)
