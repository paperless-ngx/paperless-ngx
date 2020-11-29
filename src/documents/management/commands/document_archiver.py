import hashlib
import multiprocessing

import ocrmypdf
import logging
import os
import shutil
import uuid

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from ocrmypdf import Verbosity
from whoosh.writing import AsyncWriter

from documents.models import Document
from ... import index
from ...mixins import Renderable
from ...parsers import get_parser_class_for_mime_type


def handle_document(document):
    mime_type = document.mime_type

    parser_class = get_parser_class_for_mime_type(mime_type)

    parser = parser_class(logging_group=uuid.uuid4())
    parser.parse(document.source_path, mime_type)
    if parser.get_archive_path():
        shutil.copy(parser.get_archive_path(), document.archive_path)
        with document.archive_file as f:
            document.archive_checksum = hashlib.md5(f.read()).hexdigest()
    else:
        logging.getLogger(__name__).warning(
            f"Parser {parser} did not produce an archived document "
            f"for {document.file_name}"
        )

    if parser.get_text():
        document.content = parser.get_text()
    document.save()

    parser.cleanup()


class Command(Renderable, BaseCommand):

    help = """
        Using the current classification model, assigns correspondents, tags
        and document types to all documents, effectively allowing you to
        back-tag all previously indexed documents with metadata created (or
        modified) after their initial import.
    """.replace("    ", "")

    def __init__(self, *args, **kwargs):
        self.verbosity = 0
        BaseCommand.__init__(self, *args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument(
            "-f", "--overwrite",
            default=False,
            action="store_true",
            help="Recreates the archived document for documents that already "
                 "have an archived version."
        )

    def handle(self, *args, **options):

        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)

        overwrite = options["overwrite"]

        documents = Document.objects.all()

        documents_to_process = filter(
            lambda d: overwrite or not os.path.exists(d.archive_path),
            documents
        )

        with multiprocessing.Pool(processes=settings.TASK_WORKERS) as pool:
            list(
                pool.imap(
                    handle_document,
                    list(documents_to_process)
                )
            )

        ix = index.open_index()
        with AsyncWriter(ix) as writer:
            for d in documents_to_process:
                index.update_document(writer, d)
