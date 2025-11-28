from django.core.management import BaseCommand
from django.db import transaction

from documents.management.commands.mixins import ProgressBarMixin
from documents.tasks import llmindex_index


class Command(ProgressBarMixin, BaseCommand):
    help = "Manages the LLM-based vector index for Paperless."

    def add_arguments(self, parser):
        parser.add_argument("command", choices=["rebuild", "update"])
        self.add_argument_progress_bar_mixin(parser)

    def handle(self, *args, **options):
        self.handle_progress_bar_mixin(**options)
        with transaction.atomic():
            llmindex_index(
                progress_bar_disable=self.no_progress_bar,
                rebuild=options["command"] == "rebuild",
                scheduled=False,
            )
