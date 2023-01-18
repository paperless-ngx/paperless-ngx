import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List
from typing import Optional

import magic
from django.conf import settings
from pdf2image import convert_from_path
from pikepdf import Page
from pikepdf import PasswordError
from pikepdf import Pdf
from pikepdf import PdfImage
from PIL import Image
from PIL import ImageSequence
from pyzbar import pyzbar

logger = logging.getLogger("paperless.barcodes")


class BarcodeImageFormatError(Exception):
    pass


@dataclass(frozen=True)
class Barcode:
    """
    Holds the information about a single barcode and its location
    """

    page: int
    value: str

    @property
    def is_separator(self) -> bool:
        """
        Returns True if the barcode value equals the configured separation value,
        False otherwise
        """
        return self.value == settings.CONSUMER_BARCODE_STRING

    @property
    def is_asn(self) -> bool:
        """
        Returns True if the barcode value matches the configured ASN prefix,
        False otherwise
        """
        return self.value.startswith(settings.CONSUMER_ASN_BARCODE_PREFIX)


@dataclass
class DocumentBarcodeInfo:
    """
    Describes a single document's barcode status
    """

    pdf_path: Path
    barcodes: List[Barcode]


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


def barcode_reader(image: Image) -> List[str]:
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
        except OSError as e:  # pragma: no cover
            logger.warning(
                f"Could not save the file as pdf. Error: {str(e)}",
            )
            return None
    return newpath


def scan_file_for_barcodes(
    filepath: str,
) -> DocumentBarcodeInfo:
    """
    Scan the provided pdf file for any barcodes
    Returns a PDF filepath and a list of
    (page_number, barcode_text) tuples
    """

    def _pikepdf_barcode_scan(pdf_filepath: str) -> List[Barcode]:
        detected_barcodes = []
        with Pdf.open(pdf_filepath) as pdf:
            for page_num, page in enumerate(pdf.pages):
                for image_key in page.images:
                    pdfimage = PdfImage(page.images[image_key])

                    # This type is known to have issues:
                    # https://github.com/pikepdf/pikepdf/issues/401
                    if "/CCITTFaxDecode" in pdfimage.filters:
                        raise BarcodeImageFormatError(
                            "Unable to decode CCITTFaxDecode images",
                        )

                    # Not all images can be transcoded to a PIL image, which
                    # is what pyzbar expects to receive, so this may
                    # raise an exception, triggering fallback
                    pillow_img = pdfimage.as_pil_image()

                    for barcode_value in barcode_reader(pillow_img):
                        detected_barcodes.append(Barcode(page_num, barcode_value))

        return detected_barcodes

    def _pdf2image_barcode_scan(pdf_filepath: str) -> List[Barcode]:
        detected_barcodes = []
        # use a temporary directory in case the file is too big to handle in memory
        with tempfile.TemporaryDirectory() as path:
            pages_from_path = convert_from_path(pdf_filepath, output_folder=path)
            for current_page_number, page in enumerate(pages_from_path):
                for barcode_value in barcode_reader(page):
                    detected_barcodes.append(
                        Barcode(current_page_number, barcode_value),
                    )
        return detected_barcodes

    pdf_filepath = None
    mime_type = get_file_mime_type(filepath)
    barcodes = []

    if supported_file_type(mime_type):
        pdf_filepath = filepath
        if mime_type == "image/tiff":
            pdf_filepath = convert_from_tiff_to_pdf(filepath)

        # Always try pikepdf first, it's usually fine, faster and
        # uses less memory
        try:
            barcodes = _pikepdf_barcode_scan(pdf_filepath)
        # Password protected files can't be checked
        except PasswordError as e:
            logger.warning(
                f"File is likely password protected, not checking for barcodes: {e}",
            )
        # Handle pikepdf related image decoding issues with a fallback to page
        # by page conversion to images in a temporary directory
        except Exception as e:
            logger.warning(
                f"Falling back to pdf2image because: {e}",
            )
            try:
                barcodes = _pdf2image_barcode_scan(pdf_filepath)
            # This file is really borked, allow the consumption to continue
            # but it may fail further on
            except Exception as e:  # pragma: no cover
                logger.warning(
                    f"Exception during barcode scanning: {e}",
                )

    else:
        logger.warning(
            f"Unsupported file format for barcode reader: {str(mime_type)}",
        )

    return DocumentBarcodeInfo(pdf_filepath, barcodes)


def get_separating_barcodes(barcodes: List[Barcode]) -> List[int]:
    """
    Search the parsed barcodes for separators
    and returns a list of page numbers, which
    separate the file into new files
    """
    # filter all barcodes for the separator string
    # get the page numbers of the separating barcodes

    return [bc.page for bc in barcodes if bc.is_separator]


def get_asn_from_barcodes(barcodes: List[Barcode]) -> Optional[int]:
    """
    Search the parsed barcodes for any ASNs.
    The first barcode that starts with CONSUMER_ASN_BARCODE_PREFIX
    is considered the ASN to be used.
    Returns the detected ASN (or None)
    """
    asn = None

    # get the first barcode that starts with CONSUMER_ASN_BARCODE_PREFIX
    asn_text = next(
        (x.value for x in barcodes if x.is_asn),
        None,
    )

    if asn_text:
        logger.debug(f"Found ASN Barcode: {asn_text}")
        # remove the prefix and remove whitespace
        asn_text = asn_text[len(settings.CONSUMER_ASN_BARCODE_PREFIX) :].strip()

        # now, try parsing the ASN number
        try:
            asn = int(asn_text)
        except ValueError as e:
            logger.warn(f"Failed to parse ASN number because: {e}")

    return asn


def separate_pages(filepath: str, pages_to_split_on: List[int]) -> List[str]:
    """
    Separate the provided pdf file on the pages_to_split_on.
    The pages which are defined by page_numbers will be removed.
    Returns a list of (temporary) filepaths to consume.
    These will need to be deleted later.
    """

    document_paths = []

    if not pages_to_split_on:
        logger.warning("No pages to split on!")
        return document_paths

    os.makedirs(settings.SCRATCH_DIR, exist_ok=True)
    tempdir = tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)
    fname = os.path.splitext(os.path.basename(filepath))[0]
    pdf = Pdf.open(filepath)

    # A list of documents, ie a list of lists of pages
    documents: List[List[Page]] = []
    # A single document, ie a list of pages
    document: List[Page] = []

    for idx, page in enumerate(pdf.pages):
        # Keep building the new PDF as long as it is not a
        # separator index
        if idx not in pages_to_split_on:
            document.append(page)
            # Make sure to append the very last document to the documents
            if idx == (len(pdf.pages) - 1):
                documents.append(document)
                document = []
        else:
            # This is a split index, save the current PDF pages, and restart
            # a new destination page listing
            logger.debug(f"Starting new document at idx {idx}")
            documents.append(document)
            document = []

    documents = [x for x in documents if len(x)]

    logger.debug(f"Split into {len(documents)} new documents")

    # Write the new documents out
    for doc_idx, document in enumerate(documents):
        dst = Pdf.new()
        dst.pages.extend(document)

        output_filename = f"{fname}_document_{doc_idx}.pdf"

        logger.debug(f"pdf no:{doc_idx} has {len(dst.pages)} pages")
        savepath = os.path.join(tempdir, output_filename)
        with open(savepath, "wb") as out:
            dst.save(out)
        document_paths.append(savepath)

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
