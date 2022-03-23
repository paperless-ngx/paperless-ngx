import logging

import tqdm
from django.conf import settings
from django.db.models.signals import post_save
from documents import index
from documents import sanity_checker
from documents.classifier import DocumentClassifier
from documents.classifier import load_classifier
from documents.consumer import Consumer
from documents.consumer import ConsumerError
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import Tag
from documents.sanity_checker import SanityCheckFailedException
from whoosh.writing import AsyncWriter

# barcode decoder
import os
from pyzbar import pyzbar
from pdf2image import convert_from_path
import tempfile
from pikepdf import Pdf

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
    ):

        return

    classifier = load_classifier()

    if not classifier:
        classifier = DocumentClassifier()

    try:
        if classifier.train():
            logger.info(
                "Saving updated classifier model to {}...".format(settings.MODEL_FILE),
            )
            classifier.save()
        else:
            logger.debug("Training data unchanged.")

    except Exception as e:
        logger.warning("Classifier error: " + str(e))



def barcode_reader(page) -> list:
    """
    Read any barcodes contained in page
    Returns a list containing all found barcodes
    """
    barcodes = [ ]
    # Decode the barcode image
    detected_barcodes = pyzbar.decode(page)

    if not detected_barcodes:
        logger.debug(f"No barcode detected")
    else:
        # Traverse through all the detected barcodes in image
        for barcode in detected_barcodes:
            if barcode.data!="":
                barcodes = barcodes + [str(barcode.data)]
                logger.debug(f"Barcode of type {str(barcode.type)} found: {str(barcode.data)}")
    return barcodes

def scan_file_for_seperating_barcodes(filepath) -> list:
    """
    Scan the provided file for page seperating barcodes
    Returns a list of pagenumbers, which seperate the file
    """
    seperator_page_numbers = [ ]
    # use a temporary directory in case the file os too big to handle in memory
    with tempfile.TemporaryDirectory() as path:
        pages_from_path = convert_from_path(filepath, output_folder=path)
        for current_page_number, page in enumerate(pages_from_path):
            current_barcodes = barcode_reader(page)
            if current_barcodes.isin("PATCHT"):
                seperator_page_numbers = seperator_page_numbers + current_page_number
    return seperator_page_numbers

def seperate_pages(filepath, pages_to_split_on: list):
    """
    Seperate the provided file on the pages_to_split_on.
    The pages which are defined by page_numbers will be removed.
    """
    pages_to_split_on = scan_file_for_seperating_barcodes(filepath)
    fname = os.path.splitext(os.path.basename(filepath))[0]
    pdf = Pdf.open(filepath)
    # TODO: Get the directory of the file and save the other files there
    # TODO: Return list of new paths of the new files
    for count, page_number in enumerate(pages_to_split_on):
        # First element, so iterate from zero to the first seperator page
        if count == 0:
            dst = Pdf.new()
            for page in range(0, page_number):
                dst.pages.append(page)
            output_filename = '{}_page_{}.pdf'.format(
                fname, str(count))
            with open(output_filename, 'wb') as out:
                dst.save(out)
        else:
            dst = Pdf.new()
            for page in range(pages_to_split_on[count-1], page_number):
                dst.pages.append(page)
            output_filename = '{}_page_{}.pdf'.format(
                fname, page+1)
            with open(output_filename, 'wb') as out:
                dst.save(out)


def consume_file(
    path,
    override_filename=None,
    override_title=None,
    override_correspondent_id=None,
    override_document_type_id=None,
    override_tag_ids=None,
    task_id=None,
):

    # check for seperators in current document
    seperator_page_numbers = scan_file_for_seperating_barcodes(path)
    if seperator_page_numbers != [ ]:
        logger.debug(f"Pages with seperators found: {str(seperator_page_numbers)}")

    document = Consumer().try_consume_file(
        path,
        override_filename=override_filename,
        override_title=override_title,
        override_correspondent_id=override_correspondent_id,
        override_document_type_id=override_document_type_id,
        override_tag_ids=override_tag_ids,
        task_id=task_id,
    )

    if document:
        return "Success. New document id {} created".format(document.pk)
    else:
        raise ConsumerError(
            "Unknown error: Returned document was null, but "
            "no error message was given.",
        )


def sanity_check():
    messages = sanity_checker.check_sanity()

    messages.log_messages()

    if messages.has_error():
        raise SanityCheckFailedException("Sanity check failed with errors. See log.")
    elif messages.has_warning():
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
