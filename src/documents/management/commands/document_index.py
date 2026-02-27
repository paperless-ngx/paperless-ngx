from django.db import transaction

from documents.management.commands.base import PaperlessCommand
from documents.tasks import index_optimize
from documents.tasks import index_reindex


class Command(PaperlessCommand):
    help = "Manages the document index."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("command", choices=["reindex", "optimize"])

    def handle(self, *args, **options):
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
