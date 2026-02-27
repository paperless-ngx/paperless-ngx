import logging

from django.conf import settings

from documents.management.commands.base import PaperlessCommand
from documents.models import Document
from documents.tasks import update_document_content_maybe_archive_file

logger = logging.getLogger("paperless.management.archiver")


class Command(PaperlessCommand):
    help = (
        "Using the current classification model, assigns correspondents, tags "
        "and document types to all documents, effectively allowing you to "
        "back-tag all previously indexed documents with metadata created (or "
        "modified) after their initial import."
    )

    supports_multiprocessing = True

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "-f",
            "--overwrite",
            default=False,
            action="store_true",
            help=(
                "Recreates the archived document for documents that already "
                "have an archived version."
            ),
        )
        parser.add_argument(
            "-d",
            "--document",
            default=None,
            type=int,
            required=False,
            help=(
                "Specify the ID of a document, and this command will only "
                "run on this specific document."
            ),
        )

    def handle(self, *args, **options):
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

        overwrite = options["overwrite"]

        if options["document"]:
            documents = Document.objects.filter(pk=options["document"])
        else:
            documents = Document.objects.all()

        document_ids = [
            doc.id for doc in documents if overwrite or not doc.has_archive_version
        ]

        try:
            logging.getLogger().handlers[0].level = logging.ERROR

            for result in self.process_parallel(
                update_document_content_maybe_archive_file,
                document_ids,
                description="Archiving...",
            ):
                if result.error:
                    self.console.print(
                        f"[red]Failed document {result.item}: {result.error}[/red]",
                    )
        except KeyboardInterrupt:  # pragma: no cover
            self.console.print("[yellow]Aborting...[/yellow]")
