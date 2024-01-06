import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from typing import Optional

from django.conf import settings
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError
from pikepdf import Page
from pikepdf import Pdf
from PIL import Image

from documents.converters import convert_from_tiff_to_pdf
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.utils import copy_basic_file_stats
from documents.utils import copy_file_with_basic_stats

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
        self.barcodes: list[Barcode] = []
        self._tiff_conversion_done = False
        self.temp_dir: Optional[tempfile.TemporaryDirectory] = None

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

        if not self.supported_mime_type:
            return None

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

            # remove non-numeric parts of the remaining string
            asn_text = re.sub(r"\D", "", asn_text)

            # now, try parsing the ASN number
            try:
                asn = int(asn_text)
            except ValueError as e:
                logger.warning(f"Failed to parse ASN number because: {e}")

        return asn

    @staticmethod
    def read_barcodes_zxing(image: Image) -> list[str]:
        barcodes = []

        import zxingcpp

        detected_barcodes = zxingcpp.read_barcodes(image)
        for barcode in detected_barcodes:
            if barcode.text:
                barcodes.append(barcode.text)
                logger.debug(
                    f"Barcode of type {barcode.format} found: {barcode.text}",
                )

        return barcodes

    @staticmethod
    def read_barcodes_pyzbar(image: Image) -> list[str]:
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
                    f"Barcode of type {barcode.type} found: {decoded_barcode}",
                )

        return barcodes

    def convert_from_tiff_to_pdf(self):
        """
        May convert a TIFF image into a PDF, if the input is a TIFF and
        the TIFF has not been made into a PDF
        """
        # Nothing to do, pdf_file is already assigned correctly
        if self.mime != "image/tiff" or self._tiff_conversion_done:
            return

        self._tiff_conversion_done = True
        self.pdf_file = convert_from_tiff_to_pdf(self.file, Path(self.temp_dir.name))

    def detect(self) -> None:
        """
        Scan all pages of the PDF as images, updating barcodes and the pages
        found on as we go
        """
        # Bail if barcodes already exist
        if self.barcodes:
            return

        # No op if not a TIFF
        self.convert_from_tiff_to_pdf()

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
                dpi=settings.CONSUMER_BARCODE_DPI,
                output_folder=self.temp_dir.name,
            )

            for current_page_number, page in enumerate(pages_from_path):
                factor = settings.CONSUMER_BARCODE_UPSCALE
                if factor > 1.0:
                    logger.debug(
                        f"Upscaling image by {factor} for better barcode detection",
                    )
                    x, y = page.size
                    page = page.resize(
                        (int(round(x * factor)), (int(round(y * factor)))),
                    )

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
            logger.exception(
                f"Exception during barcode scanning: {e}",
            )

    def get_separation_pages(self) -> dict[int, bool]:
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

    def separate_pages(self, pages_to_split_on: dict[int, bool]) -> list[Path]:
        """
        Separate the provided pdf file on the pages_to_split_on.
        The pages which are defined by the keys in page_numbers
        will be removed if the corresponding value is false.
        Returns a list of (temporary) filepaths to consume.
        These will need to be deleted later.
        """

        document_paths = []
        fname = self.file.stem
        with Pdf.open(self.pdf_file) as input_pdf:
            # Start with an empty document
            current_document: list[Page] = []
            # A list of documents, ie a list of lists of pages
            documents: list[list[Page]] = [current_document]

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

                copy_basic_file_stats(self.file, savepath)

                document_paths.append(savepath)

            return document_paths

    def separate(
        self,
        source: DocumentSource,
        overrides: DocumentMetadataOverrides,
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

        tmp_dir = Path(tempfile.mkdtemp(prefix="paperless-barcode-split-")).resolve()

        from documents import tasks

        # Create the split document tasks
        for new_document in self.separate_pages(separator_pages):
            copy_file_with_basic_stats(new_document, tmp_dir / new_document.name)

            tasks.consume_file.delay(
                ConsumableDocument(
                    # Same source, for templates
                    source=source,
                    # Can't use same folder or the consume might grab it again
                    original_file=(tmp_dir / new_document.name).resolve(),
                ),
                # All the same metadata
                overrides,
            )
        logger.info("Barcode splitting complete!")
        return True
