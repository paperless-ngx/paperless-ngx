import hashlib
import multiprocessing

import logging
import os
import shutil
import uuid

import tqdm
from django import db
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from filelock import FileLock
from whoosh.writing import AsyncWriter

from documents.models import Document
from ... import index
from ...file_handling import create_source_path_directory, \
    generate_unique_filename
from ...parsers import get_parser_class_for_mime_type


logger = logging.getLogger("paperless.management.archiver")


def handle_document(document_id):
    document = Document.objects.get(id=document_id)

    mime_type = document.mime_type

    parser_class = get_parser_class_for_mime_type(mime_type)

    if not parser_class:
        logger.error(f"No parser found for mime type {mime_type}, cannot "
                     f"archive document {document} (ID: {document_id})")
        return

    parser = parser_class(logging_group=uuid.uuid4())

    try:
        parser.parse(
            document.source_path,
            mime_type,
            document.get_public_filename())

        thumbnail = parser.get_optimised_thumbnail(
            document.source_path,
            mime_type,
            document.get_public_filename()
        )

        if parser.get_archive_path():
            with transaction.atomic():
                with open(parser.get_archive_path(), 'rb') as f:
                    checksum = hashlib.md5(f.read()).hexdigest()
                # I'm going to save first so that in case the file move
                # fails, the database is rolled back.
                # We also don't use save() since that triggers the filehandling
                # logic, and we don't want that yet (file not yet in place)
                document.archive_filename = generate_unique_filename(
                    document, archive_filename=True)
                Document.objects.filter(pk=document.pk).update(
                    archive_checksum=checksum,
                    content=parser.get_text(),
                    archive_filename=document.archive_filename
                )
                with FileLock(settings.MEDIA_LOCK):
                    create_source_path_directory(document.archive_path)
                    shutil.move(parser.get_archive_path(),
                                document.archive_path)
                    shutil.move(thumbnail, document.thumbnail_path)

            with index.open_index_writer() as writer:
                index.update_document(writer, document)

    except Exception as e:
        logger.exception(f"Error while parsing document {document} "
                         f"(ID: {document_id})")
    finally:
        parser.cleanup()


class Command(BaseCommand):

    help = """
        Using the current classification model, assigns correspondents, tags
        and document types to all documents, effectively allowing you to
        back-tag all previously indexed documents with metadata created (or
        modified) after their initial import.
    """.replace("    ", "")

    def add_arguments(self, parser):
        parser.add_argument(
            "-f", "--overwrite",
            default=False,
            action="store_true",
            help="Recreates the archived document for documents that already "
                 "have an archived version."
        )
        parser.add_argument(
            "-d", "--document",
            default=None,
            type=int,
            required=False,
            help="Specify the ID of a document, and this command will only "
                 "run on this specific document."
        )
        parser.add_argument(
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown"
        )

    def handle(self, *args, **options):

        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)

        overwrite = options["overwrite"]

        if options['document']:
            documents = Document.objects.filter(pk=options['document'])
        else:
            documents = Document.objects.all()

        document_ids = list(map(
            lambda doc: doc.id,
            filter(
                lambda d: overwrite or not d.has_archive_version,
                documents
            )
        ))

        # Note to future self: this prevents django from reusing database
        # conncetions between processes, which is bad and does not work
        # with postgres.
        db.connections.close_all()

        try:

            logging.getLogger().handlers[0].level = logging.ERROR
            with multiprocessing.Pool(processes=settings.TASK_WORKERS) as pool:
                list(tqdm.tqdm(
                    pool.imap_unordered(
                        handle_document,
                        document_ids
                    ),
                    total=len(document_ids),
                    disable=options['no_progress_bar']
                ))
        except KeyboardInterrupt:
            print("Aborting...")
