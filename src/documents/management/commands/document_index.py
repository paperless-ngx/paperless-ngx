from django.db import transaction

from documents.management.commands.base import PaperlessCommand
from documents.tasks import index_optimize
from documents.tasks import index_reindex


class Command(PaperlessCommand):
    help = "Manages the document index."

    def add_arguments(self, parser):
        parser.add_argument("command", choices=["reindex", "optimize"])
        self.add_argument_progress_bar_mixin(parser)

    def handle(self, *args, **options):
        self.handle_progress_bar_mixin(**options)
        with transaction.atomic():
            if options["command"] == "reindex":
                index_reindex(
                    iter_wrapper=lambda docs: self.track(
                        docs,
                        description="Indexing documents...",
                    ),
                )
            elif options["command"] == "optimize":
                index_optimize()
