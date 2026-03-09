"""
paperless.parsers
=================

Public interface for the Paperless-ngx parser plugin system.

This module defines :class:`ParserProtocol` — the structural contract that
every document parser must satisfy — whether it is a built-in parser shipped
with Paperless-ngx or a third-party parser installed via a Python entrypoint.

Phase 1/2 scope
---------------
Only the Protocol is defined here.  The transitional :class:`DocumentParser`
ABC (Phase 3) and concrete built-in parsers (Phase 3+) will be added in later
phases, so there are intentionally no imports of parser implementations here.

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

from typing import TYPE_CHECKING
from typing import Protocol
from typing import Self
from typing import runtime_checkable

if TYPE_CHECKING:
    import datetime
    from pathlib import Path

__all__ = [
    "ParserProtocol",
]


@runtime_checkable
class ParserProtocol(Protocol):
    """Structural contract for all Paperless-ngx document parsers.

    Both built-in parsers and third-party plugins (discovered via the
    ``paperless_ngx.parsers`` entrypoint group) must satisfy this Protocol.
    Because it is decorated with :func:`typing.runtime_checkable`,
    ``isinstance(obj, ParserProtocol)`` works at runtime based on method
    presence, which is useful for validation in :meth:`ParserRegistry.discover`.

    Class-level identity attributes
    --------------------------------
    Parsers are required to expose four string attributes at the **class**
    level so the registry can log attribution information without
    instantiating the parser:

    name : str
        Human-readable parser name (e.g. ``"Tesseract OCR"``).
    version : str
        Semantic version string (e.g. ``"1.2.3"``).
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

        The keys are MIME type strings (e.g. ``"application/pdf"``), and the
        values are the preferred file extension **including** the leading dot
        (e.g. ``".pdf"``).  The registry uses this mapping both to decide
        whether a parser is a candidate for a given file and to determine the
        default extension when creating archive copies.

        Returns
        -------
        dict[str, str]
            ``{mime_type: extension}`` mapping — may be empty if the parser
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
        """Return a priority score for handling ``mime_type`` on ``filename``.

        The registry calls this method after confirming that the MIME type is
        in :meth:`supported_mime_types`.  Parsers may inspect ``filename``
        (and optionally the file at ``path``) to refine their confidence level.

        A higher score wins.  Return ``None`` to explicitly decline handling
        a file even though the MIME type is listed as supported (e.g. when the
        parser detects a feature flag is disabled, or a licence has expired).

        Parameters
        ----------
        mime_type:
            The detected MIME type of the file to be parsed.
        filename:
            The original filename, including extension.
        path:
            Optional filesystem path to the file.  Parsers that need to
            inspect file content (e.g. magic-byte sniffing) may use this.
            The path may be ``None`` when scoring happens before the file
            is available locally.

        Returns
        -------
        int | None
            Priority score (higher wins), or ``None`` to decline.
        """
        ...

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def can_produce_archive(self) -> bool:
        """Whether this parser can produce a searchable PDF archive copy.

        If ``True``, the consumption pipeline will request an archive version
        when the document is processed.  If ``False``, only the thumbnail and
        text extraction will be performed.
        """
        ...

    @property
    def requires_pdf_rendition(self) -> bool:
        """Whether the parser requires a pre-rendered PDF before parsing.

        Some parsers (e.g. image-based OCR engines) work on rasterised PDFs
        rather than the original file.  When ``True``, the pipeline will
        convert the source document to PDF before calling :meth:`parse`.
        """
        ...

    # ------------------------------------------------------------------
    # Core parsing interface
    # ------------------------------------------------------------------

    def parse(
        self,
        document_path: Path,
        mime_type: str,
        file_name: str | None = None,
        *,
        produce_archive: bool = True,
    ) -> None:
        """Parse ``document_path`` and populate internal state.

        After a successful call, callers retrieve results via
        :meth:`get_text`, :meth:`get_date`, and :meth:`get_archive_path`.

        Parameters
        ----------
        document_path:
            Absolute path to the document file to parse.
        mime_type:
            Detected MIME type of the document.
        file_name:
            Original filename as provided by the user.  May differ from the
            stem of ``document_path`` (which is usually a UUID-based name).
        produce_archive:
            When ``True`` (the default) and :attr:`can_produce_archive` is
            also ``True``, the parser should produce a searchable PDF at the
            path returned by :meth:`get_archive_path`.  Pass ``False`` when
            only text extraction and thumbnail generation are required and
            disk I/O should be minimised.

        Raises
        ------
        documents.parsers.ParseError
            If parsing fails for any reason.  The consumption pipeline will
            catch this and handle failure appropriately.
        """
        ...

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def get_text(self) -> str | None:
        """Return the plain-text content extracted during :meth:`parse`.

        Returns
        -------
        str | None
            Extracted text, or ``None`` if no text could be found.
        """
        ...

    def get_date(self) -> datetime.datetime | None:
        """Return the document date detected during :meth:`parse`.

        Returns
        -------
        datetime.datetime | None
            Detected document date, or ``None`` if no date was found.
        """
        ...

    def get_archive_path(self) -> Path | None:
        """Return the path to the generated archive PDF (if any).

        Returns
        -------
        Path | None
            Path to the searchable PDF archive, or ``None`` if no archive
            was produced (e.g. because ``produce_archive=False`` was passed
            to :meth:`parse`, or the parser does not support archive
            production).
        """
        ...

    # ------------------------------------------------------------------
    # Thumbnail and metadata
    # ------------------------------------------------------------------

    def get_thumbnail(
        self,
        document_path: Path,
        mime_type: str,
        file_name: str | None = None,
    ) -> Path:
        """Generate and return the path to a thumbnail image for the document.

        Unlike :meth:`parse`, this method may be called independently of
        :meth:`parse`.  The returned path must point to an existing WebP image
        file inside the parser's temporary working directory.

        Parameters
        ----------
        document_path:
            Absolute path to the source document.
        mime_type:
            Detected MIME type of the document.
        file_name:
            Original filename.

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
            Page count, or ``None`` if the parser cannot determine it.
        """
        ...

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Self:
        """Enter the parser context, returning the parser instance.

        Implementations should perform any resource allocation (e.g. creating
        a temporary working directory) here if not done in ``__init__``.

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
        exc_tb: object,
    ) -> None:
        """Exit the parser context and release resources.

        Implementations must clean up all temporary files and other
        resources regardless of whether an exception occurred.

        Parameters
        ----------
        exc_type:
            The exception class, or ``None`` if no exception was raised.
        exc_val:
            The exception instance, or ``None``.
        exc_tb:
            The traceback, or ``None``.
        """
        ...
