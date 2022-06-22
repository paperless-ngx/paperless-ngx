import tqdm
from django.core.management.base import BaseCommand
from documents.tasks import redo_ocr


class Command(BaseCommand):

    help = """
        This will rename all documents to match the latest filename format.
    """.replace(
        "    ",
        "",
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown",
        )

        parser.add_argument(
            "documents",
            nargs="+",
            help="Document primary keys for re-processing OCR on",
        )

    def handle(self, *args, **options):
        doc_pks = tqdm.tqdm(
            options["documents"],
            disable=options["no_progress_bar"],
        )
        redo_ocr(doc_pks)
