import logging

from django.core.management.base import BaseCommand
from django.db.models.signals import post_save
from rich.progress import BarColumn
from rich.progress import Progress
from rich.progress import TaskProgressColumn
from rich.progress import TextColumn
from rich.progress import TimeRemainingColumn

from documents.management.commands.mixins import ProgressBarMixin
from documents.models import Document


class Command(ProgressBarMixin, BaseCommand):
    help = "This will rename all documents to match the latest filename format."

    def add_arguments(self, parser):
        self.add_argument_progress_bar_mixin(parser)

    def handle(self, *args, **options):
        self.handle_progress_bar_mixin(**options)
        logging.getLogger().handlers[0].level = logging.ERROR

        documents = Document.objects.all()
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            disable=self.no_progress_bar,
        ) as progress:
            task = progress.add_task("Renaming documents", total=documents.count())
            for document in documents:
                post_save.send(Document, instance=document, created=False)
                progress.update(task, advance=1)
