import logging
import multiprocessing
import os
import shutil

import tqdm
from django import db
from django.core.management.base import BaseCommand

from documents.models import Document
from documents.parsers import get_parser_class_for_mime_type


def _process_document(doc_id):
    document: Document = Document.objects.get(id=doc_id)
    parser_class = get_parser_class_for_mime_type(document.mime_type)

    if parser_class:
        parser = parser_class(logging_group=None)
    else:
        print(f"{document} No parser for mime type {document.mime_type}")
        return

    try:
        thumb = parser.get_thumbnail(
            document.source_path,
            document.mime_type,
            document.get_public_filename(),
        )

        shutil.move(thumb, document.thumbnail_path)
    finally:
        parser.cleanup()


class Command(BaseCommand):
    help = "This will regenerate the thumbnails for all documents."

    def add_arguments(self, parser):
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
        parser.add_argument(
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown",
        )
        parser.add_argument(
            "--processes",
            default=max(1, os.cpu_count() // 4),
            type=int,
            help="Number of processes to distribute work amongst",
        )

    def handle(self, *args, **options):
        logging.getLogger().handlers[0].level = logging.ERROR

        if options["document"]:
            documents = Document.objects.filter(pk=options["document"])
        else:
            documents = Document.objects.all()

        ids = [doc.id for doc in documents]

        # Note to future self: this prevents django from reusing database
        # connections between processes, which is bad and does not work
        # with postgres.
        db.connections.close_all()

        with multiprocessing.Pool(processes=options["processes"]) as pool:
            list(
                tqdm.tqdm(
                    pool.imap_unordered(_process_document, ids),
                    total=len(ids),
                    disable=options["no_progress_bar"],
                ),
            )
