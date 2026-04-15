import dataclasses
from itertools import combinations
from typing import Final

import rapidfuzz
from django.core.management import CommandError
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from documents.management.commands.base import PaperlessCommand
from documents.models import Document


@dataclasses.dataclass(frozen=True, slots=True)
class _WorkPackage:
    pk_a: int
    content_a: str
    pk_b: int
    content_b: str
    score_cutoff: float


@dataclasses.dataclass(frozen=True, slots=True)
class _WorkResult:
    doc_one_pk: int
    doc_two_pk: int
    ratio: float


def _process_and_match(work: _WorkPackage) -> _WorkResult:
    """
    Process document content and compute the fuzzy ratio.
    score_cutoff lets rapidfuzz short-circuit when the score cannot reach the threshold.
    """
    first_string = rapidfuzz.utils.default_process(work.content_a)
    second_string = rapidfuzz.utils.default_process(work.content_b)
    ratio = rapidfuzz.fuzz.ratio(
        first_string,
        second_string,
        score_cutoff=work.score_cutoff,
    )
    return _WorkResult(work.pk_a, work.pk_b, ratio)


class Command(PaperlessCommand):
    help = "Searches for documents where the content almost matches"

    supports_progress_bar = True
    supports_multiprocessing = True

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--ratio",
            default=85.0,
            type=float,
            help="Ratio to consider documents a match",
        )
        parser.add_argument(
            "--delete",
            default=False,
            action="store_true",
            help="If set, one document of matches above the ratio WILL BE DELETED",
        )
        parser.add_argument(
            "--yes",
            default=False,
            action="store_true",
            help="Skip the confirmation prompt when used with --delete",
        )

    def _render_results(
        self,
        matches: list[_WorkResult],
        *,
        opt_ratio: float,
        do_delete: bool,
    ) -> list[int]:
        """Render match results as a Rich table. Returns list of PKs to delete."""
        if not matches:
            self.console.print(
                Panel(
                    "[green]No duplicate documents found.[/green]",
                    title="Fuzzy Match",
                    border_style="green",
                ),
            )
            return []

        # Fetch titles for matched documents in a single query.
        all_pks = {pk for m in matches for pk in (m.doc_one_pk, m.doc_two_pk)}
        titles: dict[int, str] = dict(
            Document.objects.filter(pk__in=all_pks)
            .only("pk", "title")
            .values_list("pk", "title"),
        )

        table = Table(
            title=f"Fuzzy Matches (threshold: {opt_ratio:.1f}%)",
            show_lines=True,
            title_style="bold",
        )
        table.add_column("#", style="dim", width=4, no_wrap=True)
        table.add_column("Document A", min_width=24)
        table.add_column("Document B", min_width=24)
        table.add_column("Similarity", width=11, justify="right")

        maybe_delete_ids: list[int] = []

        for i, match_result in enumerate(matches, 1):
            pk_a = match_result.doc_one_pk
            pk_b = match_result.doc_two_pk
            ratio = match_result.ratio

            if ratio >= 97.0:
                ratio_style = "bold red"
            elif ratio >= 92.0:
                ratio_style = "red"
            elif ratio >= 88.0:
                ratio_style = "yellow"
            else:
                ratio_style = "dim"

            table.add_row(
                str(i),
                f"[dim]#{pk_a}[/dim] {titles.get(pk_a, 'Unknown')}",
                f"[dim]#{pk_b}[/dim] {titles.get(pk_b, 'Unknown')}",
                Text(f"{ratio:.1f}%", style=ratio_style),
            )
            maybe_delete_ids.append(pk_b)

        self.console.print(table)

        summary = f"Found [bold]{len(matches)}[/bold] matching pair(s)."
        if do_delete:
            summary += f" [yellow]{len(maybe_delete_ids)}[/yellow] document(s) will be deleted."
        self.console.print(summary)

        return maybe_delete_ids

    def handle(self, *args, **options):
        RATIO_MIN: Final[float] = 0.0
        RATIO_MAX: Final[float] = 100.0

        opt_ratio = options["ratio"]

        if opt_ratio < RATIO_MIN or opt_ratio > RATIO_MAX:
            raise CommandError("The ratio must be between 0 and 100")

        if options["delete"]:
            self.console.print(
                Panel(
                    "[bold yellow]WARNING:[/bold yellow] This run is configured to delete"
                    " documents. One document from each matched pair WILL BE PERMANENTLY DELETED.",
                    title="Delete Mode",
                    border_style="red",
                ),
            )

        # Load only the fields we need -- avoids fetching title, archive_checksum, etc.
        slim_docs: list[tuple[int, str]] = list(
            Document.objects.only("id", "content")
            .order_by("id")
            .values_list("id", "content"),
        )

        # combinations() generates each unique pair exactly once -- no checked_pairs set needed.
        # The total is computed cheaply so the progress bar can start immediately without
        # materialising all pairs up front (n*(n-1)/2 can be hundreds of thousands).
        n = len(slim_docs)
        total_pairs = n * (n - 1) // 2

        def _work_gen():
            for (pk_a, ca), (pk_b, cb) in combinations(slim_docs, 2):
                if ca.strip() and cb.strip():
                    yield _WorkPackage(pk_a, ca, pk_b, cb, opt_ratio)

        def _iter_matches():
            if self.process_count == 1:
                for work in self.track(
                    _work_gen(),
                    description="Matching...",
                    total=total_pairs,
                ):
                    result = _process_and_match(work)
                    if result.ratio >= opt_ratio:
                        yield result
            else:  # pragma: no cover
                work_pkgs = list(_work_gen())
                for proc_result in self.process_parallel(
                    _process_and_match,
                    work_pkgs,
                    description="Matching...",
                ):
                    if proc_result.error:
                        self.console.print(
                            f"[red]Failed: {proc_result.error}[/red]",
                        )
                    elif (
                        proc_result.result is not None
                        and proc_result.result.ratio >= opt_ratio
                    ):
                        yield proc_result.result

        matches = sorted(_iter_matches(), key=lambda m: m.ratio, reverse=True)
        maybe_delete_ids = self._render_results(
            matches,
            opt_ratio=opt_ratio,
            do_delete=options["delete"],
        )

        if options["delete"] and maybe_delete_ids:
            confirmed = options["yes"]
            if not confirmed:
                self.console.print(
                    f"\nDelete [bold]{len(maybe_delete_ids)}[/bold] document(s)? "
                    "[bold]\\[y/N][/bold] ",
                    end="",
                )
                answer = input().strip().lower()
                confirmed = answer in {"y", "yes"}

            if confirmed:
                self.console.print(
                    f"[red]Deleting {len(maybe_delete_ids)} document(s)...[/red]",
                )
                Document.objects.filter(pk__in=maybe_delete_ids).delete()
                self.console.print("[green]Done.[/green]")
            else:
                self.console.print("[yellow]Deletion cancelled.[/yellow]")
