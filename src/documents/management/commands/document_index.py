import logging

from django.conf import settings
from django.db import transaction

from documents.management.commands.base import PaperlessCommand
from documents.models import Document
from documents.search import get_backend
from documents.search import needs_rebuild
from documents.search import reset_backend
from documents.search import wipe_index

logger = logging.getLogger("paperless.management.document_index")


class Command(PaperlessCommand):
    """
    Django management command for search index operations.

    Provides subcommands for reindexing documents and optimizing the search index.
    Supports conditional reindexing based on schema version and language changes.
    """

    help = "Manages the document index."

    supports_progress_bar = True
    supports_multiprocessing = False

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("command", choices=["reindex", "optimize"])
        parser.add_argument(
            "--recreate",
            action="store_true",
            default=False,
            help="Wipe and recreate the index from scratch (only used with reindex).",
        )
        parser.add_argument(
            "--if-needed",
            action="store_true",
            default=False,
            help=(
                "Skip reindex if the index is already up to date. "
                "Checks schema version and search language sentinels. "
                "Safe to run on every startup or upgrade."
            ),
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            if options["command"] == "reindex":
                if options.get("if_needed") and not needs_rebuild(settings.INDEX_DIR):
                    self.stdout.write("Search index is up to date.")
                    return
                if options.get("recreate"):
                    wipe_index(settings.INDEX_DIR)

                documents = Document.objects.select_related(
                    "correspondent",
                    "document_type",
                    "storage_path",
                    "owner",
                ).prefetch_related("tags", "notes", "custom_fields", "versions")
                get_backend().rebuild(
                    documents,
                    iter_wrapper=lambda docs: self.track(
                        docs,
                        description="Indexing documents...",
                    ),
                )
                reset_backend()

            elif options["command"] == "optimize":
                logger.info(
                    "document_index optimize is a no-op — Tantivy manages "
                    "segment merging automatically.",
                )
