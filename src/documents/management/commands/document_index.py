from django.conf import settings
from django.db import transaction

from documents.management.commands.base import PaperlessCommand
from documents.tasks import index_optimize
from documents.tasks import index_reindex


class Command(PaperlessCommand):
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

    def handle(self, *args, **options):
        with transaction.atomic():
            if options["command"] == "reindex":
                if options.get("recreate"):
                    from documents.search import wipe_index

                    wipe_index(settings.INDEX_DIR)
                index_reindex(
                    iter_wrapper=lambda docs: self.track(
                        docs,
                        description="Indexing documents...",
                    ),
                )
            elif options["command"] == "optimize":
                index_optimize()
