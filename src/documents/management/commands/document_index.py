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
        parser.add_argument(
            "--heap-size-mb",
            type=int,
            default=None,
            help=(
                "Tantivy writer memory budget in MB for a full reindex "
                "(split across writer threads). Defaults to 512MB; lower "
                "this on memory-constrained hosts. Larger values buffer "
                "more documents before flushing a segment, deferring "
                "merge work rather than avoiding it."
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
                ).prefetch_related(
                    "tags",
                    "notes__user",
                    "custom_fields__field",
                    "versions",
                )
                total = documents.count()
                rebuild_kwargs = {}
                if options.get("heap_size_mb") is not None:
                    rebuild_kwargs["writer_heap_bytes"] = (
                        options["heap_size_mb"] * 1_000_000
                    )
                get_backend().rebuild(
                    documents,
                    iter_wrapper=lambda pairs: self.track(
                        pairs,
                        description="Indexing documents...",
                        total=total,
                    ),
                    **rebuild_kwargs,
                )
                reset_backend()

            elif options["command"] == "optimize":
                logger.info(
                    "document_index optimize is a no-op — Tantivy manages "
                    "segment merging automatically.",
                )
