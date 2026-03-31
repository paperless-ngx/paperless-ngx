"""
Built-in Tika document parser.

Handles Office documents (DOCX, ODT, XLS, XLSX, PPT, PPTX, RTF, etc.) by
sending them to an Apache Tika server for text extraction and a Gotenberg
server for PDF conversion.  Because the source formats cannot be rendered by
a browser natively, the parser always produces a PDF rendition for display.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from contextlib import ExitStack
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Self

import httpx
from django.conf import settings
from django.utils import timezone
from gotenberg_client import GotenbergClient
from gotenberg_client.options import PdfAFormat
from tika_client import TikaClient

from documents.parsers import ParseError
from documents.parsers import make_thumbnail_from_pdf
from paperless.config import OutputTypeConfig
from paperless.models import OutputTypeChoices
from paperless.version import __full_version_str__

if TYPE_CHECKING:
    import datetime
    from types import TracebackType

    from paperless.parsers import MetadataEntry
    from paperless.parsers import ParserContext

logger = logging.getLogger("paperless.parsing.tika")

_SUPPORTED_MIME_TYPES: dict[str, str] = {
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
}


class TikaDocumentParser:
    """Parse Office documents via Apache Tika and Gotenberg for Paperless-ngx.

    Text extraction is handled by the Tika server.  PDF conversion for display
    is handled by Gotenberg (LibreOffice route).  Because the source formats
    cannot be rendered by a browser natively, ``requires_pdf_rendition`` is
    True and the PDF is always produced regardless of the ``produce_archive``
    flag passed to ``parse``.

    Both ``TikaClient`` and ``GotenbergClient`` are opened once in
    ``__enter__`` via an ``ExitStack`` and shared across ``parse``,
    ``extract_metadata``, and ``_convert_to_pdf`` calls, then closed via
    ``ExitStack.close()`` in ``__exit__``.  The parser must always be used
    as a context manager.

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

    name: str = "Paperless-ngx Tika Parser"
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
            Mapping of MIME type to preferred file extension.
        """
        return _SUPPORTED_MIME_TYPES

    @classmethod
    def score(
        cls,
        mime_type: str,
        filename: str,
        path: Path | None = None,
    ) -> int | None:
        """Return the priority score for handling this file.

        Returns ``None`` when Tika integration is disabled so the registry
        skips this parser entirely.

        Parameters
        ----------
        mime_type:
            Detected MIME type of the file.
        filename:
            Original filename including extension.
        path:
            Optional filesystem path. Not inspected by this parser.

        Returns
        -------
        int | None
            10 if TIKA_ENABLED and the MIME type is supported, otherwise None.
        """
        if not settings.TIKA_ENABLED:
            return None
        if mime_type in _SUPPORTED_MIME_TYPES:
            return 10
        return None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def can_produce_archive(self) -> bool:
        """Whether this parser can produce a searchable PDF archive copy.

        Returns
        -------
        bool
            Always False — Tika produces a display PDF, not an OCR archive.
        """
        return False

    @property
    def requires_pdf_rendition(self) -> bool:
        """Whether the parser must produce a PDF for the frontend to display.

        Returns
        -------
        bool
            Always True — Office formats cannot be rendered natively in a
            browser, so a PDF conversion is always required for display.
        """
        return True

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
        self._exit_stack = ExitStack()
        self._tika_client: TikaClient | None = None
        self._gotenberg_client: GotenbergClient | None = None

    def __enter__(self) -> Self:
        self._tika_client = self._exit_stack.enter_context(
            TikaClient(
                tika_url=settings.TIKA_ENDPOINT,
                timeout=settings.CELERY_TASK_TIME_LIMIT,
            ),
        )
        self._gotenberg_client = self._exit_stack.enter_context(
            GotenbergClient(
                host=settings.TIKA_GOTENBERG_ENDPOINT,
                timeout=settings.CELERY_TASK_TIME_LIMIT,
            ),
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._exit_stack.close()
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
        """Send the document to Tika for text extraction and Gotenberg for PDF.

        Because ``requires_pdf_rendition`` is True the PDF conversion is
        always performed — the ``produce_archive`` flag is intentionally
        ignored.

        Parameters
        ----------
        document_path:
            Absolute path to the document file to parse.
        mime_type:
            Detected MIME type of the document.
        produce_archive:
            Accepted for protocol compatibility but ignored; the PDF rendition
            is always produced since the source format cannot be displayed
            natively in the browser.

        Raises
        ------
        documents.parsers.ParseError
            If Tika or Gotenberg returns an error.
        """
        if TYPE_CHECKING:
            assert self._tika_client is not None

        logger.info("Sending %s to Tika server", document_path)

        try:
            try:
                parsed = self._tika_client.tika.as_text.from_file(
                    document_path,
                    mime_type,
                )
            except httpx.HTTPStatusError as err:
                # Workaround https://issues.apache.org/jira/browse/TIKA-4110
                # Tika fails with some files as multi-part form data
                if err.response.status_code == httpx.codes.INTERNAL_SERVER_ERROR:
                    parsed = self._tika_client.tika.as_text.from_buffer(
                        document_path.read_bytes(),
                        mime_type,
                    )
                else:  # pragma: no cover
                    raise
        except Exception as err:
            raise ParseError(
                f"Could not parse {document_path} with tika server at "
                f"{settings.TIKA_ENDPOINT}: {err}",
            ) from err

        self._text = parsed.content
        if self._text is not None:
            self._text = self._text.strip()

        self._date = parsed.created
        if self._date is not None and timezone.is_naive(self._date):
            self._date = timezone.make_aware(self._date)

        # Always convert — requires_pdf_rendition=True means the browser
        # cannot display the source format natively.
        self._archive_path = self._convert_to_pdf(document_path)

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def get_text(self) -> str | None:
        """Return the plain-text content extracted during parse.

        Returns
        -------
        str | None
            Extracted text, or None if parse has not been called yet.
        """
        return self._text

    def get_date(self) -> datetime.datetime | None:
        """Return the document date detected during parse.

        Returns
        -------
        datetime.datetime | None
            Creation date from Tika metadata, or None if not detected.
        """
        return self._date

    def get_archive_path(self) -> Path | None:
        """Return the path to the generated PDF rendition, or None.

        Returns
        -------
        Path | None
            Path to the PDF produced by Gotenberg, or None if parse has not
            been called yet.
        """
        return self._archive_path

    # ------------------------------------------------------------------
    # Thumbnail and metadata
    # ------------------------------------------------------------------

    def get_thumbnail(self, document_path: Path, mime_type: str) -> Path:
        """Generate a thumbnail from the PDF rendition of the document.

        Converts the document to PDF first if not already done.

        Parameters
        ----------
        document_path:
            Absolute path to the source document.
        mime_type:
            Detected MIME type of the document.

        Returns
        -------
        Path
            Path to the generated WebP thumbnail inside the temporary directory.
        """
        if self._archive_path is None:
            self._archive_path = self._convert_to_pdf(document_path)
        return make_thumbnail_from_pdf(self._archive_path, self._tempdir)

    def get_page_count(
        self,
        document_path: Path,
        mime_type: str,
    ) -> int | None:
        """Return the number of pages in the document.

        Counts pages in the archive PDF produced by a preceding parse()
        call.  Returns ``None`` if parse() has not been called yet or if
        no archive was produced.

        Returns
        -------
        int | None
            Page count of the archive PDF, or ``None``.
        """
        if self._archive_path is not None:
            from paperless.parsers.utils import get_page_count_for_pdf

            return get_page_count_for_pdf(self._archive_path, log=logger)
        return None

    def extract_metadata(
        self,
        document_path: Path,
        mime_type: str,
    ) -> list[MetadataEntry]:
        """Extract format-specific metadata via the Tika metadata endpoint.

        Returns
        -------
        list[MetadataEntry]
            All key/value pairs returned by Tika, or ``[]`` on error.
        """
        if TYPE_CHECKING:
            assert self._tika_client is not None

        try:
            parsed = self._tika_client.metadata.from_file(document_path, mime_type)
            return [
                {
                    "namespace": "",
                    "prefix": "",
                    "key": key,
                    "value": parsed.data[key],
                }
                for key in parsed.data
            ]
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

    def _convert_to_pdf(self, document_path: Path) -> Path:
        """Convert the document to PDF using Gotenberg's LibreOffice route.

        Parameters
        ----------
        document_path:
            Absolute path to the source document.

        Returns
        -------
        Path
            Path to the generated PDF inside the temporary directory.

        Raises
        ------
        documents.parsers.ParseError
            If Gotenberg returns an error.
        """
        if TYPE_CHECKING:
            assert self._gotenberg_client is not None

        pdf_path = self._tempdir / "convert.pdf"

        logger.info("Converting %s to PDF as %s", document_path, pdf_path)

        with self._gotenberg_client.libre_office.to_pdf() as route:
            # Set the output format of the resulting PDF.
            # OutputTypeConfig reads the database-stored ApplicationConfiguration
            # first, then falls back to the PAPERLESS_OCR_OUTPUT_TYPE env var.
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

            try:
                response = route.run()
                pdf_path.write_bytes(response.content)
                return pdf_path
            except Exception as err:
                raise ParseError(
                    f"Error while converting document to PDF: {err}",
                ) from err
