"""
Built-in remote-OCR document parser.

Handles documents by sending them to a configured remote OCR engine and
retrieving both the extracted text and a searchable PDF with an embedded
text layer.  Two engines are supported:

* ``azureai`` — Azure AI Vision / Document Intelligence, which returns a
  ready-made searchable PDF.
* ``mistral`` — Mistral OCR (``mistral-ocr-latest``), which returns markdown
  text plus paragraph-level bounding boxes.  Because Mistral does not return
  a PDF, the searchable archive is assembled locally by rendering an
  invisible text layer over the page image via ocrmypdf's fpdf2 renderer.

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

    from ocrmypdf.models.ocr_element import BoundingBox
    from ocrmypdf.models.ocr_element import OcrElement

    from paperless.parsers import MetadataEntry
    from paperless.parsers import ParserContext

logger = logging.getLogger("paperless.parsing.remote")

_SUPPORTED_MIME_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
    "image/bmp": ".bmp",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

#: Default base URL for the hosted Mistral OCR API.  Overridable via
#: ``PAPERLESS_REMOTE_OCR_ENDPOINT`` for self-hosted deployments.
MISTRAL_DEFAULT_ENDPOINT: str = "https://api.mistral.ai"

#: Mistral OCR model identifier.
MISTRAL_OCR_MODEL: str = "mistral-ocr-latest"

#: Request timeout (seconds) for a single Mistral OCR call.  OCR of large
#: documents can take a while, so this is intentionally generous.
MISTRAL_OCR_TIMEOUT: float = 600.0

#: DPI used to rasterise PDF pages before overlaying the invisible text
#: layer.  Only relevant for the Mistral engine.
_RENDER_DPI: int = 200


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

        Both engines require an API key.  ``azureai`` additionally requires
        an endpoint; ``mistral`` defaults to the hosted endpoint when none is
        given, so an endpoint is optional there.
        """
        if self.api_key is None:
            return False
        if self.engine == "azureai":
            return self.endpoint is not None
        return self.engine == "mistral"


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
            Always True — the remote engine always returns a PDF with an
            embedded text layer that serves as the archive copy.
        """
        return True

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
            Ignored — the remote engine always returns a searchable PDF,
            which is stored as the archive copy regardless of this flag.
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
        elif config.engine == "mistral":
            self._text = self._mistral_ocr_parse(document_path, mime_type, config)

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

    def _mistral_ocr_parse(
        self,
        file: Path,
        mime_type: str,
        config: RemoteEngineConfig,
    ) -> str | None:
        """Send ``file`` to the Mistral OCR API and return the extracted text.

        Mistral returns markdown text plus paragraph-level bounding boxes but
        no PDF, so a searchable archive is assembled locally and stored at
        ``self._archive_path``.  Returns the extracted text, or ``None`` on
        failure (the error is logged and the archive path is cleared).

        Parameters
        ----------
        file:
            Absolute path to the document to analyse.
        mime_type:
            Detected MIME type of the document.
        config:
            Validated remote engine configuration.

        Returns
        -------
        str | None
            Extracted text, or None if the Mistral call failed.
        """
        if TYPE_CHECKING:
            # engine_is_valid() guarantees api_key is not None for mistral.
            assert config.api_key is not None

        import httpx

        endpoint = (config.endpoint or MISTRAL_DEFAULT_ENDPOINT).rstrip("/")
        url = f"{endpoint}/v1/ocr"

        document_uri = _data_uri(mime_type, file.read_bytes())
        if mime_type == "application/pdf":
            document = {"type": "document_url", "document_url": document_uri}
        else:
            document = {"type": "image_url", "image_url": document_uri}

        payload = {
            "model": MISTRAL_OCR_MODEL,
            "document": document,
            "include_blocks": True,
        }
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(
                url,
                json=payload,
                headers=headers,
                timeout=MISTRAL_OCR_TIMEOUT,
            )
            response.raise_for_status()
            pages = response.json().get("pages", [])

            self._archive_path = self._tempdir / "archive.pdf"
            self._build_searchable_pdf(file, mime_type, pages, self._archive_path)

            return _mistral_pages_to_text(pages)

        except Exception as e:
            logger.exception("Mistral OCR parsing failed: %s", e)
            self._archive_path = None

        return None

    def _build_searchable_pdf(
        self,
        source: Path,
        mime_type: str,
        pages: list[dict],
        out_path: Path,
    ) -> None:
        """Assemble a searchable PDF from the original file and OCR results.

        Each page image (rasterised from PDF input, or the image itself) is
        rendered with an invisible text layer positioned using Mistral's
        paragraph-level bounding boxes, using ocrmypdf's fpdf2 renderer and
        its bundled Unicode font.  The per-page PDFs are merged into
        ``out_path``.

        Parameters
        ----------
        source:
            Absolute path to the original document.
        mime_type:
            Detected MIME type of the original document.
        pages:
            The ``pages`` array returned by the Mistral OCR API.
        out_path:
            Destination path for the merged searchable PDF.
        """
        import ocrmypdf
        import pikepdf
        from ocrmypdf.font import MultiFontManager
        from ocrmypdf.fpdf_renderer import Fpdf2PdfRenderer

        images = _load_page_images(source, mime_type, _RENDER_DPI)
        font_dir = Path(ocrmypdf.__file__).parent / "data"
        font_manager = MultiFontManager(font_dir)

        merged = pikepdf.Pdf.new()
        opened: list = []
        try:
            for index, image in enumerate(images):
                page_data = pages[index] if index < len(pages) else {}

                image_path = self._tempdir / f"page-{index}.png"
                image.save(image_path)

                ocr_page = _build_ocr_page(
                    page_data,
                    image.width,
                    image.height,
                    _RENDER_DPI,
                )

                page_pdf_path = self._tempdir / f"page-{index}.pdf"
                Fpdf2PdfRenderer(
                    page=ocr_page,
                    dpi=_RENDER_DPI,
                    multi_font_manager=font_manager,
                    invisible_text=True,
                    image=image_path,
                ).render(page_pdf_path)

                page_pdf = pikepdf.open(page_pdf_path)
                opened.append(page_pdf)
                merged.pages.extend(page_pdf.pages)

            merged.save(out_path)
        finally:
            for page_pdf in opened:
                page_pdf.close()
            merged.close()


# ----------------------------------------------------------------------
# Mistral OCR helpers (pure, framework-independent)
# ----------------------------------------------------------------------


def _data_uri(mime_type: str, data: bytes) -> str:
    """Encode ``data`` as a ``data:`` URI for the given MIME type."""
    import base64

    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _mistral_pages_to_text(pages: list[dict]) -> str:
    """Concatenate the markdown content of every page, blank pages dropped."""
    parts = [str(page.get("markdown", "")).strip() for page in pages]
    return "\n\n".join(part for part in parts if part)


def _block_text(block: dict) -> str:
    """Best-effort extraction of a block's text content."""
    for key in ("markdown", "text", "content"):
        value = block.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _block_bounding_box(block: dict) -> tuple[float, float, float, float] | None:
    """Best-effort extraction of a block bbox as ``(left, top, right, bottom)``.

    Supports the bounding-box shapes Mistral has used across API revisions:
    a ``bbox`` list ``[x0, y0, x1, y1]``, a ``bbox`` dict with
    ``left/top/right/bottom``, or the image-style
    ``top_left_x/top_left_y/bottom_right_x/bottom_right_y`` keys (either nested
    under ``bbox`` or directly on the block).  Returns ``None`` when no usable
    box is present.
    """
    corner_keys = ("top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y")
    edge_keys = ("left", "top", "right", "bottom")

    candidates = [block.get("bbox"), block]
    for candidate in candidates:
        if isinstance(candidate, (list, tuple)) and len(candidate) == 4:
            try:
                return tuple(float(v) for v in candidate)  # type: ignore[return-value]
            except (TypeError, ValueError):
                continue
        if isinstance(candidate, dict):
            for keys in (edge_keys, corner_keys):
                if all(k in candidate for k in keys):
                    try:
                        return tuple(float(candidate[k]) for k in keys)  # type: ignore[return-value]
                    except (TypeError, ValueError):
                        continue
    return None


def _clamp_bbox(
    left: float,
    top: float,
    right: float,
    bottom: float,
    max_width: float,
    max_height: float,
) -> BoundingBox | None:
    """Clamp a bbox to the page and return a valid ``BoundingBox`` or ``None``.

    ``BoundingBox`` rejects degenerate boxes (``right <= left`` etc.), so this
    also filters out empty or inverted boxes.
    """
    from ocrmypdf.models.ocr_element import BoundingBox

    left = max(0.0, min(left, max_width))
    right = max(0.0, min(right, max_width))
    top = max(0.0, min(top, max_height))
    bottom = max(0.0, min(bottom, max_height))
    if right <= left or bottom <= top:
        return None
    return BoundingBox(left, top, right, bottom)


def _text_band_elements(
    text: str,
    left: float,
    top: float,
    right: float,
    bottom: float,
    max_width: float,
    max_height: float,
    dpi: float,
) -> list[OcrElement]:
    """Lay ``text`` into one thin invisible ``ocr_line`` band per text line.

    A single tall box makes the fpdf2 renderer scale text so aggressively that
    the glyphs become unrecoverable, so the box is divided into one horizontal
    band per line of text and each band's height is capped to roughly a single
    line.  Returns the resulting ``ocr_line`` elements (each wrapping one
    ``ocrx_word``); an empty list when there is no usable text.
    """
    from ocrmypdf.models.ocr_element import OcrElement

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    band_cap = dpi * 0.3
    slot = (bottom - top) / len(lines)
    elements: list[OcrElement] = []
    for index, line in enumerate(lines):
        band_top = top + index * slot
        band_bottom = band_top + min(slot, band_cap)
        bbox = _clamp_bbox(left, band_top, right, band_bottom, max_width, max_height)
        if bbox is None:
            continue
        word = OcrElement(ocr_class="ocrx_word", text=line, bbox=bbox)
        elements.append(OcrElement(ocr_class="ocr_line", bbox=bbox, children=[word]))
    return elements


def _build_ocr_page(
    page_data: dict,
    image_width: int,
    image_height: int,
    dpi: float,
) -> OcrElement:
    """Build an ``OcrElement`` page tree from a Mistral OCR page result.

    Each content block's text is laid into thin invisible bands positioned at
    the block's (scaled) bounding box.  When no usable blocks are present, the
    whole page markdown is laid across the full page instead, so the archive
    stays searchable either way.
    """
    from ocrmypdf.models.ocr_element import BoundingBox
    from ocrmypdf.models.ocr_element import OcrElement

    dimensions = page_data.get("dimensions") or {}
    source_width = dimensions.get("width") or image_width
    source_height = dimensions.get("height") or image_height
    scale_x = image_width / source_width if source_width else 1.0
    scale_y = image_height / source_height if source_height else 1.0

    children: list[OcrElement] = []
    for block in page_data.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        text = _block_text(block)
        box = _block_bounding_box(block)
        if not text or box is None:
            continue
        left, top, right, bottom = box
        children.extend(
            _text_band_elements(
                text,
                left * scale_x,
                top * scale_y,
                right * scale_x,
                bottom * scale_y,
                image_width,
                image_height,
                dpi,
            ),
        )

    if not children:
        # Fallback: no positioned blocks — keep the page searchable by laying
        # the full markdown text across the whole page as invisible text.
        children.extend(
            _text_band_elements(
                str(page_data.get("markdown", "")).strip(),
                0,
                0,
                image_width,
                image_height,
                image_width,
                image_height,
                dpi,
            ),
        )

    return OcrElement(
        ocr_class="ocr_page",
        bbox=BoundingBox(0, 0, image_width, image_height),
        dpi=dpi,
        page_number=page_data.get("index", 0),
        children=children,
    )


def _load_page_images(source: Path, mime_type: str, dpi: int) -> list:
    """Return one RGB ``PIL.Image`` per page of the source document.

    PDF input is rasterised with pdf2image; image input (including multi-frame
    TIFF) is loaded directly, one entry per frame.
    """
    from PIL import Image
    from PIL import ImageSequence

    if mime_type == "application/pdf":
        from pdf2image import convert_from_path

        return convert_from_path(source, dpi=dpi)

    with Image.open(source) as opened:
        return [frame.convert("RGB") for frame in ImageSequence.Iterator(opened)]
