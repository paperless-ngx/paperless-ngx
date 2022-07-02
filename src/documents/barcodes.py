import logging
import os
import shutil
import tempfile
from functools import lru_cache
from typing import List  # for type hinting. Can be removed, if only Python >3.8 is used

import magic
from django.conf import settings
from pdf2image import convert_from_path
from pikepdf import Pdf
from PIL import Image
from PIL import ImageSequence
from pyzbar import pyzbar

logger = logging.getLogger("paperless.barcodes")


@lru_cache(maxsize=8)
def supported_file_type(mime_type) -> bool:
    """
    Determines if the file is valid for barcode
    processing, based on MIME type and settings

    :return: True if the file is supported, False otherwise
    """
    supported_mime = ["application/pdf"]
    if settings.CONSUMER_BARCODE_TIFF_SUPPORT:
        supported_mime += ["image/tiff"]

    return mime_type in supported_mime


def barcode_reader(image) -> List[str]:
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


def get_file_mime_type(path: str) -> str:
    """
    Determines the file type, based on MIME type.

    Returns the MIME type.
    """
    mime_type = magic.from_file(path, mime=True)
    logger.debug(f"Detected mime type: {mime_type}")
    return mime_type


def convert_from_tiff_to_pdf(filepath: str) -> str:
    """
    converts a given TIFF image file to pdf into a temporary directory.

    Returns the new pdf file.
    """
    file_name = os.path.splitext(os.path.basename(filepath))[0]
    mime_type = get_file_mime_type(filepath)
    tempdir = tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)
    # use old file name with pdf extension
    if mime_type == "image/tiff":
        newpath = os.path.join(tempdir, file_name + ".pdf")
    else:
        logger.warning(
            f"Cannot convert mime type {str(mime_type)} from {str(filepath)} to pdf.",
        )
        return None
    with Image.open(filepath) as image:
        images = []
        for i, page in enumerate(ImageSequence.Iterator(image)):
            page = page.convert("RGB")
            images.append(page)
        try:
            if len(images) == 1:
                images[0].save(newpath)
            else:
                images[0].save(newpath, save_all=True, append_images=images[1:])
        except OSError as e:
            logger.warning(
                f"Could not save the file as pdf. Error: {str(e)}",
            )
            return None
    return newpath


def scan_file_for_separating_barcodes(filepath: str) -> List[int]:
    """
    Scan the provided pdf file for page separating barcodes
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


def separate_pages(filepath: str, pages_to_split_on: List[int]) -> List[str]:
    """
    Separate the provided pdf file on the pages_to_split_on.
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
        output_filename = f"{fname}_document_0.pdf"
        savepath = os.path.join(tempdir, output_filename)
        with open(savepath, "wb") as out:
            dst.save(out)
        document_paths = [savepath]

        # iterate through the rest of the document
        for count, page_number in enumerate(pages_to_split_on):
            logger.debug(f"Count: {str(count)} page_number: {str(page_number)}")
            dst = Pdf.new()
            try:
                next_page = pages_to_split_on[count + 1]
            except IndexError:
                next_page = len(pdf.pages)
            # skip the first page_number. This contains the barcode page
            for page in range(page_number + 1, next_page):
                logger.debug(
                    f"page_number: {str(page_number)} next_page: {str(next_page)}",
                )
                dst.pages.append(pdf.pages[page])
            output_filename = f"{fname}_document_{str(count + 1)}.pdf"
            logger.debug(f"pdf no:{str(count)} has {str(len(dst.pages))} pages")
            savepath = os.path.join(tempdir, output_filename)
            with open(savepath, "wb") as out:
                dst.save(out)
            document_paths.append(savepath)
    logger.debug(f"Temp files are {str(document_paths)}")
    return document_paths


def save_to_dir(
    filepath: str,
    newname: str = None,
    target_dir: str = settings.CONSUMPTION_DIR,
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
