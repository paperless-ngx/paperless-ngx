from __future__ import annotations

import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import regex as regex_mod
from django.conf import settings
from pdf2image import convert_from_path
from pikepdf import Page
from pikepdf import PasswordError
from pikepdf import Pdf

from documents.converters import convert_from_tiff_to_pdf
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.data_models import StoredBarcode
from documents.models import Document
from documents.models import PaperlessTask
from documents.models import Tag
from documents.plugins.base import ConsumeTaskPlugin
from documents.plugins.base import StopConsumeTaskError
from documents.plugins.helpers import ProgressManager
from documents.plugins.helpers import ProgressStatusOptions
from documents.regex import safe_regex_match
from documents.regex import safe_regex_sub
from documents.utils import copy_basic_file_stats
from documents.utils import copy_file_with_basic_stats
from documents.utils import maybe_override_pixel_limit
from paperless.config import BarcodeConfig

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger("paperless.barcodes")


@dataclass(frozen=True)
class Barcode:
    """
    Holds the information about a single barcode and its location in a document
    """

    page: int
    value: str
    settings: BarcodeConfig
    format: str = ""

    @property
    def is_separator(self) -> bool:
        """
        Returns True if the barcode value equals the configured separation value,
        False otherwise
        """
        return self.value == self.settings.barcode_string

    @property
    def is_asn(self) -> bool:
        """
        Returns True if the barcode value matches the configured ASN prefix,
        False otherwise
        """
        return self.value.startswith(self.settings.barcode_asn_prefix)

    @property
    def is_tag(self) -> bool:
        """
        Returns True if the barcode value matches any configured tag mapping pattern,
        False otherwise.

        Note: This does NOT exclude ASN or separator barcodes - they can also be used
        as tags if they match a tag mapping pattern (e.g., {"ASN12.*": "JOHN"}).
        """
        for pattern in self.settings.barcode_tag_mapping:
            if safe_regex_match(pattern, self.value, flags=regex_mod.IGNORECASE):
                return True
        return False

    def stored(self) -> StoredBarcode:
        """
        The barcode as it is stored with a document, page 1-indexed
        """
        return {"page": self.page + 1, "value": self.value, "format": self.format}


class BarcodePlugin(ConsumeTaskPlugin):
    NAME: str = "BarcodePlugin"

    @property
    def able_to_run(self) -> bool:
        """
        Able to run if:
          - ASN from barcode detection is enabled or
          - Barcode support is enabled and the mime type is supported
        """
        return (
            self.settings.barcode_enable_asn
            or self.settings.barcodes_enabled
            or self.settings.barcode_enable_tag
            or self.settings.barcode_store_values
        ) and self.input_doc.mime_type in scannable_mime_types(self.settings)

    def get_settings(self) -> BarcodeConfig:
        """
        Returns the settings for this plugin (Django settings or app config)
        """
        return BarcodeConfig()

    def __init__(
        self,
        input_doc: ConsumableDocument,
        metadata: DocumentMetadataOverrides,
        status_mgr: ProgressManager,
        base_tmp_dir: Path,
        task_id: str,
    ) -> None:
        super().__init__(
            input_doc,
            metadata,
            status_mgr,
            base_tmp_dir,
            task_id,
        )
        # need these for able_to_run
        self.settings = self.get_settings()

    def setup(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(
            dir=self.base_tmp_dir,
            prefix="barcode",
        )
        self.pdf_file: Path = self.input_doc.original_file
        self._tiff_conversion_done = False
        self.barcodes: list[Barcode] = []

    def _apply_detected_asn(self, detected_asn: int) -> None:
        """
        Apply a detected ASN to metadata if allowed.
        """
        if (
            self.metadata.skip_asn_if_exists
            and Document.global_objects.filter(
                archive_serial_number=detected_asn,
            ).exists()
        ):
            logger.info(
                f"Found ASN in barcode {detected_asn} but skipping because it already exists.",
            )
            return

        logger.info(f"Found ASN in barcode: {detected_asn}")
        self.metadata.asn = detected_asn

    def run(self) -> None:
        # Some operations may use PIL, override pixel setting if needed
        maybe_override_pixel_limit()

        # Maybe do the conversion of TIFF to PDF
        self.convert_from_tiff_to_pdf()

        # Locate any barcodes in the files
        self.detect()

        # try reading tags from barcodes
        # If tag splitting is enabled, skip this on the original document - let each split document extract its own tags
        # However, if we're processing a split document (original_path is set), extract tags
        if (
            self.settings.barcode_enable_tag
            and (
                not self.settings.barcode_tag_split
                or self.input_doc.original_path is not None
            )
            and (tags := self.tags) is not None
            and len(tags) > 0
        ):
            if self.metadata.tag_ids:
                self.metadata.tag_ids += tags
            else:
                self.metadata.tag_ids = tags
            logger.info(f"Found tags in barcode: {tags}")

        # Lastly attempt to split documents
        if self.settings.barcodes_enabled and (
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

            _SOURCE_TO_TRIGGER: dict[DocumentSource, PaperlessTask.TriggerSource] = {
                DocumentSource.ConsumeFolder: PaperlessTask.TriggerSource.FOLDER_CONSUME,
                DocumentSource.ApiUpload: PaperlessTask.TriggerSource.API_UPLOAD,
                DocumentSource.MailFetch: PaperlessTask.TriggerSource.EMAIL_CONSUME,
                DocumentSource.WebUI: PaperlessTask.TriggerSource.WEB_UI,
            }
            trigger_source = _SOURCE_TO_TRIGGER.get(
                self.input_doc.source,
                PaperlessTask.TriggerSource.MANUAL,
            )

            # Create the split document tasks
            for new_document in self.separate_pages(separator_pages):
                copy_file_with_basic_stats(new_document, tmp_dir / new_document.name)

                task = tasks.consume_file.apply_async(
                    kwargs={
                        "input_doc": ConsumableDocument(
                            # Same source, for templates
                            source=self.input_doc.source,
                            mailrule_id=self.input_doc.mailrule_id,
                            # Can't use same folder or the consume might grab it again
                            original_file=(tmp_dir / new_document.name).resolve(),
                            # Adding optional original_path for later uses in
                            # workflow matching
                            original_path=self.input_doc.original_file,
                        ),
                        "overrides": self.metadata,
                    },
                    headers={"trigger_source": trigger_source},
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
        if self.settings.barcode_enable_asn and (located_asn := self.asn) is not None:
            self._apply_detected_asn(located_asn)

        # After splitting too, so each split document keeps its own barcodes
        if self.settings.barcode_store_values:
            self.metadata.barcodes = [x.stored() for x in self.barcodes] or None

    def cleanup(self) -> None:
        self.temp_dir.cleanup()

    def convert_from_tiff_to_pdf(self) -> None:
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

        try:
            self.barcodes = scan_pdf(
                self.pdf_file,
                self.settings,
                Path(self.temp_dir.name),
            )

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
        The first barcode that starts with barcode_asn_prefix
        is considered the ASN to be used.
        Returns the detected ASN (or None)
        """
        asn = None

        # Ensure the barcodes have been read
        self.detect()

        # get the first barcode that starts with barcode_asn_prefix
        asn_text: str | None = next(
            (x.value for x in self.barcodes if x.is_asn),
            None,
        )

        if asn_text:
            logger.debug(f"Found ASN Barcode: {asn_text}")
            # remove the prefix and remove whitespace
            asn_text = asn_text[len(self.settings.barcode_asn_prefix) :].strip()

            # remove non-numeric parts of the remaining string
            asn_text = re.sub(r"\D", "", asn_text)

            # now, try parsing the ASN number
            try:
                asn = int(asn_text)
            except ValueError as e:
                logger.warning(f"Failed to parse ASN number because: {e}")

        return asn

    @property
    def tags(self) -> list[int]:
        """
        Search the parsed barcodes for any tags.
        Returns the detected tag ids (or empty list)
        """
        tags: list[int] = []

        # Ensure the barcodes have been read
        self.detect()

        for x in self.barcodes:
            tag_texts: str = x.value

            for raw in tag_texts.split(","):
                try:
                    tag_str: str | None = None
                    for pattern in self.settings.barcode_tag_mapping:
                        if safe_regex_match(pattern, raw, flags=regex_mod.IGNORECASE):
                            sub = self.settings.barcode_tag_mapping[pattern]
                            tag_str = (
                                safe_regex_sub(
                                    pattern,
                                    sub,
                                    raw,
                                    flags=regex_mod.IGNORECASE,
                                )
                                if sub
                                else raw
                            )
                            break

                    if tag_str:
                        tag, _ = Tag.objects.get_or_create(
                            name__iexact=tag_str,
                            defaults={"name": tag_str},
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
        retain = self.settings.barcode_retain_split_pages
        separator_pages = {
            bc.page: retain
            for bc in self.barcodes
            if bc.is_separator and (not retain or (retain and bc.page > 0))
        }  # as below, dont include the first page if retain is enabled

        # add the page numbers of the ASN barcodes
        # (except for first page, that might lead to infinite loops).
        if self.settings.barcode_enable_asn:
            separator_pages = {
                **separator_pages,
                **{bc.page: True for bc in self.barcodes if bc.is_asn and bc.page != 0},
            }

        # add the page numbers of the TAG barcodes if splitting is enabled
        # (except for first page, that might lead to infinite loops).
        if self.settings.barcode_tag_split and self.settings.barcode_enable_tag:
            separator_pages = {
                **separator_pages,
                **{bc.page: True for bc in self.barcodes if bc.is_tag and bc.page != 0},
            }

        return separator_pages

    def separate_pages(self, pages_to_split_on: dict[int, bool]) -> list[Path]:
        """
        Separate the provided pdf file on the pages_to_split_on.
        The pages which are defined by the keys in page_numbers
        will be removed if the corresponding value is false.
        Returns a list of (temporary) filepaths to consume.
        These will need to be deleted later.
        """

        document_paths = []
        fname: str = self.input_doc.original_file.stem
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
                keep_page: bool = pages_to_split_on[idx]
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
                with savepath.open("wb") as out:
                    dst.save(out)

                copy_basic_file_stats(self.input_doc.original_file, savepath)

                document_paths.append(savepath)

            return document_paths


def scannable_mime_types(settings: BarcodeConfig) -> set[str]:
    """
    The file types the barcode scan supports with the current settings
    """
    if settings.barcode_enable_tiff_support:
        return {"application/pdf", "image/tiff"}
    return {"application/pdf"}


def read_barcodes_zxing(image: Image.Image) -> list[tuple[str, str]]:
    """
    Returns the text and format (zxing enum name) of each barcode found in
    the image
    """
    barcodes = []

    import zxingcpp

    detected_barcodes = zxingcpp.read_barcodes(image)
    for barcode in detected_barcodes:
        if barcode.text:
            barcodes.append((barcode.text, barcode.format.name))
            logger.debug(
                f"Barcode of type {barcode.format} found: {barcode.text}",
            )

    return barcodes


def scan_pdf(pdf_path: Path, settings: BarcodeConfig, work_dir: Path) -> list[Barcode]:
    """
    Scans the pages of a PDF as images for barcodes. Errors are not caught,
    so callers can tell a failed scan from one that found nothing.
    """
    barcodes: list[Barcode] = []

    with Pdf.open(pdf_path) as pdf:
        num_of_pages = len(pdf.pages)
    logger.debug(f"PDF has {num_of_pages} pages")

    # Get limit from configuration
    barcode_max_pages: int = (
        num_of_pages if settings.barcode_max_pages == 0 else settings.barcode_max_pages
    )

    if barcode_max_pages < num_of_pages:  # pragma: no cover
        logger.debug(
            f"Barcodes detection will be limited to the first {barcode_max_pages} pages",
        )

    for current_page_number in range(min(num_of_pages, barcode_max_pages)):
        logger.debug(f"Processing page {current_page_number}")

        # Convert page to image
        page = convert_from_path(
            pdf_path,
            dpi=settings.barcode_dpi,
            output_folder=work_dir,
            first_page=current_page_number + 1,
            last_page=current_page_number + 1,
        )[0]

        # Remember filename, since it is lost by upscaling
        page_filepath = Path(page.filename)
        logger.debug(f"Image is at {page_filepath}")

        # Upscale image if configured
        factor = settings.barcode_upscale
        if factor > 1.0:
            logger.debug(
                f"Upscaling image by {factor} for better barcode detection",
            )
            x, y = page.size
            page = page.resize(
                (round(x * factor), (round(y * factor))),
            )

        for barcode_value, barcode_format in read_barcodes_zxing(page):
            barcodes.append(
                Barcode(current_page_number, barcode_value, settings, barcode_format),
            )

        # Delete temporary image file
        page_filepath.unlink()

    return barcodes


def read_barcode_values(
    path: Path,
    mime_type: str,
    settings: BarcodeConfig,
    work_dir: Path,
) -> list[StoredBarcode] | None:
    """
    Reads the barcodes of a file outside of the consumption plugins: for new
    versions, which skip the barcode plugin, and when reprocessing.

    Returns None if the file can't be scanned with the current settings.
    Errors while scanning are raised.
    """
    if mime_type not in scannable_mime_types(settings):
        return None
    if mime_type == "image/tiff":
        path = convert_from_tiff_to_pdf(path, work_dir)
    return [x.stored() for x in scan_pdf(path, settings, work_dir)]
