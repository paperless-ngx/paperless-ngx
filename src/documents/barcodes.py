import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from subprocess import run
from typing import Dict
from typing import Final
from typing import List
from typing import Optional

import img2pdf
from django.conf import settings
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError
from pikepdf import Page
from pikepdf import Pdf
from PIL import Image

from documents.data_models import DocumentSource

logger = logging.getLogger("paperless.barcodes")


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


class BarcodeReader:
    def __init__(self, filepath: Path, mime_type: str) -> None:
        self.file: Final[Path] = filepath
        self.mime: Final[str] = mime_type
        self.pdf_file: Path = self.file
        self.barcodes: List[Barcode] = []
        self.temp_dir: Optional[Path] = None

        if settings.CONSUMER_BARCODE_TIFF_SUPPORT:
            self.SUPPORTED_FILE_MIMES = {"application/pdf", "image/tiff"}
        else:
            self.SUPPORTED_FILE_MIMES = {"application/pdf"}

    def __enter__(self):
        if self.supported_mime_type:
            self.temp_dir = tempfile.TemporaryDirectory(prefix="paperless-barcodes")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir is not None:
            self.temp_dir.cleanup()
            self.temp_dir = None

    @property
    def supported_mime_type(self) -> bool:
        """
        Return True if the given mime type is supported for barcodes, false otherwise
        """
        return self.mime in self.SUPPORTED_FILE_MIMES

    @property
    def asn(self) -> Optional[int]:
        """
        Search the parsed barcodes for any ASNs.
        The first barcode that starts with CONSUMER_ASN_BARCODE_PREFIX
        is considered the ASN to be used.
        Returns the detected ASN (or None)
        """
        asn = None

        # Ensure the barcodes have been read
        self.detect()

        # get the first barcode that starts with CONSUMER_ASN_BARCODE_PREFIX
        asn_text = next(
            (x.value for x in self.barcodes if x.is_asn),
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
                logger.warning(f"Failed to parse ASN number because: {e}")

        return asn

    @staticmethod
    def read_barcodes_zxing(image: Image) -> List[str]:
        barcodes = []

        import zxingcpp

        detected_barcodes = zxingcpp.read_barcodes(image)
        for barcode in detected_barcodes:
            if barcode.text:
                barcodes.append(barcode.text)
                logger.debug(
                    f"Barcode of type {str(barcode.format)} found: {barcode.text}",
                )

        return barcodes

    @staticmethod
    def read_barcodes_pyzbar(image: Image) -> List[str]:
        barcodes = []

        from pyzbar import pyzbar

        # Decode the barcode image
        detected_barcodes = pyzbar.decode(image)

        # Traverse through all the detected barcodes in image
        for barcode in detected_barcodes:
            if barcode.data:
                decoded_barcode = barcode.data.decode("utf-8")
                barcodes.append(decoded_barcode)
                logger.debug(
                    f"Barcode of type {str(barcode.type)} found: {decoded_barcode}",
                )

        return barcodes

    def convert_from_tiff_to_pdf(self):
        """
        May convert a TIFF image into a PDF, if the input is a TIFF
        """
        # Nothing to do, pdf_file is already assigned correctly
        if self.mime != "image/tiff":
            return

        with Image.open(self.file) as im:
            has_alpha_layer = im.mode in ("RGBA", "LA")
        if has_alpha_layer:
            # Note the save into the temp folder, so as not to trigger a new
            # consume
            scratch_image = Path(self.temp_dir.name) / Path(self.file.name)
            run(
                [
                    settings.CONVERT_BINARY,
                    "-alpha",
                    "off",
                    self.file,
                    scratch_image,
                ],
            )
        else:
            # Not modifying the original, safe to use in place
            scratch_image = self.file

        self.pdf_file = Path(self.temp_dir.name) / Path(self.file.name).with_suffix(
            ".pdf",
        )

        with scratch_image.open("rb") as img_file, self.pdf_file.open("wb") as pdf_file:
            pdf_file.write(img2pdf.convert(img_file))

        # Copy what file stat is possible
        shutil.copystat(self.file, self.pdf_file)

    def detect(self) -> None:
        """
        Scan all pages of the PDF as images, updating barcodes and the pages
        found on as we go
        """
        # Bail if barcodes already exist
        if self.barcodes:
            return

        # Choose the library for reading
        if settings.CONSUMER_BARCODE_SCANNER == "PYZBAR":
            reader = self.read_barcodes_pyzbar
            logger.debug("Scanning for barcodes using PYZBAR")
        else:
            reader = self.read_barcodes_zxing
            logger.debug("Scanning for barcodes using ZXING")

        try:
            pages_from_path = convert_from_path(
                self.pdf_file,
                dpi=300,
                output_folder=self.temp_dir.name,
            )

            for current_page_number, page in enumerate(pages_from_path):
                for barcode_value in reader(page):
                    self.barcodes.append(
                        Barcode(current_page_number, barcode_value),
                    )

        # Password protected files can't be checked
        # This is the exception raised for those
        except PDFPageCountError as e:
            logger.warning(
                f"File is likely password protected, not checking for barcodes: {e}",
            )
        # This file is really borked, allow the consumption to continue
        # but it may fail further on
        except Exception as e:  # pragma: no cover
            logger.warning(
                f"Exception during barcode scanning: {e}",
            )

    def get_separation_pages(self) -> Dict[int, bool]:
        """
        Search the parsed barcodes for separators and returns a dict of page
        numbers, which separate the file into new files, together with the
        information whether to keep the page.
        """
        # filter all barcodes for the separator string
        # get the page numbers of the separating barcodes
        separator_pages = {bc.page: False for bc in self.barcodes if bc.is_separator}
        if not settings.CONSUMER_ENABLE_ASN_BARCODE:
            return separator_pages

        # add the page numbers of the ASN barcodes
        # (except for first page, that might lead to infinite loops).
        return {
            **separator_pages,
            **{bc.page: True for bc in self.barcodes if bc.is_asn and bc.page != 0},
        }

    def separate_pages(self, pages_to_split_on: Dict[int, bool]) -> List[Path]:
        """
        Separate the provided pdf file on the pages_to_split_on.
        The pages which are defined by the keys in page_numbers
        will be removed if the corresponding value is false.
        Returns a list of (temporary) filepaths to consume.
        These will need to be deleted later.
        """

        document_paths = []
        fname = self.file.with_suffix("").name
        with Pdf.open(self.pdf_file) as input_pdf:
            # Start with an empty document
            current_document: List[Page] = []
            # A list of documents, ie a list of lists of pages
            documents: List[List[Page]] = [current_document]

            for idx, page in enumerate(input_pdf.pages):
                # Keep building the new PDF as long as it is not a
                # separator index
                if idx not in pages_to_split_on:
                    current_document.append(page)
                    continue

                # This is a split index
                # Start a new destination page listing
                logger.debug(f"Starting new document at idx {idx}")
                current_document = []
                documents.append(current_document)
                keep_page = pages_to_split_on[idx]
                if keep_page:
                    # Keep the page
                    # (new document is started by asn barcode)
                    current_document.append(page)

            documents = [x for x in documents if len(x)]

            logger.debug(f"Split into {len(documents)} new documents")

            # Write the new documents out
            for doc_idx, document in enumerate(documents):
                dst = Pdf.new()
                dst.pages.extend(document)

                output_filename = f"{fname}_document_{doc_idx}.pdf"

                logger.debug(f"pdf no:{doc_idx} has {len(dst.pages)} pages")
                savepath = Path(self.temp_dir.name) / output_filename
                with open(savepath, "wb") as out:
                    dst.save(out)

                shutil.copystat(self.file, savepath)

                document_paths.append(savepath)

            return document_paths

    def separate(
        self,
        source: DocumentSource,
        override_name: Optional[str] = None,
    ) -> bool:
        """
        Separates the document, based on barcodes and configuration, creating new
        documents as required in the appropriate location.

        Returns True if a split happened, False otherwise
        """
        # Do nothing
        if not self.supported_mime_type:
            logger.warning(f"Unsupported file format for barcode reader: {self.mime}")
            return False

        # Does nothing unless needed
        self.convert_from_tiff_to_pdf()

        # Actually read the codes, if any
        self.detect()

        separator_pages = self.get_separation_pages()

        # Also do nothing
        if not separator_pages:
            logger.warning("No pages to split on!")
            return False

        # Create the split documents
        doc_paths = self.separate_pages(separator_pages)

        # Save the new documents to correct folder
        if source != DocumentSource.ConsumeFolder:
            # The given file is somewhere in SCRATCH_DIR,
            # and new documents must be moved to the CONSUMPTION_DIR
            # for the consumer to notice them
            save_to_dir = settings.CONSUMPTION_DIR
        else:
            # The given file is somewhere in CONSUMPTION_DIR,
            # and may be some levels down for recursive tagging
            # so use the file's parent to preserve any metadata
            save_to_dir = self.file.parent

        for idx, document_path in enumerate(doc_paths):
            if override_name is not None:
                newname = f"{str(idx)}_{override_name}"
                dest = save_to_dir / newname
            else:
                dest = save_to_dir
            logger.info(f"Saving {document_path} to {dest}")
            shutil.copy2(document_path, dest)
        return True
