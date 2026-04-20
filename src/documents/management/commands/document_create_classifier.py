from __future__ import annotations

import time

from documents.management.commands.base import PaperlessCommand
from documents.tasks import train_classifier


class Command(PaperlessCommand):
    help = (
        "Trains the classifier on your data and saves the resulting models to a "
        "file. The document consumer will then automatically use this new model."
    )
    supports_progress_bar = False
    supports_multiprocessing = False

    def handle(self, *args, **options) -> None:
        start = time.monotonic()

        with (
            self.buffered_logging("paperless.tasks"),
            self.buffered_logging("paperless.classifier"),
        ):
            train_classifier(
                status_callback=lambda msg: self.console.print(f"  {msg}"),
            )

        elapsed = time.monotonic() - start
        self.console.print(
            f"[green]✓[/green] Classifier training complete ({elapsed:.1f}s)",
        )
