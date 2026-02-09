from auditlog.models import LogEntry
from django.core.management.base import BaseCommand
from django.db import transaction
from rich.console import Console
from rich.progress import BarColumn
from rich.progress import Progress
from rich.progress import TaskProgressColumn
from rich.progress import TextColumn
from rich.progress import TimeRemainingColumn

from documents.management.commands.mixins import ProgressBarMixin


class Command(BaseCommand, ProgressBarMixin):
    """
    Prune the audit logs of objects that no longer exist.
    """

    help = "Prunes the audit logs of objects that no longer exist."

    def add_arguments(self, parser):
        self.add_argument_progress_bar_mixin(parser)

    def handle(self, **options):
        self.handle_progress_bar_mixin(**options)
        console = Console()
        with transaction.atomic():
            log_entries = LogEntry.objects.all()
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console,
                disable=self.no_progress_bar,
            ) as progress:
                task = progress.add_task(
                    "Pruning audit logs",
                    total=log_entries.count(),
                )
                for log_entry in log_entries:
                    model_class = log_entry.content_type.model_class()
                    # use global_objects for SoftDeleteModel
                    objects = (
                        model_class.global_objects
                        if hasattr(model_class, "global_objects")
                        else model_class.objects
                    )
                    if (
                        log_entry.object_id
                        and not objects.filter(pk=log_entry.object_id).exists()
                    ):
                        log_entry.delete()
                        console.print(
                            self.style.NOTICE(
                                f"Deleted audit log entry for {model_class.__name__} #{log_entry.object_id}",
                            ),
                        )
                    progress.update(task, advance=1)
