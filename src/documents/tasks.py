import logging
import os
import shutil
import tempfile

import tqdm
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
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
from pdf2image import convert_from_path
from pikepdf import Pdf
from pyzbar import pyzbar
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


def barcode_reader(image) -> list[str]:
    """
    Read any barcodes contained in image
    Returns a list containing all found barcodes
    """
    barcodes = []
    # Decode the barcode image
    detected_barcodes = pyzbar.decode(image)

    if detected_barcodes:
        # Traverse through all the detected barcodes in image
        for barcode in detected_barcodes:
            if barcode.data:
                decoded_barcode = barcode.data.decode("utf-8")
                barcodes.append(decoded_barcode)
                logger.debug(
                    f"Barcode of type {str(barcode.type)} found: {decoded_barcode}",
                )
    return barcodes


def scan_file_for_separating_barcodes(filepath: str) -> list[int]:
    """
    Scan the provided file for page separating barcodes
    Returns a list of pagenumbers, which separate the file
    """
    separator_page_numbers = []
    separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
    # use a temporary directory in case the file os too big to handle in memory
    with tempfile.TemporaryDirectory() as path:
        pages_from_path = convert_from_path(filepath, output_folder=path)
        for current_page_number, page in enumerate(pages_from_path):
            current_barcodes = barcode_reader(page)
            if separator_barcode in current_barcodes:
                separator_page_numbers.append(current_page_number)
    return separator_page_numbers


def separate_pages(filepath: str, pages_to_split_on: list[int]) -> list[str]:
    """
    Separate the provided file on the pages_to_split_on.
    The pages which are defined by page_numbers will be removed.
    Returns a list of (temporary) filepaths to consume.
    These will need to be deleted later.
    """
    os.makedirs(settings.SCRATCH_DIR, exist_ok=True)
    tempdir = tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)
    fname = os.path.splitext(os.path.basename(filepath))[0]
    pdf = Pdf.open(filepath)
    document_paths = []
    logger.debug(f"Temp dir is {str(tempdir)}")
    if not pages_to_split_on:
        logger.warning("No pages to split on!")
    else:
        # go from the first page to the first separator page
        dst = Pdf.new()
        for n, page in enumerate(pdf.pages):
            if n < pages_to_split_on[0]:
                dst.pages.append(page)
        output_filename = "{}_document_0.pdf".format(fname)
        savepath = os.path.join(tempdir, output_filename)
        with open(savepath, "wb") as out:
            dst.save(out)
        document_paths = [savepath]

    for count, page_number in enumerate(pages_to_split_on):
        logger.debug(f"Count: {str(count)} page_number: {str(page_number)}")
        dst = Pdf.new()
        try:
            next_page = pages_to_split_on[count + 1]
        except IndexError:
            next_page = len(pdf.pages)
        # skip the first page_number. This contains the barcode page
        for page in range(page_number + 1, next_page):
            logger.debug(f"page_number: {str(page_number)} next_page: {str(next_page)}")
            dst.pages.append(pdf.pages[page])
        output_filename = "{}_document_{}.pdf".format(fname, str(count + 1))
        logger.debug(f"pdf no:{str(count)} has {str(len(dst.pages))} pages")
        savepath = os.path.join(tempdir, output_filename)
        with open(savepath, "wb") as out:
            dst.save(out)
        document_paths.append(savepath)
    logger.debug(f"Temp files are {str(document_paths)}")
    return document_paths


def save_to_dir(
    filepath: str, newname: str = None, target_dir: str = settings.CONSUMPTION_DIR
):
    """
    Copies filepath to target_dir.
    Optionally rename the file.
    """
    if os.path.isfile(filepath) and os.path.isdir(target_dir):
        dst = shutil.copy(filepath, target_dir)
        logging.debug(f"saved {str(filepath)} to {str(dst)}")
        if newname:
            dst_new = os.path.join(target_dir, newname)
            logger.debug(f"moving {str(dst)} to {str(dst_new)}")
            os.rename(dst, dst_new)
    else:
        logger.warning(f"{str(filepath)} or {str(target_dir)} don't exist.")


def consume_file(
    path,
    override_filename=None,
    override_title=None,
    override_correspondent_id=None,
    override_document_type_id=None,
    override_tag_ids=None,
    task_id=None,
):

    # check for separators in current document
    separators = []
    if settings.CONSUMER_ENABLE_BARCODES:
        separators = scan_file_for_separating_barcodes(path)
    document_list = []
    if separators:
        logger.debug(f"Pages with separators found in: {str(path)}")
        document_list = separate_pages(path, separators)
    if document_list:
        for n, document in enumerate(document_list):
            # save to consumption dir
            # rename it to the original filename  with number prefix
            newname = f"{str(n)}_" + override_filename
            save_to_dir(document, newname=newname)
        # if we got here, the document was successfully split
        # and can safely be deleted
        logger.debug("Deleting file {}".format(path))
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
        async_to_sync(get_channel_layer().group_send)(
            "status_updates",
            {"type": "status_update", "data": payload},
        )
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
