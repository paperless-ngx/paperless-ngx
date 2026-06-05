"""
Built-in remote-OCR document parser.

Handles documents by sending them to a configured remote OCR engine and
retrieving the extracted text. Two engines are supported:

* ``azureai`` — Azure AI Vision / Document Intelligence. Returns both the
  extracted text and a searchable PDF with an embedded text layer, which
  is stored as the archive copy.
* ``mineru`` — a self-hosted `MinerU <https://github.com/opendatalab/mineru>`_
  server. Returns Markdown text only via the synchronous ``/file_parse``
  API; no archive PDF is produced (text-only), so the original file remains
  the viewable document.

When no engine is configured, ``score()`` returns ``None`` so the parser
is effectively invisible to the registry — the tesseract parser handles
these MIME types instead.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Self

from django.conf import settings

from paperless.version import __full_version_str__

if TYPE_CHECKING:
    import datetime
    from types import TracebackType

    from paperless.parsers import MetadataEntry
    from paperless.parsers import ParserContext

logger = logging.getLogger("paperless.parsing.remote")

# MinerU document parsing can take a while for large documents; allow a
# generous timeout for the synchronous /file_parse call.
_MINERU_TIMEOUT_SECONDS: int = 600

_SUPPORTED_MIME_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
    "image/bmp": ".bmp",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


class RemoteEngineConfig:
    """Holds and validates the remote OCR engine configuration."""

    def __init__(
        self,
        engine: str | None,
        api_key: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        self.engine = engine
        self.api_key = api_key
        self.endpoint = endpoint

    def engine_is_valid(self) -> bool:
        """Return True when the engine is known and fully configured.

        ``azureai`` requires both an API key and an endpoint. ``mineru`` is
        self-hosted and only requires an endpoint (the MinerU API base URL).

        Returns
        -------
        bool
            True when the configured engine has all required settings.
        """
        if self.engine == "azureai":
            return self.api_key is not None and self.endpoint is not None
        if self.engine == "mineru":
            return self.endpoint is not None
        return False


class RemoteDocumentParser:
    """Parse documents via a remote OCR API (currently Azure AI Vision).

    This parser sends documents to a remote engine that returns both
    extracted text and a searchable PDF with an embedded text layer.
    It does not depend on Tesseract or ocrmypdf.

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

    name: str = "Paperless-ngx Remote OCR Parser"
    version: str = __full_version_str__
    author: str = "Paperless-ngx Contributors"
    url: str = "https://github.com/paperless-ngx/paperless-ngx"

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def supported_mime_types(cls) -> dict[str, str]:
        """Return the MIME types this parser can handle.

        The full set is always returned regardless of whether a remote
        engine is configured.  The ``score()`` method handles the
        "am I active?" logic by returning ``None`` when not configured.

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
        """Return the priority score for handling this file, or None.

        Returns ``None`` when no valid remote engine is configured,
        making the parser invisible to the registry for this file.
        When configured, returns 20 — higher than the Tesseract parser's
        default of 10 — so the remote engine takes priority.

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
            20 when the remote engine is configured and the MIME type is
            supported, otherwise None.
        """
        config = RemoteEngineConfig(
            engine=settings.REMOTE_OCR_ENGINE,
            api_key=settings.REMOTE_OCR_API_KEY,
            endpoint=settings.REMOTE_OCR_ENDPOINT,
        )
        if not config.engine_is_valid():
            return None
        if mime_type not in _SUPPORTED_MIME_TYPES:
            return None
        return 20

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def can_produce_archive(self) -> bool:
        """Whether this parser can produce a searchable PDF archive copy.

        Returns
        -------
        bool
            True for the Azure engine, which returns a PDF with an embedded
            text layer that serves as the archive copy. False for the MinerU
            engine, which is text-only and produces no archive PDF.
        """
        return settings.REMOTE_OCR_ENGINE != "mineru"

    @property
    def requires_pdf_rendition(self) -> bool:
        """Whether the parser must produce a PDF for the frontend to display.

        Returns
        -------
        bool
            Always False — all supported originals are displayable by
            the browser (PDF) or handled via the archive copy (images).
        """
        return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, logging_group: object = None) -> None:
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        self._tempdir = Path(
            tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR),
        )
        self._logging_group = logging_group
        self._text: str | None = None
        self._archive_path: Path | None = None

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
        """Send the document to the remote engine and store results.

        Parameters
        ----------
        document_path:
            Absolute path to the document file to parse.
        mime_type:
            Detected MIME type of the document.
        produce_archive:
            Ignored. The Azure engine always returns a searchable PDF that
            is stored as the archive copy; the MinerU engine is text-only and
            never produces an archive.
        """
        config = RemoteEngineConfig(
            engine=settings.REMOTE_OCR_ENGINE,
            api_key=settings.REMOTE_OCR_API_KEY,
            endpoint=settings.REMOTE_OCR_ENDPOINT,
        )

        if not config.engine_is_valid():
            logger.warning(
                "No valid remote parser engine is configured, content will be empty.",
            )
            self._text = ""
            return

        if config.engine == "azureai":
            self._text = self._azure_ai_vision_parse(document_path, config)
        elif config.engine == "mineru":
            self._text = self._mineru_parse(document_path, config)

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def get_text(self) -> str:
        """Return the plain-text content extracted during parse."""
        return self._text or ""

    def get_date(self) -> datetime.datetime | None:
        """Return the document date detected during parse.

        Returns
        -------
        datetime.datetime | None
            Always None — the remote parser does not detect dates.
        """
        return None

    def get_archive_path(self) -> Path | None:
        """Return the path to the generated archive PDF, or None."""
        return self._archive_path

    # ------------------------------------------------------------------
    # Thumbnail and metadata
    # ------------------------------------------------------------------

    def get_thumbnail(self, document_path: Path, mime_type: str) -> Path:
        """Generate a thumbnail image for the document.

        Uses the archive PDF produced by the remote engine when available,
        otherwise falls back to the original document path (PDF inputs).

        Parameters
        ----------
        document_path:
            Absolute path to the source document.
        mime_type:
            Detected MIME type of the document.

        Returns
        -------
        Path
            Path to the generated WebP thumbnail inside the temp directory.
        """
        # make_thumbnail_from_pdf lives in documents.parsers for now;
        # it will move to paperless.parsers.utils when the tesseract
        # parser is migrated in a later phase.
        from documents.parsers import make_thumbnail_from_pdf

        return make_thumbnail_from_pdf(
            self._archive_path or document_path,
            self._tempdir,
            self._logging_group,
        )

    def get_page_count(
        self,
        document_path: Path,
        mime_type: str,
    ) -> int | None:
        """Return the number of pages in a PDF document.

        Parameters
        ----------
        document_path:
            Absolute path to the source document.
        mime_type:
            Detected MIME type of the document.

        Returns
        -------
        int | None
            Page count for PDF inputs, or ``None`` for other MIME types.
        """
        if mime_type != "application/pdf":
            return None

        from paperless.parsers.utils import get_page_count_for_pdf

        return get_page_count_for_pdf(document_path, log=logger)

    def extract_metadata(
        self,
        document_path: Path,
        mime_type: str,
    ) -> list[MetadataEntry]:
        """Extract format-specific metadata from the document.

        Delegates to the shared pikepdf-based extractor for PDF files.
        Returns ``[]`` for all other MIME types.

        Parameters
        ----------
        document_path:
            Absolute path to the file to extract metadata from.
        mime_type:
            MIME type of the file.  May be ``"application/pdf"`` when
            called for the archive version of an image original.

        Returns
        -------
        list[MetadataEntry]
            Zero or more metadata entries.
        """
        if mime_type != "application/pdf":
            return []

        from paperless.parsers.utils import extract_pdf_metadata

        return extract_pdf_metadata(document_path, log=logger)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _azure_ai_vision_parse(
        self,
        file: Path,
        config: RemoteEngineConfig,
    ) -> str | None:
        """Send ``file`` to Azure AI Document Intelligence and return text.

        Downloads the searchable PDF output from Azure and stores it at
        ``self._archive_path``.  Returns the extracted text content, or
        ``None`` on failure (the error is logged).

        Parameters
        ----------
        file:
            Absolute path to the document to analyse.
        config:
            Validated remote engine configuration.

        Returns
        -------
        str | None
            Extracted text, or None if the Azure call failed.
        """
        if TYPE_CHECKING:
            # Callers must have already validated config via engine_is_valid():
            # engine_is_valid() asserts api_key is not None and (for azureai)
            # endpoint is not None, so these casts are provably safe.
            assert config.endpoint is not None
            assert config.api_key is not None

        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
        from azure.ai.documentintelligence.models import AnalyzeOutputOption
        from azure.ai.documentintelligence.models import DocumentContentFormat
        from azure.core.credentials import AzureKeyCredential

        client = DocumentIntelligenceClient(
            endpoint=config.endpoint,
            credential=AzureKeyCredential(config.api_key),
        )

        try:
            with file.open("rb") as f:
                analyze_request = AnalyzeDocumentRequest(bytes_source=f.read())
                poller = client.begin_analyze_document(
                    model_id="prebuilt-read",
                    body=analyze_request,
                    output_content_format=DocumentContentFormat.TEXT,
                    output=[AnalyzeOutputOption.PDF],
                    content_type="application/json",
                )

            poller.wait()
            result_id = poller.details["operation_id"]
            result = poller.result()

            self._archive_path = self._tempdir / "archive.pdf"
            with self._archive_path.open("wb") as f:
                for chunk in client.get_analyze_result_pdf(
                    model_id="prebuilt-read",
                    result_id=result_id,
                ):
                    f.write(chunk)

            return result.content

        except Exception as e:
            logger.exception("Azure AI Vision parsing failed: %s", e)

        finally:
            client.close()

        return None

    def _mineru_parse(
        self,
        file: Path,
        config: RemoteEngineConfig,
    ) -> str | None:
        """Send ``file`` to a self-hosted MinerU server and return its text.

        Performs a synchronous ``POST {endpoint}/file_parse`` request and
        returns the Markdown content extracted by MinerU. No archive PDF is
        produced — MinerU returns text only, so ``self._archive_path`` is left
        unset and the original file remains the viewable document.

        Parameters
        ----------
        file:
            Absolute path to the document to parse.
        config:
            Validated remote engine configuration. ``config.endpoint`` is the
            MinerU API base URL (e.g. ``http://host:8000``).

        Returns
        -------
        str | None
            Extracted Markdown text, or None if the MinerU call failed (the
            error is logged).

        Examples
        --------
        >>> # With PAPERLESS_REMOTE_OCR_ENGINE=mineru and
        >>> # PAPERLESS_REMOTE_OCR_ENDPOINT=http://host:8000 configured:
        >>> parser._mineru_parse(Path("/tmp/doc.pdf"), config)  # doctest: +SKIP
        '# Document title\\n\\nBody text...'
        """
        if TYPE_CHECKING:
            # Callers must have validated config via engine_is_valid(), which
            # asserts endpoint is not None for the mineru engine.
            assert config.endpoint is not None

        import httpx

        url = f"{config.endpoint.rstrip('/')}/file_parse"

        try:
            with file.open("rb") as fh:
                response = httpx.post(
                    url,
                    files={"files": (file.name, fh, "application/octet-stream")},
                    data={
                        "return_md": "true",
                        "response_format_zip": "false",
                    },
                    timeout=_MINERU_TIMEOUT_SECONDS,
                )
            response.raise_for_status()

            results = response.json().get("results", {})
            for entry in results.values():
                md_content = entry.get("md_content")
                if md_content is not None:
                    return md_content

            logger.warning("MinerU response contained no markdown content.")
            return ""

        except Exception as e:
            logger.exception("MinerU parsing failed: %s", e)

        return None
