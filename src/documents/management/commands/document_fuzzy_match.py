import dataclasses
from typing import Final

import rapidfuzz
from django.core.management import CommandError

from documents.management.commands.base import PaperlessCommand
from documents.models import Document


@dataclasses.dataclass(frozen=True, slots=True)
class _WorkPackage:
    first_doc: Document
    second_doc: Document


@dataclasses.dataclass(frozen=True, slots=True)
class _WorkResult:
    doc_one_pk: int
    doc_two_pk: int
    ratio: float

    def __lt__(self, other: "_WorkResult") -> bool:
        return self.doc_one_pk < other.doc_one_pk


def _process_and_match(work: _WorkPackage) -> _WorkResult:
    """
    Does basic processing of document content, gets the basic ratio
    and returns the result package.
    """
    first_string = rapidfuzz.utils.default_process(work.first_doc.content)
    second_string = rapidfuzz.utils.default_process(work.second_doc.content)

    match = rapidfuzz.fuzz.ratio(first_string, second_string)

    return _WorkResult(work.first_doc.pk, work.second_doc.pk, match)


class Command(PaperlessCommand):
    help = "Searches for documents where the content almost matches"

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
        checked_pairs: set[tuple[int, int]] = set()
        work_pkgs: list[_WorkPackage] = []

        if opt_ratio < RATIO_MIN or opt_ratio > RATIO_MAX:
            raise CommandError("The ratio must be between 0 and 100")

        all_docs = Document.objects.all().order_by("id")

        for first_doc in all_docs:
            for second_doc in all_docs:
                if first_doc.pk == second_doc.pk:
                    continue
                if first_doc.content.strip() == "" or second_doc.content.strip() == "":
                    continue
                doc_1_to_doc_2 = (first_doc.pk, second_doc.pk)
                doc_2_to_doc_1 = doc_1_to_doc_2[::-1]
                if doc_1_to_doc_2 in checked_pairs or doc_2_to_doc_1 in checked_pairs:
                    continue
                checked_pairs.update([doc_1_to_doc_2, doc_2_to_doc_1])
                work_pkgs.append(_WorkPackage(first_doc, second_doc))

        results: list[_WorkResult] = []
        if self.process_count == 1:
            for work in self.track(work_pkgs, description="Matching..."):
                results.append(_process_and_match(work))
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
                elif proc_result.result is not None:
                    results.append(proc_result.result)

        messages: list[str] = []
        maybe_delete_ids: list[int] = []
        for match_result in sorted(results):
            if match_result.ratio >= opt_ratio:
                messages.append(
                    self.style.NOTICE(
                        f"Document {match_result.doc_one_pk} fuzzy match"
                        f" to {match_result.doc_two_pk}"
                        f" (confidence {match_result.ratio:.3f})\n",
                    ),
                )
                maybe_delete_ids.append(match_result.doc_two_pk)

        if len(messages) == 0:
            messages.append(self.style.SUCCESS("No matches found\n"))
        self.stdout.writelines(messages)

        if options["delete"]:
            self.stdout.write(
                self.style.NOTICE(
                    f"Deleting {len(maybe_delete_ids)} documents based on ratio matches",
                ),
            )
            Document.objects.filter(pk__in=maybe_delete_ids).delete()
