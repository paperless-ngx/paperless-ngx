from auditlog.models import LogEntry
from django.db import transaction

from documents.management.commands.base import PaperlessCommand


class Command(PaperlessCommand):
    """Prune the audit logs of objects that no longer exist."""

    help = "Prunes the audit logs of objects that no longer exist."

    def handle(self, *args, **options):
        with transaction.atomic():
            for log_entry in self.track(
                LogEntry.objects.all(),
                description="Pruning audit logs...",
            ):
                model_class = log_entry.content_type.model_class()
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
                    self.console.print(
                        f"Deleted audit log entry for "
                        f"{model_class.__name__} #{log_entry.object_id}",
                        style="yellow",
                    )
