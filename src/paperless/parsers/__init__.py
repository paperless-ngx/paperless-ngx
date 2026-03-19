"""
Public interface for the Paperless-ngx parser plugin system.

This module defines ParserProtocol — the structural contract that every
document parser must satisfy, whether it is a built-in parser shipped with
Paperless-ngx or a third-party parser installed via a Python entrypoint.

Phase 1/2 scope: only the Protocol is defined here. The transitional
DocumentParser ABC (Phase 3) and concrete built-in parsers (Phase 3+) will
be added in later phases, so there are intentionally no imports of parser
implementations here.

Usage example (third-party parser)::

    from paperless.parsers import ParserProtocol

    class MyParser:
        name = "my-parser"
        version = "1.0.0"
        author = "Acme Corp"
        url = "https://example.com/my-parser"

        @classmethod
        def supported_mime_types(cls) -> dict[str, str]:
            return {"application/x-my-format": ".myf"}

        @classmethod
        def score(cls, mime_type, filename, path=None):
            return 10

        # … implement remaining protocol methods …

    assert isinstance(MyParser(), ParserProtocol)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Protocol
from typing import Self
from typing import TypedDict
from typing import runtime_checkable

if TYPE_CHECKING:
    import datetime
    from pathlib import Path
    from types import TracebackType

__all__ = [
    "MetadataEntry",
    "ParserContext",
    "ParserProtocol",
]


class MetadataEntry(TypedDict):
    """A single metadata field extracted from a document.

    All four keys are required. Values are always serialised to strings —
    type-specific conversion (dates, integers, lists) is the responsibility
    of the parser before returning.
    """

    namespace: str
    """URI of the metadata namespace (e.g. 'http://ns.adobe.com/pdf/1.3/')."""

    prefix: str
    """Conventional namespace prefix (e.g. 'pdf', 'xmp', 'dc')."""

    key: str
    """Field name within the namespace (e.g. 'Author', 'CreateDate')."""

    value: str
    """String representation of the field value."""


@dataclass(frozen=True, slots=True)
class ParserContext:
    """Immutable context passed to a parser before parse().

    The consumer assembles this from the ingestion event and Django
    settings, then calls ``parser.configure(context)`` before
    ``parser.parse()``.  Parsers read only the fields relevant to them;
    unneeded fields are ignored.

    ``frozen=True`` prevents accidental mutation after the consumer
    hands the context off.  ``slots=True`` keeps instances lightweight.

    Fields
    ------
    mailrule_id : int | None
        Primary key of the ``MailRule`` that triggered this ingestion,
        or ``None`` when the document did not arrive via a mail rule.
        Used by ``MailDocumentParser`` to select the PDF layout.

    Notes
    -----
    Future fields (not yet implemented):

    * ``output_type`` — PDF/A variant for archive generation
      (replaces ``settings.OCR_OUTPUT_TYPE`` reads inside parsers).
    * ``ocr_mode`` — skip-text, redo, force, etc.
      (replaces ``settings.OCR_MODE`` reads inside parsers).
    * ``ocr_language`` — Tesseract language string.
      (replaces ``settings.OCR_LANGUAGE`` reads inside parsers).

    When those fields are added the consumer will read from Django
    settings once and populate them here, decoupling parsers from
    ``settings.*`` entirely.
    """

    mailrule_id: int | None = None


@runtime_checkable
class ParserProtocol(Protocol):
    """Structural contract for all Paperless-ngx document parsers.

    Both built-in parsers and third-party plugins (discovered via the
    "paperless_ngx.parsers" entrypoint group) must satisfy this Protocol.
    Because it is decorated with runtime_checkable, isinstance(obj,
    ParserProtocol) works at runtime based on method presence, which is
    useful for validation in ParserRegistry.discover.

    Parsers must expose four string attributes at the class level so the
    registry can log attribution information without instantiating the parser:

    name : str
        Human-readable parser name (e.g. "Tesseract OCR").
    version : str
        Semantic version string (e.g. "1.2.3").
    author : str
        Author or organisation name.
    url : str
        URL for documentation, source code, or issue tracker.
    """

    # ------------------------------------------------------------------
    # Class-level identity (checked by the registry, not Protocol methods)
    # ------------------------------------------------------------------

    name: str
    version: str
    author: str
    url: str

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def supported_mime_types(cls) -> dict[str, str]:
        """Return a mapping of supported MIME types to preferred file extensions.

        The keys are MIME type strings (e.g. "application/pdf"), and the
        values are the preferred file extension including the leading dot
        (e.g. ".pdf").  The registry uses this mapping both to decide whether
        a parser is a candidate for a given file and to determine the default
        extension when creating archive copies.

        Returns
        -------
        dict[str, str]
            {mime_type: extension} mapping — may be empty if the parser
            has been temporarily disabled.
        """
        ...

    @classmethod
    def score(
        cls,
        mime_type: str,
        filename: str,
        path: Path | None = None,
    ) -> int | None:
        """Return a priority score for handling this file, or None to decline.

        The registry calls this after confirming that the MIME type is in
        supported_mime_types. Parsers may inspect filename and optionally
        the file at path to refine their confidence level.

        A higher score wins. Return None to explicitly decline handling a file
        even though the MIME type is listed as supported (e.g. when a feature
        flag is disabled, or a required service is not configured).

        Parameters
        ----------
        mime_type:
            The detected MIME type of the file to be parsed.
        filename:
            The original filename, including extension.
        path:
            Optional filesystem path to the file. Parsers that need to
            inspect file content (e.g. magic-byte sniffing) may use this.
            May be None when scoring happens before the file is available locally.

        Returns
        -------
        int | None
            Priority score (higher wins), or None to decline.
        """
        ...

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def can_produce_archive(self) -> bool:
        """Whether this parser can produce a searchable PDF archive copy.

        If True, the consumption pipeline may request an archive version when
        processing the document, subject to the ARCHIVE_FILE_GENERATION
        setting. If False, only thumbnail and text extraction are performed.
        """
        ...

    @property
    def requires_pdf_rendition(self) -> bool:
        """Whether the parser must produce a PDF for the frontend to display.

        True for formats the browser cannot display natively (e.g. DOCX, ODT).
        When True, the pipeline always stores the PDF output regardless of the
        ARCHIVE_FILE_GENERATION setting, since the original format cannot be
        shown to the user.
        """
        ...

    # ------------------------------------------------------------------
    # Core parsing interface
    # ------------------------------------------------------------------

    def configure(self, context: ParserContext) -> None:
        """Apply source context before parse().

        Called by the consumer after instantiation and before parse().
        The default implementation is a no-op; parsers override only the
        fields they need.

        Parameters
        ----------
        context:
            Immutable context assembled by the consumer for this
            specific ingestion event.
        """
        ...

    def parse(
        self,
        document_path: Path,
        mime_type: str,
        *,
        produce_archive: bool = True,
    ) -> None:
        """Parse document_path and populate internal state.

        After a successful call, callers retrieve results via get_text,
        get_date, and get_archive_path.

        Parameters
        ----------
        document_path:
            Absolute path to the document file to parse.
        mime_type:
            Detected MIME type of the document.
        produce_archive:
            When True (the default) and can_produce_archive is also True,
            the parser should produce a searchable PDF at the path returned
            by get_archive_path. Pass False when only text extraction and
            thumbnail generation are required and disk I/O should be minimised.

        Raises
        ------
        documents.parsers.ParseError
            If parsing fails for any reason.
        """
        ...

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def get_text(self) -> str | None:
        """Return the plain-text content extracted during parse.

        Returns
        -------
        str | None
            Extracted text, or None if no text could be found.
        """
        ...

    def get_date(self) -> datetime.datetime | None:
        """Return the document date detected during parse.

        Returns
        -------
        datetime.datetime | None
            Detected document date, or None if no date was found.
        """
        ...

    def get_archive_path(self) -> Path | None:
        """Return the path to the generated archive PDF, or None.

        Returns
        -------
        Path | None
            Path to the searchable PDF archive, or None if no archive was
            produced (e.g. because produce_archive=False or the parser does
            not support archive generation).
        """
        ...

    # ------------------------------------------------------------------
    # Thumbnail and metadata
    # ------------------------------------------------------------------

    def get_thumbnail(self, document_path: Path, mime_type: str) -> Path:
        """Generate and return the path to a thumbnail image for the document.

        May be called independently of parse. The returned path must point to
        an existing WebP image file inside the parser's temporary working
        directory.

        Parameters
        ----------
        document_path:
            Absolute path to the source document.
        mime_type:
            Detected MIME type of the document.

        Returns
        -------
        Path
            Path to the generated thumbnail image (WebP format preferred).
        """
        ...

    def get_page_count(
        self,
        document_path: Path,
        mime_type: str,
    ) -> int | None:
        """Return the number of pages in the document, if determinable.

        Parameters
        ----------
        document_path:
            Absolute path to the source document.
        mime_type:
            Detected MIME type of the document.

        Returns
        -------
        int | None
            Page count, or None if the parser cannot determine it.
        """
        ...

    def extract_metadata(
        self,
        document_path: Path,
        mime_type: str,
    ) -> list[MetadataEntry]:
        """Extract format-specific metadata from the document.

        Called by the API view layer on demand — not during the consumption
        pipeline. Results are returned to the frontend for per-file display.

        For documents with an archive version, this method is called twice:
        once for the original file (with its native MIME type) and once for
        the archive file (with ``"application/pdf"``). Parsers that produce
        archives should handle both cases.

        Implementations must not raise. A failure to read metadata is not
        fatal — log a warning and return whatever partial results were
        collected, or ``[]`` if none.

        Parameters
        ----------
        document_path:
            Absolute path to the file to extract metadata from.
        mime_type:
            MIME type of the file at ``document_path``. May be
            ``"application/pdf"`` when called for the archive version.

        Returns
        -------
        list[MetadataEntry]
            Zero or more metadata entries. Returns ``[]`` if no metadata
            could be extracted or the format does not support it.
        """
        ...

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Self:
        """Enter the parser context, returning the parser instance.

        Implementations should perform any resource allocation here if not
        done in __init__ (e.g. creating API clients or temp directories).

        Returns
        -------
        Self
            The parser instance itself.
        """
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the parser context and release all resources.

        Implementations must clean up all temporary files and other resources
        regardless of whether an exception occurred.

        Parameters
        ----------
        exc_type:
            The exception class, or None if no exception was raised.
        exc_val:
            The exception instance, or None.
        exc_tb:
            The traceback, or None.
        """
        ...
