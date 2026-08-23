"""
Built-in native document parser.

Converts office documents (DOCX, ODT, XLS, XLSX, PPT, PPTX, RTF, EPUB, CSV)
to text in-process via the `anydoc` Rust library and text-based PDFs via the
`pdf-inspector` Rust library.  Unlike the Tika parser, no external parsing
service is required — everything runs inside the Paperless container.

A Gotenberg endpoint is optional.  When configured, office documents are
additionally rendered to PDF (LibreOffice route) so the frontend can display
them; without it, documents are still ingested with their extracted text but
receive a placeholder thumbnail and no PDF preview.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final
from typing import Self

import anydoc
import httpx
import pdf_inspector
from django.conf import settings
from gotenberg_client import GotenbergClient
from gotenberg_client.options import PdfAFormat
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from documents.parsers import ParseError
from documents.parsers import make_thumbnail_from_pdf
from paperless.config import OutputTypeConfig
from paperless.models import OutputTypeChoices
from paperless.parsers.utils import extract_pdf_metadata
from paperless.parsers.utils import get_page_count_for_pdf
from paperless.parsers.utils import post_process_text
from paperless.version import __full_version_str__

if TYPE_CHECKING:
    import datetime
    from types import TracebackType

    from paperless.parsers import MetadataEntry
    from paperless.parsers import ParserContext

logger = logging.getLogger("paperless.parsing.anydoc")

_PDF_MIME_TYPE: Final[str] = "application/pdf"

# Office formats handled natively by anydoc.  PDFs are listed separately in
# supported_mime_types because they are only claimed after content inspection
# confirms the file carries native text (see score).
_SUPPORTED_MIME_TYPES: Final[dict[str, str]] = {
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.presentationml.slideshow": ".ppsx",
    "application/vnd.oasis.opendocument.presentation": ".odp",
    "application/vnd.oasis.opendocument.spreadsheet": ".ods",
    "application/vnd.oasis.opendocument.text": ".odt",
    "application/vnd.oasis.opendocument.graphics": ".odg",
    "text/rtf": ".rtf",
    "application/epub+zip": ".epub",
}


class AnydocDocumentParser:
    """Parse office documents and text-based PDFs natively for Paperless-ngx.

    Text extraction happens entirely in-process: office formats through the
    ``anydoc`` Rust library, PDFs through ``pdf-inspector``.  The parser only
    claims a PDF when content inspection classifies it as ``text_based``;
    scanned or mixed PDFs are declined so the Tesseract OCR parser handles
    them as usual.

    Gotenberg is optional.  When ``ANYDOC_GOTENBERG_ENDPOINT`` is set (and
    non-empty), office documents are converted to PDF for frontend display
    and ``requires_pdf_rendition`` is True; otherwise no rendition is
    produced and thumbnails fall back to a rendered-text placeholder.

    Class attributes
    ----------------
    name : str
        Human-readable parser name.
    version : str
        Semantic version string, kept in sync with Paperless-ngx releases.
    author : str
        Maintainer name.
    url : str
        Issue tracker / source URL.
    """

    name: str = "Paperless-ngx Anydoc Parser"
    version: str = __full_version_str__
    author: str = "Paperless-ngx Contributors"
    url: str = "https://github.com/paperless-ngx/paperless-ngx"

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def supported_mime_types(cls) -> dict[str, str]:
        """Return the MIME types this parser handles.

        Returns
        -------
        dict[str, str]
            Mapping of MIME type to preferred file extension.  Includes
            ``application/pdf`` although PDFs are only actually claimed by
            :meth:`score` after confirming they contain native text.
        """
        return {**_SUPPORTED_MIME_TYPES, _PDF_MIME_TYPE: ".pdf"}

    @classmethod
    def score(
        cls,
        mime_type: str,
        filename: str,
        path: Path | None = None,
    ) -> int | None:
        """Return the priority score for handling this file.

        Returns ``None`` when native parsing is disabled so the registry
        skips this parser entirely.  PDFs are only claimed when inspection
        classifies them as ``text_based`` (score 20 beats the Tesseract OCR
        parser's default score of 10); scanned or mixed PDFs return None and
        remain with the OCR pipeline.

        Parameters
        ----------
        mime_type:
            Detected MIME type of the file.
        filename:
            Original filename including extension.
        path:
            Filesystem path.  Required to claim PDFs (content inspection);
            optional for office formats.

        Returns
        -------
        int | None
            10 for office MIME types, 20 for text-based PDFs, otherwise
            None.
        """
        if not settings.ANYDOC_ENABLED:
            return None
        if mime_type in _SUPPORTED_MIME_TYPES:
            return 10
        if mime_type == _PDF_MIME_TYPE:
            if path is None:
                return None
            return cls._score_pdf(path)
        return None

    @classmethod
    def _score_pdf(cls, path: Path) -> int | None:
        """Classify a PDF and return a winning score only for text-based ones."""
        try:
            classification = pdf_inspector.classify_pdf(str(path))
        except Exception:
            logger.debug(
                "Could not classify PDF %s, leaving it to other parsers",
                path,
                exc_info=True,
            )
            return None
        if classification.pdf_type == "text_based":
            logger.debug("PDF %s classified as text_based", path)
            return 20
        logger.debug(
            "PDF %s classified as %s, leaving it to the OCR parser",
            path,
            classification.pdf_type,
        )
        return None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @staticmethod
    def _gotenberg_available() -> bool:
        """Whether a Gotenberg endpoint is configured for PDF rendering."""
        return bool(settings.ANYDOC_GOTENBERG_ENDPOINT)

    @property
    def can_produce_archive(self) -> bool:
        """Whether this parser can produce a PDF archive copy.

        True only when Gotenberg is available: office documents are archived
        as their rendered PDF, and text-based PDFs as a byte-identical copy
        of the original.  Without Gotenberg no archive is produced.
        """
        return self._gotenberg_available()

    @property
    def requires_pdf_rendition(self) -> bool:
        """Whether the parser must produce a PDF for the frontend to display.

        True only when Gotenberg is available, since office formats cannot
        be rendered natively by a browser.  Without Gotenberg the document
        is stored original-only with a placeholder thumbnail.
        """
        return self._gotenberg_available()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, logging_group: object = None) -> None:
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        self._tempdir = Path(
            tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR),
        )
        self._text: str | None = None
        self._date: datetime.datetime | None = None
        self._archive_path: Path | None = None
        self._page_count: int | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        logger.debug("Cleaning up temporary directory %s", self._tempdir)
        shutil.rmtree(self._tempdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Core parsing interface
    # ------------------------------------------------------------------

    def configure(self, context: ParserContext) -> None:
        pass

    def parse(
        self,
        document_path: Path,
        mime_type: str,
        *,
        produce_archive: bool = True,
    ) -> None:
        """Extract text locally and optionally produce a PDF archive.

        Neither anydoc nor pdf-inspector expose creation dates, so
        :meth:`get_date` always returns None; the consumer falls back to
        date detection from filename and content.

        Parameters
        ----------
        document_path:
            Absolute path to the document file to parse.
        mime_type:
            Detected MIME type of the document.
        produce_archive:
            When True and a Gotenberg endpoint is configured (or the source
            already is a PDF), a PDF is placed at the path returned by
            :meth:`get_archive_path`.

        Raises
        ------
        documents.parsers.ParseError
            If extraction fails.
        """
        if mime_type == _PDF_MIME_TYPE:
            self._parse_pdf(document_path, produce_archive=produce_archive)
        else:
            self._parse_office(document_path, produce_archive=produce_archive)

    def _parse_pdf(self, document_path: Path, *, produce_archive: bool) -> None:
        """Extract text from a text-based PDF with pdf-inspector."""
        logger.info("Parsing %s natively with pdf-inspector", document_path)

        try:
            result = pdf_inspector.process_pdf(str(document_path))
        except Exception as err:
            raise ParseError(
                f"Could not parse {document_path} with pdf-inspector: {err}",
            ) from err

        markdown = result.markdown
        if not markdown:
            markdown = pdf_inspector.extract_text(str(document_path))
        self._text = post_process_text(markdown) or ""
        self._page_count = result.page_count

        if produce_archive:
            # The original already is a PDF; the archive is a byte-identical
            # copy so consumers relying on an archive file keep working.
            archive_path = self._tempdir / "archive.pdf"
            logger.debug("Copying %s to %s as archive", document_path, archive_path)
            shutil.copy2(document_path, archive_path)
            self._archive_path = archive_path

    def _parse_office(self, document_path: Path, *, produce_archive: bool) -> None:
        """Extract text from an office document with anydoc."""
        logger.info("Parsing %s natively with anydoc", document_path)

        try:
            markdown = anydoc.to_markdown(str(document_path))
        except Exception as err:
            raise ParseError(
                f"Could not parse {document_path} with anydoc: {err}",
            ) from err

        self._text = post_process_text(markdown) or ""

        if produce_archive and self._gotenberg_available():
            self._archive_path = self._convert_to_pdf(document_path)
        elif produce_archive:
            logger.warning(
                "No Gotenberg endpoint configured; %s will be ingested "
                "without a PDF preview",
                document_path,
            )

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def get_text(self) -> str:
        """Return the text content extracted during parse.

        Returns
        -------
        str
            Extracted text (Markdown-flavoured), or an empty string if no
            text could be found.
        """
        return self._text or ""

    def get_date(self) -> datetime.datetime | None:
        """Return the document date detected during parse.

        Returns
        -------
        datetime.datetime | None
            Always None — neither anydoc nor pdf-inspector expose document
            dates.  The consumer detects dates from filename/content instead.
        """
        return self._date

    def get_archive_path(self) -> Path | None:
        """Return the path to the generated PDF archive, or None.

        Returns
        -------
        Path | None
            Path to the produced PDF (rendered by Gotenberg for office
            formats, byte-identical copy for PDFs), or None when no archive
            was produced.
        """
        return self._archive_path

    # ------------------------------------------------------------------
    # Thumbnail and metadata
    # ------------------------------------------------------------------

    def get_thumbnail(self, document_path: Path, mime_type: str) -> Path:
        """Generate a thumbnail for the document.

        Uses the PDF rendition when one exists (or the original itself for
        PDFs); renders a text placeholder otherwise.

        Parameters
        ----------
        document_path:
            Absolute path to the source document.
        mime_type:
            Detected MIME type of the document.

        Returns
        -------
        Path
            Path to the generated WebP thumbnail inside the temporary
            directory.
        """
        if mime_type == _PDF_MIME_TYPE:
            return make_thumbnail_from_pdf(document_path, self._tempdir)
        if self._archive_path is not None:
            return make_thumbnail_from_pdf(self._archive_path, self._tempdir)
        return self._make_placeholder_thumbnail()

    def _make_placeholder_thumbnail(self) -> Path:
        """Render the first portion of the extracted text as a WebP thumbnail."""
        max_chars = 100_000
        text = (self._text or "[No preview available]")[:max_chars]

        img = Image.new("RGB", (500, 700), color="white")
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(
            font=settings.THUMBNAIL_FONT_NAME,
            size=20,
            layout_engine=ImageFont.Layout.BASIC,
        )
        draw.multiline_text((5, 5), text, font=font, fill="black", spacing=4)

        out_path = self._tempdir / "thumb.webp"
        img.save(out_path, format="WEBP")

        return out_path

    def get_page_count(
        self,
        document_path: Path,
        mime_type: str,
    ) -> int | None:
        """Return the number of pages in the document.

        For PDFs this comes from the pdf-inspection performed during parse;
        otherwise from the produced PDF rendition when one exists.

        Returns
        -------
        int | None
            Page count, or None when it cannot be determined.
        """
        if self._page_count is not None:
            return self._page_count
        if self._archive_path is not None:
            return get_page_count_for_pdf(self._archive_path, log=logger)
        return None

    def extract_metadata(
        self,
        document_path: Path,
        mime_type: str,
    ) -> list[MetadataEntry]:
        """Extract format-specific metadata from the document.

        PDFs (originals and archives alike) are read with pikepdf.  anydoc
        does not currently expose a metadata API for office formats, so no
        entries are returned for those.

        Returns
        -------
        list[MetadataEntry]
            XMP/PDF metadata entries for PDF files, or ``[]``.
        """
        if mime_type != _PDF_MIME_TYPE:
            return []
        try:
            return extract_pdf_metadata(document_path, log=logger)
        except Exception as e:
            logger.warning(
                "Error while fetching document metadata for %s: %s",
                document_path,
                e,
            )
            return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _convert_to_pdf(self, document_path: Path) -> Path | None:
        """Convert the document to PDF using Gotenberg's LibreOffice route.

        The PDF rendition is optional: when Gotenberg cannot be reached at
        all (connection error), the document is still ingested with its
        extracted text but without a PDF preview.  Errors reported *by*
        Gotenberg for this specific document are fatal, since they usually
        indicate an unparseable file.

        Parameters
        ----------
        document_path:
            Absolute path to the source document.

        Returns
        -------
        Path | None
            Path to the generated PDF inside the temporary directory, or
            None when Gotenberg is unreachable.

        Raises
        ------
        documents.parsers.ParseError
            If Gotenberg returns an error.
        """
        pdf_path = self._tempdir / "convert.pdf"

        logger.info("Converting %s to PDF as %s", document_path, pdf_path)

        try:
            with (
                GotenbergClient(
                    host=settings.ANYDOC_GOTENBERG_ENDPOINT,
                    timeout=settings.CELERY_TASK_TIME_LIMIT,
                ) as client,
                client.libre_office.to_pdf() as route,
            ):
                # Preserve document fields as authored. updateIndexes
                # (Gotenberg's default) triggers a refresh() that rewrites
                # dynamic fields like auto-dates to the current date.
                route.update_indexes(update_indexes=False)

                # Set the output format of the resulting PDF.
                # OutputTypeConfig reads the database-stored
                # ApplicationConfiguration first, then falls back to the
                # PAPERLESS_OCR_OUTPUT_TYPE env var.
                output_type = OutputTypeConfig().output_type
                if output_type in {
                    OutputTypeChoices.PDF_A,
                    OutputTypeChoices.PDF_A2,
                }:
                    route.pdf_format(PdfAFormat.A2b)
                elif output_type == OutputTypeChoices.PDF_A1:
                    logger.warning(
                        "Gotenberg does not support PDF/A-1a, choosing PDF/A-2b instead",
                    )
                    route.pdf_format(PdfAFormat.A2b)
                elif output_type == OutputTypeChoices.PDF_A3:
                    route.pdf_format(PdfAFormat.A3b)

                route.convert(document_path)
                response = route.run()
                pdf_path.write_bytes(response.content)
        except httpx.TransportError as err:
            logger.warning(
                "Could not reach Gotenberg at %s (%s); ingesting %s "
                "without a PDF preview. Set PAPERLESS_ANYDOC_GOTENBERG_ENDPOINT"
                " to a reachable Gotenberg instance to enable previews.",
                settings.ANYDOC_GOTENBERG_ENDPOINT,
                err,
                document_path,
            )
            return None
        except Exception as err:
            raise ParseError(
                f"Error while converting document to PDF: {err}",
            ) from err

        return pdf_path
