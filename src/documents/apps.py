from django.apps import AppConfig
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.utils.translation import gettext_lazy as _
from treenode.signals import post_delete_treenode
from treenode.signals import post_save_treenode


class DocumentsConfig(AppConfig):
    name = "documents"

    verbose_name = _("Documents")

    def ready(self):
        from documents.models import Tag
        from documents.signals import document_consumption_finished
        from documents.signals import document_updated
        from documents.signals.handlers import add_inbox_tags
        from documents.signals.handlers import add_to_index
        from documents.signals.handlers import run_workflows_added
        from documents.signals.handlers import run_workflows_updated
        from documents.signals.handlers import schedule_tag_tree_update
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
        document_updated.connect(run_workflows_updated)

        # treenode updates the entire tree on every save/delete via hooks
        # so disconnect for Tags and run once-per-transaction.
        post_save.disconnect(
            post_save_treenode,
            sender=Tag,
            dispatch_uid="post_save_treenode",
        )
        post_delete.disconnect(
            post_delete_treenode,
            sender=Tag,
            dispatch_uid="post_delete_treenode",
        )
        post_save.connect(
            schedule_tag_tree_update,
            sender=Tag,
            dispatch_uid="paperless_tag_mark_dirty_save",
        )
        post_delete.connect(
            schedule_tag_tree_update,
            sender=Tag,
            dispatch_uid="paperless_tag_mark_dirty_delete",
        )

        import documents.schema  # noqa: F401

        AppConfig.ready(self)
