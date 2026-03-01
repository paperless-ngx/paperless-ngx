"""Management command to check the document archive for issues."""

from __future__ import annotations

import logging
from typing import Any

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from documents.management.commands.base import PaperlessCommand
from documents.models import Document
from documents.sanity_checker import SanityCheckMessages
from documents.sanity_checker import check_sanity

_LEVEL_STYLE: dict[int, tuple[str, str]] = {
    logging.ERROR: ("bold red", "ERROR"),
    logging.WARNING: ("yellow", "WARN"),
    logging.INFO: ("dim", "INFO"),
}


class Command(PaperlessCommand):
    help = "This command checks your document archive for issues."

    def _render_results(self, messages: SanityCheckMessages) -> None:
        """Render sanity check results as a Rich table."""
        console = self.console

        if len(messages) == 0:
            console.print(
                Panel(
                    "[green]No issues detected.[/green]",
                    title="Sanity Check",
                    border_style="green",
                ),
            )
            return

        # Build a lookup for document titles
        doc_pks = [pk for pk in messages.document_pks() if pk is not None]
        titles: dict[int, str] = {}
        if doc_pks:
            titles = dict(
                Document.global_objects.filter(pk__in=doc_pks)
                .only("pk", "title")
                .values_list("pk", "title"),
            )

        table = Table(
            title="Sanity Check Results",
            show_lines=True,
            title_style="bold",
        )
        table.add_column("Level", width=7, no_wrap=True)
        table.add_column("Document", min_width=20)
        table.add_column("Issue", ratio=1)

        for doc_pk, doc_messages in messages.iter_messages():
            if doc_pk is not None:
                title = titles.get(doc_pk, "Unknown")
                doc_label = f"#{doc_pk} {title}"
            else:
                doc_label = "(global)"

            for msg in doc_messages:
                style, label = _LEVEL_STYLE.get(
                    msg["level"],
                    ("dim", "INFO"),
                )
                table.add_row(
                    Text(label, style=style),
                    doc_label,
                    msg["message"],
                )

        console.print(table)

        # Summary line
        parts: list[str] = []
        if messages.has_error:
            parts.append("[bold red]errors[/bold red]")
        if messages.has_warning:
            parts.append("[yellow]warnings[/yellow]")
        summary = " and ".join(parts) if parts else "infos"
        console.print(f"\nFound {len(messages)} document(s) with {summary}.")

    def handle(self, *args: Any, **options: Any) -> None:
        messages = check_sanity(
            scheduled=False,
            iter_wrapper=lambda docs: self.track(
                docs,
                description="Checking documents...",
            ),
        )
        self._render_results(messages)
