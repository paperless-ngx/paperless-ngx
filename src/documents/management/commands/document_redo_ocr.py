import logging
import shutil
from pathlib import Path
from typing import Type

import tqdm
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from documents.models import Document
from documents.parsers import DocumentParser
from documents.parsers import get_parser_class_for_mime_type
from documents.parsers import ParseError


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

        logging.getLogger().handlers[0].level = logging.ERROR

        all_docs = Document.objects.all()

        for doc_pk in tqdm.tqdm(args.documents, disable=options["no_progress_bar"]):
            try:
                self.stdout.write(self.style.INFO(f"Parsing document {doc_pk}"))
                doc: Document = all_docs.get(pk=doc_pk)
            except ObjectDoesNotExist:
                self.stdout.write(self.style.ERROR(f"Document {doc_pk} does not exist"))
                continue

            # Get the correct parser for this mime type
            parser_class: Type[DocumentParser] = get_parser_class_for_mime_type(
                doc.mime_type,
            )
            document_parser: DocumentParser = parser_class(
                "redo-ocr",
            )

            # Create a file path to copy the original file to for working on
            temp_file = (Path(document_parser.tempdir) / Path("new-ocr-file")).resolve()

            shutil.copy(doc.source_path, temp_file)

            try:
                # Try to re-parse the document into text
                document_parser.parse(str(temp_file), doc.mime_type)

                doc.content = document_parser.get_text()
                doc.save()

            except ParseError as e:
                self.stdout.write(self.style.ERROR(f"Error parsing document: {e}"))
            finally:
                # Remove the file path if it was created
                if temp_file.exists() and temp_file.is_file():
                    temp_file.unlink()
