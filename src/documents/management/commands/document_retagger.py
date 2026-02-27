from __future__ import annotations

import logging
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from documents.classifier import load_classifier
from documents.management.commands.base import PaperlessCommand
from documents.models import Document
from documents.signals.handlers import set_correspondent
from documents.signals.handlers import set_document_type
from documents.signals.handlers import set_storage_path
from documents.signals.handlers import set_tags

if TYPE_CHECKING:
    from documents.models import Correspondent
    from documents.models import DocumentType
    from documents.models import StoragePath
    from documents.models import Tag

logger = logging.getLogger("paperless.management.retagger")


@dataclass(slots=True)
class RetaggerStats:
    """Cumulative counters updated as the retagger processes documents.

    Mutable by design -- fields are incremented in the processing loop.
    slots=True reduces per-instance memory overhead and speeds attribute access.
    """

    correspondents: int = 0
    document_types: int = 0
    tags_added: int = 0
    tags_removed: int = 0
    storage_paths: int = 0
    documents_processed: int = 0


@dataclass(slots=True)
class DocumentSuggestion:
    """Buffered classifier suggestions for a single document (suggest mode only).

    Mutable by design -- fields are assigned incrementally as each setter runs.
    """

    document: Document
    correspondent: Correspondent | None = None
    document_type: DocumentType | None = None
    tags_to_add: frozenset[Tag] = field(default_factory=frozenset)
    tags_to_remove: frozenset[Tag] = field(default_factory=frozenset)
    storage_path: StoragePath | None = None

    @property
    def has_suggestions(self) -> bool:
        return bool(
            self.correspondent is not None
            or self.document_type is not None
            or self.tags_to_add
            or self.tags_to_remove
            or self.storage_path is not None,
        )


def _build_stats_table(stats: RetaggerStats, *, suggest: bool) -> Table:
    """
    Build the live-updating stats table shown below the progress bar.

    In suggest mode the labels read "would set / would add" to make clear
    that nothing has been written to the database.
    """
    table = Table(box=None, padding=(0, 2), show_header=True, header_style="bold")

    table.add_column("Documents")
    table.add_column("Correspondents")
    table.add_column("Doc Types")
    table.add_column("Tags (+)")
    table.add_column("Tags (-)")
    table.add_column("Storage Paths")

    verb = "would set" if suggest else "set"

    table.add_row(
        str(stats.documents_processed),
        f"{stats.correspondents} {verb}",
        f"{stats.document_types} {verb}",
        f"+{stats.tags_added}",
        f"-{stats.tags_removed}",
        f"{stats.storage_paths} {verb}",
    )

    return table


def _build_suggestion_table(
    suggestions: list[DocumentSuggestion],
    base_url: str | None,
) -> Table:
    """
    Build the final suggestion table printed after the progress bar completes.

    Only documents with at least one suggestion are included.
    """
    table = Table(
        title="Suggested Changes",
        show_header=True,
        header_style="bold cyan",
        show_lines=True,
    )

    table.add_column("Document", style="bold", no_wrap=False, min_width=20)
    table.add_column("Correspondent")
    table.add_column("Doc Type")
    table.add_column("Tags")
    table.add_column("Storage Path")

    for suggestion in suggestions:
        if not suggestion.has_suggestions:
            continue

        doc = suggestion.document

        if base_url:
            doc_cell = Text()
            doc_cell.append(str(doc))
            doc_cell.append(f"\n{base_url}/documents/{doc.pk}", style="dim")
        else:
            doc_cell = Text(f"{doc} [{doc.pk}]")

        tag_parts: list[str] = []
        for tag in sorted(suggestion.tags_to_add, key=lambda t: t.name):
            tag_parts.append(f"[green]+{tag.name}[/green]")
        for tag in sorted(suggestion.tags_to_remove, key=lambda t: t.name):
            tag_parts.append(f"[red]-{tag.name}[/red]")
        tag_cell = Text.from_markup(", ".join(tag_parts)) if tag_parts else Text("-")

        table.add_row(
            doc_cell,
            str(suggestion.correspondent) if suggestion.correspondent else "-",
            str(suggestion.document_type) if suggestion.document_type else "-",
            tag_cell,
            str(suggestion.storage_path) if suggestion.storage_path else "-",
        )

    return table


def _build_summary_table(stats: RetaggerStats) -> Table:
    """Build the final applied-changes summary table."""
    table = Table(
        title="Retagger Summary",
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("Documents processed", str(stats.documents_processed))
    table.add_row("Correspondents set", str(stats.correspondents))
    table.add_row("Document types set", str(stats.document_types))
    table.add_row("Tags added", str(stats.tags_added))
    table.add_row("Tags removed", str(stats.tags_removed))
    table.add_row("Storage paths set", str(stats.storage_paths))

    return table


class Command(PaperlessCommand):
    help = (
        "Using the current classification model, assigns correspondents, tags "
        "and document types to all documents, effectively allowing you to "
        "back-tag all previously indexed documents with metadata created (or "
        "modified) after their initial import."
    )

    def add_arguments(self, parser) -> None:
        super().add_arguments(parser)
        parser.add_argument("-c", "--correspondent", default=False, action="store_true")
        parser.add_argument("-T", "--tags", default=False, action="store_true")
        parser.add_argument("-t", "--document_type", default=False, action="store_true")
        parser.add_argument("-s", "--storage_path", default=False, action="store_true")
        parser.add_argument("-i", "--inbox-only", default=False, action="store_true")
        parser.add_argument(
            "--use-first",
            default=False,
            action="store_true",
            help=(
                "By default this command will not try to assign a correspondent "
                "if more than one matches the document. Use this flag to pick "
                "the first match instead."
            ),
        )
        parser.add_argument(
            "-f",
            "--overwrite",
            default=False,
            action="store_true",
            help=(
                "Overwrite any previously set correspondent, document type, and "
                "remove tags that no longer match due to changed rules."
            ),
        )
        parser.add_argument(
            "--suggest",
            default=False,
            action="store_true",
            help="Show what would be changed without applying anything.",
        )
        parser.add_argument(
            "--base-url",
            help="Base URL used to build document links in suggest output.",
        )
        parser.add_argument(
            "--id-range",
            help="Restrict retagging to documents within this ID range (inclusive).",
            nargs=2,
            type=int,
        )

    def handle(self, *args, **options) -> None:
        suggest: bool = options["suggest"]
        overwrite: bool = options["overwrite"]
        use_first: bool = options["use_first"]
        base_url: str | None = options["base_url"]

        do_correspondent: bool = options["correspondent"]
        do_document_type: bool = options["document_type"]
        do_tags: bool = options["tags"]
        do_storage_path: bool = options["storage_path"]

        if not any([do_correspondent, do_document_type, do_tags, do_storage_path]):
            self.console.print(
                "[yellow]No classifier targets specified. "
                "Use -c, -T, -t, or -s to select what to retag.[/yellow]",
            )
            return

        if options["inbox_only"]:
            queryset = Document.objects.filter(tags__is_inbox_tag=True)
        else:
            queryset = Document.objects.all()

        if options["id_range"]:
            lo, hi = options["id_range"]
            queryset = queryset.filter(id__range=(lo, hi))

        documents = queryset.distinct()
        classifier = load_classifier()

        stats = RetaggerStats()
        suggestions: list[DocumentSuggestion] = []

        def render_stats() -> RenderableType:
            return _build_stats_table(stats, suggest=suggest)

        for document in self.track_with_stats(
            documents,
            description="Retagging...",
            stats_renderer=render_stats,
        ):
            suggestion = DocumentSuggestion(document=document)

            if do_correspondent:
                correspondent = set_correspondent(
                    None,
                    document,
                    classifier=classifier,
                    replace=overwrite,
                    use_first=use_first,
                    dry_run=suggest,
                )
                if correspondent is not None:
                    stats.correspondents += 1
                    suggestion.correspondent = correspondent

            if do_document_type:
                document_type = set_document_type(
                    None,
                    document,
                    classifier=classifier,
                    replace=overwrite,
                    use_first=use_first,
                    dry_run=suggest,
                )
                if document_type is not None:
                    stats.document_types += 1
                    suggestion.document_type = document_type

            if do_tags:
                tags_to_add, tags_to_remove = set_tags(
                    None,
                    document,
                    classifier=classifier,
                    replace=overwrite,
                    dry_run=suggest,
                )
                stats.tags_added += len(tags_to_add)
                stats.tags_removed += len(tags_to_remove)
                suggestion.tags_to_add = frozenset(tags_to_add)
                suggestion.tags_to_remove = frozenset(tags_to_remove)

            if do_storage_path:
                storage_path = set_storage_path(
                    None,
                    document,
                    classifier=classifier,
                    replace=overwrite,
                    use_first=use_first,
                    dry_run=suggest,
                )
                if storage_path is not None:
                    stats.storage_paths += 1
                    suggestion.storage_path = storage_path

            stats.documents_processed += 1

            if suggest:
                suggestions.append(suggestion)

        # Post-loop output
        if suggest:
            visible = [s for s in suggestions if s.has_suggestions]
            if visible:
                self.console.print(_build_suggestion_table(visible, base_url))
            else:
                self.console.print("[green]No changes suggested.[/green]")
        else:
            self.console.print(_build_summary_table(stats))
