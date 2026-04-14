import dataclasses
from itertools import combinations
from typing import Final

import rapidfuzz
from django.core.management import CommandError

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

    def __lt__(self, other: "_WorkResult") -> bool:
        return self.doc_one_pk < other.doc_one_pk


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

    def handle(self, *args, **options):
        RATIO_MIN: Final[float] = 0.0
        RATIO_MAX: Final[float] = 100.0

        if options["delete"]:
            self.stdout.write(
                self.style.WARNING(
                    "The command is configured to delete documents.  Use with caution",
                ),
            )

        opt_ratio = options["ratio"]

        if opt_ratio < RATIO_MIN or opt_ratio > RATIO_MAX:
            raise CommandError("The ratio must be between 0 and 100")

        # Load only the fields we need -- avoids fetching title, archive_checksum, etc.
        slim_docs: list[tuple[int, str]] = list(
            Document.objects.only("id", "content")
            .order_by("id")
            .values_list("id", "content"),
        )

        # combinations() generates each unique pair exactly once -- no checked_pairs set needed.
        work_pkgs: list[_WorkPackage] = [
            _WorkPackage(pk_a, ca, pk_b, cb, opt_ratio)
            for (pk_a, ca), (pk_b, cb) in combinations(slim_docs, 2)
            if ca.strip() and cb.strip()
        ]

        def _iter_matches():
            if self.process_count == 1:
                for work in self.track(work_pkgs, description="Matching..."):
                    result = _process_and_match(work)
                    if result.ratio >= opt_ratio:
                        yield result
            else:  # pragma: no cover
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

        messages: list[str] = []
        maybe_delete_ids: list[int] = []
        for match_result in sorted(_iter_matches()):
            messages.append(
                self.style.NOTICE(
                    f"Document {match_result.doc_one_pk} fuzzy match"
                    f" to {match_result.doc_two_pk}"
                    f" (confidence {match_result.ratio:.3f})\n",
                ),
            )
            maybe_delete_ids.append(match_result.doc_two_pk)

        if not messages:
            messages.append(self.style.SUCCESS("No matches found\n"))
        self.stdout.writelines(messages)

        if options["delete"]:
            self.stdout.write(
                self.style.NOTICE(
                    f"Deleting {len(maybe_delete_ids)} documents based on ratio matches",
                ),
            )
            Document.objects.filter(pk__in=maybe_delete_ids).delete()
