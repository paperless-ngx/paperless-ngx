import dataclasses
import multiprocessing
from typing import Final

import rapidfuzz
import tqdm
from django.core.management import BaseCommand
from django.core.management import CommandError

from documents.models import Document


@dataclasses.dataclass(frozen=True)
class _WorkPackage:
    first_doc: Document
    second_doc: Document


@dataclasses.dataclass(frozen=True)
class _WorkResult:
    doc_one_pk: int
    doc_two_pk: int
    ratio: float

    def __lt__(self, other: "_WorkResult") -> bool:
        return self.doc_one_pk < other.doc_one_pk


def _process_and_match(work: _WorkPackage) -> _WorkResult:
    """
    Does basic processing of document content, gets the basic ratio
    and returns the result package
    """
    # Normalize the string some, lower case, whitespace, etc
    first_string = rapidfuzz.utils.default_process(work.first_doc.content)
    second_string = rapidfuzz.utils.default_process(work.second_doc.content)

    # Basic matching ratio
    match = rapidfuzz.fuzz.ratio(first_string, second_string)

    return _WorkResult(work.first_doc.pk, work.second_doc.pk, match)


class Command(BaseCommand):
    help = "Searches for documents where the content almost matches"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ratio",
            default=85.0,
            type=float,
            help="Ratio to consider documents a match",
        )
        parser.add_argument(
            "--processes",
            default=4,
            type=int,
            help="Number of processes to distribute work amongst",
        )
        parser.add_argument(
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown",
        )

    def handle(self, *args, **options):
        RATIO_MIN: Final[float] = 0.0
        RATIO_MAX: Final[float] = 100.0

        opt_ratio = options["ratio"]
        checked_pairs: set[tuple[int, int]] = set()
        work_pkgs: list[_WorkPackage] = []

        # Ratio is a float from 0.0 to 100.0
        if opt_ratio < RATIO_MIN or opt_ratio > RATIO_MAX:
            raise CommandError("The ratio must be between 0 and 100")

        if options["processes"] < 1:
            raise CommandError("There must be at least 1 process")

        all_docs = Document.objects.all().order_by("id")

        # Build work packages for processing
        for first_doc in all_docs:
            for second_doc in all_docs:
                # doc to doc is obviously not useful
                if first_doc.pk == second_doc.pk:
                    continue
                # Skip matching which have already been matched together
                # doc 1 to doc 2 is the same as doc 2 to doc 1
                if (first_doc.pk, second_doc.pk) in checked_pairs or (
                    second_doc.pk,
                    first_doc.pk,
                ) in checked_pairs:
                    continue
                checked_pairs.update(
                    [(first_doc.pk, second_doc.pk), (second_doc.pk, first_doc.pk)],
                )

                work_pkgs.append(_WorkPackage(first_doc, second_doc))

        # Don't spin up a pool of 1 process
        if options["processes"] == 1:
            results = []
            for work in tqdm.tqdm(work_pkgs, disable=options["no_progress_bar"]):
                results.append(_process_and_match(work))
        else:
            with multiprocessing.Pool(processes=options["processes"]) as pool:
                results = list(
                    tqdm.tqdm(
                        pool.imap_unordered(_process_and_match, work_pkgs),
                        total=len(work_pkgs),
                        disable=options["no_progress_bar"],
                    ),
                )

        # Check results
        messages = []
        for result in sorted(results):
            if result.ratio >= opt_ratio:
                messages.append(
                    self.style.NOTICE(
                        f"Document {result.doc_one_pk} fuzzy match"
                        f" to {result.doc_two_pk} (confidence {result.ratio:.3f})",
                    ),
                )

        if len(messages) == 0:
            messages.append(
                self.style.SUCCESS("No matches found"),
            )
        self.stdout.writelines(
            messages,
        )
