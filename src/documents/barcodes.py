import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from pdf2image import convert_from_path
from pikepdf import Page
from pikepdf import PasswordError
from pikepdf import Pdf
from PIL import Image

from documents.converters import convert_from_tiff_to_pdf
from documents.data_models import ConsumableDocument
from documents.models import Tag
from documents.plugins.base import ConsumeTaskPlugin
from documents.plugins.base import StopConsumeTaskError
from documents.plugins.helpers import ProgressStatusOptions
from documents.utils import copy_basic_file_stats
from documents.utils import copy_file_with_basic_stats
from documents.utils import maybe_override_pixel_limit

logger = logging.getLogger("paperless.barcodes")


@dataclass(frozen=True)
class Barcode:
    """
    Holds the information about a single barcode and its location in a document
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


class BarcodePlugin(ConsumeTaskPlugin):
    NAME: str = "BarcodePlugin"

    @property
    def able_to_run(self) -> bool:
        """
        Able to run if:
          - ASN from barcode detection is enabled or
          - Barcode support is enabled and the mime type is supported
        """
        if settings.CONSUMER_BARCODE_TIFF_SUPPORT:
            supported_mimes = {"application/pdf", "image/tiff"}
        else:
            supported_mimes = {"application/pdf"}

        return (
            settings.CONSUMER_ENABLE_ASN_BARCODE
            or settings.CONSUMER_ENABLE_BARCODES
            or settings.CONSUMER_ENABLE_TAG_BARCODE
        ) and self.input_doc.mime_type in supported_mimes

    def setup(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            dir=self.base_tmp_dir,
            prefix="barcode",
        )
        self.pdf_file = self.input_doc.original_file
        self._tiff_conversion_done = False
        self.barcodes: list[Barcode] = []

    def run(self) -> str | None:
        # Some operations may use PIL, override pixel setting if needed
        maybe_override_pixel_limit()

        # Maybe do the conversion of TIFF to PDF
        self.convert_from_tiff_to_pdf()

        # Locate any barcodes in the files
        self.detect()

        # try reading tags from barcodes
        if (
            settings.CONSUMER_ENABLE_TAG_BARCODE
            and (tags := self.tags) is not None
            and len(tags) > 0
        ):
            if self.metadata.tag_ids:
                self.metadata.tag_ids += tags
            else:
                self.metadata.tag_ids = tags
            logger.info(f"Found tags in barcode: {tags}")

        # Lastly attempt to split documents
        if settings.CONSUMER_ENABLE_BARCODES and (
            separator_pages := self.get_separation_pages()
        ):
            # We have pages to split against

            # Note this does NOT use the base_temp_dir, as that will be removed
            tmp_dir = Path(
                tempfile.mkdtemp(
                    dir=settings.SCRATCH_DIR,
                    prefix="paperless-barcode-split-",
                ),
            ).resolve()

            from documents import tasks

            # Create the split document tasks
            for new_document in self.separate_pages(separator_pages):
                copy_file_with_basic_stats(new_document, tmp_dir / new_document.name)

                task = tasks.consume_file.delay(
                    ConsumableDocument(
                        # Same source, for templates
                        source=self.input_doc.source,
                        mailrule_id=self.input_doc.mailrule_id,
                        # Can't use same folder or the consume might grab it again
                        original_file=(tmp_dir / new_document.name).resolve(),
                    ),
                    # All the same metadata
                    self.metadata,
                )
                logger.info(f"Created new task {task.id} for {new_document.name}")

            # This file is now two or more files
            self.input_doc.original_file.unlink()

            msg = "Barcode splitting complete!"

            # Update the progress to complete
            self.status_mgr.send_progress(ProgressStatusOptions.SUCCESS, msg, 100, 100)

            # Request the consume task stops
            raise StopConsumeTaskError(msg)

        # Update/overwrite an ASN if possible
        # After splitting, as otherwise each split document gets the same ASN
        if (
            settings.CONSUMER_ENABLE_ASN_BARCODE
            and (located_asn := self.asn) is not None
        ):
            logger.info(f"Found ASN in barcode: {located_asn}")
            self.metadata.asn = located_asn

    def cleanup(self) -> None:
        self.temp_dir.cleanup()

    def convert_from_tiff_to_pdf(self):
        """
        May convert a TIFF image into a PDF, if the input is a TIFF and
        the TIFF has not been made into a PDF
        """
        # Nothing to do, pdf_file is already assigned correctly
        if self.input_doc.mime_type != "image/tiff" or self._tiff_conversion_done:
            return

        self.pdf_file = convert_from_tiff_to_pdf(
            self.input_doc.original_file,
            Path(self.temp_dir.name),
        )
        self._tiff_conversion_done = True

    @staticmethod
    def read_barcodes_zxing(image: Image.Image) -> list[str]:
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
    def read_barcodes_pyzbar(image: Image.Image) -> list[str]:
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
            # Read number of pages from pdf
            with Pdf.open(self.pdf_file) as pdf:
                num_of_pages = len(pdf.pages)
            logger.debug(f"PDF has {num_of_pages} pages")

            # Get limit from configuration
            barcode_max_pages = (
                num_of_pages
                if settings.CONSUMER_BARCODE_MAX_PAGES == 0
                else settings.CONSUMER_BARCODE_MAX_PAGES
            )

            if barcode_max_pages < num_of_pages:  # pragma: no cover
                logger.debug(
                    f"Barcodes detection will be limited to the first {barcode_max_pages} pages",
                )

            # Loop al page
            for current_page_number in range(min(num_of_pages, barcode_max_pages)):
                logger.debug(f"Processing page {current_page_number}")

                # Convert page to image
                page = convert_from_path(
                    self.pdf_file,
                    dpi=settings.CONSUMER_BARCODE_DPI,
                    output_folder=self.temp_dir.name,
                    first_page=current_page_number + 1,
                    last_page=current_page_number + 1,
                )[0]

                # Remember filename, since it is lost by upscaling
                page_filepath = Path(page.filename)
                logger.debug(f"Image is at {page_filepath}")

                # Upscale image if configured
                factor = settings.CONSUMER_BARCODE_UPSCALE
                if factor > 1.0:
                    logger.debug(
                        f"Upscaling image by {factor} for better barcode detection",
                    )
                    x, y = page.size
                    page = page.resize(
                        (int(round(x * factor)), (int(round(y * factor)))),
                    )

                # Detect barcodes
                for barcode_value in reader(page):
                    self.barcodes.append(
                        Barcode(current_page_number, barcode_value),
                    )

                # Delete temporary image file
                page_filepath.unlink()

        # Password protected files can't be checked
        # This is the exception raised for those
        except PasswordError as e:
            logger.warning(
                f"File is likely password protected, not checking for barcodes: {e}",
            )
        # This file is really borked, allow the consumption to continue
        # but it may fail further on
        except Exception as e:  # pragma: no cover
            logger.warning(
                f"Exception during barcode scanning: {e}",
            )

    @property
    def asn(self) -> int | None:
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

            # remove non-numeric parts of the remaining string
            asn_text = re.sub(r"\D", "", asn_text)

            # now, try parsing the ASN number
            try:
                asn = int(asn_text)
            except ValueError as e:
                logger.warning(f"Failed to parse ASN number because: {e}")

        return asn

    @property
    def tags(self) -> list[int] | None:
        """
        Search the parsed barcodes for any tags.
        Returns the detected tag ids (or empty list)
        """
        tags = []

        # Ensure the barcodes have been read
        self.detect()

        for x in self.barcodes:
            tag_texts = x.value

            for raw in tag_texts.split(","):
                try:
                    tag = None
                    for regex in settings.CONSUMER_TAG_BARCODE_MAPPING:
                        if re.match(regex, raw, flags=re.IGNORECASE):
                            sub = settings.CONSUMER_TAG_BARCODE_MAPPING[regex]
                            tag = (
                                re.sub(regex, sub, raw, flags=re.IGNORECASE)
                                if sub
                                else raw
                            )
                            break

                    if tag:
                        tag, _ = Tag.objects.get_or_create(
                            name__iexact=tag,
                            defaults={"name": tag},
                        )

                        logger.debug(
                            f"Found Tag Barcode '{raw}', substituted "
                            f"to '{tag}' and mapped to "
                            f"tag #{tag.pk}.",
                        )
                        tags.append(tag.pk)

                except Exception as e:
                    logger.error(
                        f"Failed to find or create TAG '{raw}' because: {e}",
                    )

        return tags

    def get_separation_pages(self) -> dict[int, bool]:
        """
        Search the parsed barcodes for separators and returns a dict of page
        numbers, which separate the file into new files, together with the
        information whether to keep the page.
        """
        # filter all barcodes for the separator string
        # get the page numbers of the separating barcodes
        retain = settings.CONSUMER_BARCODE_RETAIN_SPLIT_PAGES
        separator_pages = {
            bc.page: retain
            for bc in self.barcodes
            if bc.is_separator and (not retain or (retain and bc.page > 0))
        }  # as below, dont include the first page if retain is enabled
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
        fname = self.input_doc.original_file.stem
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

                copy_basic_file_stats(self.input_doc.original_file, savepath)

                document_paths.append(savepath)

            return document_paths
