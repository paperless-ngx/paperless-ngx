import logging
import os
import shutil
from pathlib import Path
from typing import Type

import tqdm
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_save
from documents import barcodes
from documents import index
from documents import sanity_checker
from documents.classifier import DocumentClassifier
from documents.classifier import load_classifier
from documents.consumer import Consumer
from documents.consumer import ConsumerError
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.parsers import DocumentParser
from documents.parsers import get_parser_class_for_mime_type
from documents.parsers import ParseError
from documents.sanity_checker import SanityCheckFailedException
from whoosh.writing import AsyncWriter


logger = logging.getLogger("paperless.tasks")


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

    # check for separators in current document
    if settings.CONSUMER_ENABLE_BARCODES:

        mime_type = barcodes.get_file_mime_type(path)

        if not barcodes.supported_file_type(mime_type):
            # if not supported, skip this routine
            logger.warning(
                f"Unsupported file format for barcode reader: {str(mime_type)}",
            )
        else:
            separators = []
            document_list = []

            if mime_type == "image/tiff":
                file_to_process = barcodes.convert_from_tiff_to_pdf(path)
            else:
                file_to_process = path

            separators = barcodes.scan_file_for_separating_barcodes(file_to_process)

            if separators:
                logger.debug(
                    f"Pages with separators found in: {str(path)}",
                )
                document_list = barcodes.separate_pages(file_to_process, separators)

            if document_list:
                for n, document in enumerate(document_list):
                    # save to consumption dir
                    # rename it to the original filename  with number prefix
                    if override_filename:
                        newname = f"{str(n)}_" + override_filename
                    else:
                        newname = None
                    barcodes.save_to_dir(document, newname=newname)

                # if we got here, the document was successfully split
                # and can safely be deleted
                if mime_type == "image/tiff":
                    # Remove the TIFF converted to PDF file
                    logger.debug(f"Deleting file {file_to_process}")
                    os.unlink(file_to_process)
                # Remove the original file (new file is saved above)
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
                except OSError as e:
                    logger.warning(
                        "OSError. It could be, the broker cannot be reached.",
                    )
                    logger.warning(str(e))
                # consuming stops here, since the original document with
                # the barcodes has been split and will be consumed separately
                return "File successfully split"

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
    )

    if document:
        return f"Success. New document id {document.pk} created"
    else:
        raise ConsumerError(
            "Unknown error: Returned document was null, but "
            "no error message was given.",
        )


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


def bulk_update_documents(document_ids):
    documents = Document.objects.filter(id__in=document_ids)

    ix = index.open_index()

    for doc in documents:
        post_save.send(Document, instance=doc, created=False)

    with AsyncWriter(ix) as writer:
        for doc in documents:
            index.update_document(writer, doc)


def redo_ocr(document_ids):
    all_docs = Document.objects.all()

    for doc_pk in document_ids:
        try:
            logger.info(f"Parsing document {doc_pk}")
            doc: Document = all_docs.get(pk=doc_pk)
        except ObjectDoesNotExist:
            logger.error(f"Document {doc_pk} does not exist")
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
            logger.info(
                f"Using {type(document_parser).__name__} for document",
            )
            # Try to re-parse the document into text
            document_parser.parse(str(temp_file), doc.mime_type)

            doc.content = document_parser.get_text()
            doc.save()
            logger.info("Document OCR updated")

        except ParseError as e:
            logger.error(f"Error parsing document: {e}")
        finally:
            # Remove the file path if it was created
            if temp_file.exists() and temp_file.is_file():
                temp_file.unlink()
