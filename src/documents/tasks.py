import hashlib
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Type

import tqdm
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from documents import barcodes
from documents import index
from documents import sanity_checker
from documents.classifier import DocumentClassifier
from documents.classifier import load_classifier
from documents.consumer import Consumer
from documents.consumer import ConsumerError
from documents.file_handling import create_source_path_directory
from documents.file_handling import generate_unique_filename
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.parsers import DocumentParser
from documents.parsers import get_parser_class_for_mime_type
from documents.sanity_checker import SanityCheckFailedException
from filelock import FileLock
from redis.exceptions import ConnectionError
from whoosh.writing import AsyncWriter


logger = logging.getLogger("paperless.tasks")


@shared_task
def index_optimize():
    ix = index.open_index()
    writer = AsyncWriter(ix)
    writer.commit(optimize=True)


def index_reindex(progress_bar_disable=False):
    documents = Document.objects.all()

    ix = index.open_index(recreate=True)

    with AsyncWriter(ix) as writer:
        for document in tqdm.tqdm(documents, disable=progress_bar_disable):
            index.update_document(writer, document)


@shared_task
def train_classifier():
    if (
        not Tag.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
        and not DocumentType.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
        and not Correspondent.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
        and not StoragePath.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
    ):

        return

    classifier = load_classifier()

    if not classifier:
        classifier = DocumentClassifier()

    try:
        if classifier.train():
            logger.info(
                f"Saving updated classifier model to {settings.MODEL_FILE}...",
            )
            classifier.save()
        else:
            logger.debug("Training data unchanged.")

    except Exception as e:
        logger.warning("Classifier error: " + str(e))


@shared_task
def consume_file(
    path,
    override_filename=None,
    override_title=None,
    override_correspondent_id=None,
    override_document_type_id=None,
    override_tag_ids=None,
    task_id=None,
    override_created=None,
):

    path = Path(path).resolve()
    asn = None

    # Celery converts this to a string, but everything expects a datetime
    # Long term solution is to not use JSON for the serializer but pickle instead
    # TODO: This will be resolved in kombu 5.3, expected with celery 5.3
    # More types will be retained through JSON encode/decode
    if override_created is not None and isinstance(override_created, str):
        try:
            override_created = datetime.fromisoformat(override_created)
        except Exception:
            pass

    # read all barcodes in the current document
    if settings.CONSUMER_ENABLE_BARCODES or settings.CONSUMER_ENABLE_ASN_BARCODE:
        pdf_filepath, parsed_barcodes = barcodes.scan_file_for_barcodes(path)

        # split document by separator pages, if enabled
        if settings.CONSUMER_ENABLE_BARCODES:
            separators = barcodes.get_separating_barcodes(parsed_barcodes)

            if len(separators) > 0:
                logger.debug(
                    f"Pages with separators found in: {str(path)}",
                )
                document_list = barcodes.separate_pages(pdf_filepath, separators)

                if document_list:
                    for n, document in enumerate(document_list):
                        # save to consumption dir
                        # rename it to the original filename  with number prefix
                        if override_filename:
                            newname = f"{str(n)}_" + override_filename
                        else:
                            newname = None

                        # If the file is an upload, it's in the scratch directory
                        # Move it to consume directory to be picked up
                        # Otherwise, use the current parent to keep possible tags
                        # from subdirectories
                        try:
                            # is_relative_to would be nicer, but new in 3.9
                            _ = path.relative_to(settings.SCRATCH_DIR)
                            save_to_dir = settings.CONSUMPTION_DIR
                        except ValueError:
                            save_to_dir = path.parent

                        barcodes.save_to_dir(
                            document,
                            newname=newname,
                            target_dir=save_to_dir,
                        )

                    # Delete the PDF file which was split
                    os.remove(pdf_filepath)

                    # If the original was a TIFF, remove the original file as well
                    if str(pdf_filepath) != str(path):
                        logger.debug(f"Deleting file {path}")
                        os.unlink(path)

                    # notify the sender, otherwise the progress bar
                    # in the UI stays stuck
                    payload = {
                        "filename": override_filename,
                        "task_id": task_id,
                        "current_progress": 100,
                        "max_progress": 100,
                        "status": "SUCCESS",
                        "message": "finished",
                    }
                    try:
                        async_to_sync(get_channel_layer().group_send)(
                            "status_updates",
                            {"type": "status_update", "data": payload},
                        )
                    except ConnectionError as e:
                        logger.warning(f"ConnectionError on status send: {str(e)}")
                    # consuming stops here, since the original document with
                    # the barcodes has been split and will be consumed separately
                    return "File successfully split"

        # try reading the ASN from barcode
        if settings.CONSUMER_ENABLE_ASN_BARCODE:
            asn = barcodes.get_asn_from_barcodes(parsed_barcodes)
            if asn:
                logger.info(f"Found ASN in barcode: {asn}")

    # continue with consumption if no barcode was found
    document = Consumer().try_consume_file(
        path,
        override_filename=override_filename,
        override_title=override_title,
        override_correspondent_id=override_correspondent_id,
        override_document_type_id=override_document_type_id,
        override_tag_ids=override_tag_ids,
        task_id=task_id,
        override_created=override_created,
        override_asn=asn,
    )

    if document:
        return f"Success. New document id {document.pk} created"
    else:
        raise ConsumerError(
            "Unknown error: Returned document was null, but "
            "no error message was given.",
        )


@shared_task
def sanity_check():
    messages = sanity_checker.check_sanity()

    messages.log_messages()

    if messages.has_error:
        raise SanityCheckFailedException("Sanity check failed with errors. See log.")
    elif messages.has_warning:
        return "Sanity check exited with warnings. See log."
    elif len(messages) > 0:
        return "Sanity check exited with infos. See log."
    else:
        return "No issues detected."


@shared_task
def bulk_update_documents(document_ids):
    documents = Document.objects.filter(id__in=document_ids)

    ix = index.open_index()

    for doc in documents:
        post_save.send(Document, instance=doc, created=False)

    with AsyncWriter(ix) as writer:
        for doc in documents:
            index.update_document(writer, doc)


@shared_task
def update_document_archive_file(document_id):
    """
    Re-creates the archive file of a document, including new OCR content and thumbnail
    """
    document = Document.objects.get(id=document_id)

    mime_type = document.mime_type

    parser_class: Type[DocumentParser] = get_parser_class_for_mime_type(mime_type)

    if not parser_class:
        logger.error(
            f"No parser found for mime type {mime_type}, cannot "
            f"archive document {document} (ID: {document_id})",
        )
        return

    parser: DocumentParser = parser_class(logging_group=uuid.uuid4())

    try:
        parser.parse(document.source_path, mime_type, document.get_public_filename())

        thumbnail = parser.get_thumbnail(
            document.source_path,
            mime_type,
            document.get_public_filename(),
        )

        if parser.get_archive_path():
            with transaction.atomic():
                with open(parser.get_archive_path(), "rb") as f:
                    checksum = hashlib.md5(f.read()).hexdigest()
                # I'm going to save first so that in case the file move
                # fails, the database is rolled back.
                # We also don't use save() since that triggers the filehandling
                # logic, and we don't want that yet (file not yet in place)
                document.archive_filename = generate_unique_filename(
                    document,
                    archive_filename=True,
                )
                Document.objects.filter(pk=document.pk).update(
                    archive_checksum=checksum,
                    content=parser.get_text(),
                    archive_filename=document.archive_filename,
                )
                with FileLock(settings.MEDIA_LOCK):
                    create_source_path_directory(document.archive_path)
                    shutil.move(parser.get_archive_path(), document.archive_path)
                    shutil.move(thumbnail, document.thumbnail_path)

            with index.open_index_writer() as writer:
                index.update_document(writer, document)

    except Exception:
        logger.exception(
            f"Error while parsing document {document} " f"(ID: {document_id})",
        )
    finally:
        parser.cleanup()
