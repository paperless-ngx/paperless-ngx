import logging
import multiprocessing
import os

import tqdm
from django import db
from django.conf import settings
from django.core.management.base import BaseCommand

from documents.models import Document
from documents.tasks import update_document_archive_file

logger = logging.getLogger("paperless.management.archiver")


class Command(BaseCommand):

    help = """
        Using the current classification model, assigns correspondents, tags
        and document types to all documents, effectively allowing you to
        back-tag all previously indexed documents with metadata created (or
        modified) after their initial import.
    """.replace(
        "    ",
        "",
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--overwrite",
            default=False,
            action="store_true",
            help="Recreates the archived document for documents that already "
            "have an archived version.",
        )
        parser.add_argument(
            "-d",
            "--document",
            default=None,
            type=int,
            required=False,
            help="Specify the ID of a document, and this command will only "
            "run on this specific document.",
        )
        parser.add_argument(
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown",
        )

    def handle(self, *args, **options):

        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)

        overwrite = options["overwrite"]

        if options["document"]:
            documents = Document.objects.filter(pk=options["document"])
        else:
            documents = Document.objects.all()

        document_ids = list(
            map(
                lambda doc: doc.id,
                filter(lambda d: overwrite or not d.has_archive_version, documents),
            ),
        )

        # Note to future self: this prevents django from reusing database
        # conncetions between processes, which is bad and does not work
        # with postgres.
        db.connections.close_all()

        try:

            logging.getLogger().handlers[0].level = logging.ERROR
            with multiprocessing.Pool(processes=settings.TASK_WORKERS) as pool:
                list(
                    tqdm.tqdm(
                        pool.imap_unordered(update_document_archive_file, document_ids),
                        total=len(document_ids),
                        disable=options["no_progress_bar"],
                    ),
                )
        except KeyboardInterrupt:
            self.stdout.write(self.style.NOTICE("Aborting..."))
