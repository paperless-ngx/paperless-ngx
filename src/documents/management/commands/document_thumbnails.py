import logging
import shutil

from documents.management.commands.base import PaperlessCommand
from documents.models import Document
from documents.parsers import get_parser_class_for_mime_type

logger = logging.getLogger("paperless.management.thumbnails")


def _process_document(doc_id: int) -> None:
    document: Document = Document.objects.get(id=doc_id)
    parser_class = get_parser_class_for_mime_type(document.mime_type)

    if parser_class is None:
        logger.warning(
            "%s: No parser for mime type %s",
            document,
            document.mime_type,
        )
        return

    parser = parser_class(logging_group=None)

    try:
        thumb = parser.get_thumbnail(
            document.source_path,
            document.mime_type,
            document.get_public_filename(),
        )
        shutil.move(thumb, document.thumbnail_path)
    finally:
        parser.cleanup()


class Command(PaperlessCommand):
    help = "This will regenerate the thumbnails for all documents."

    supports_multiprocessing = True

    def add_arguments(self, parser) -> None:
        super().add_arguments(parser)
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
        logging.getLogger().handlers[0].level = logging.ERROR

        if options["document"]:
            documents = Document.objects.filter(pk=options["document"])
        else:
            documents = Document.objects.all()

        ids = list(documents.values_list("id", flat=True))

        for result in self.process_parallel(
            _process_document,
            ids,
            description="Regenerating thumbnails...",
        ):
            if result.error:  # pragma: no cover
                self.console.print(
                    f"[red]Failed document {result.item}: {result.error}[/red]",
                )
