"""
BIM (IFC) document parser.

Implements the three DocumentParser hooks the consumer pipeline calls:
  - parse()         — extract searchable structured text from the IFC
  - get_thumbnail() — render an isometric SVG via ifcopenshell.geom
                      + matplotlib
  - extract_metadata() — emit project/schema/counts as Paperless metadata

We also synthesise an LLM summary (via paperless_bim.summary) and prepend
it to ``self.text`` so DocRead Q&A and full-text search both benefit.
"""
from __future__ import annotations

from pathlib import Path

from documents.parsers import DocumentParser
from documents.parsers import ParseError

from paperless_bim.ifc_extract import extract_metadata
from paperless_bim.ifc_extract import extract_text
from paperless_bim.ifc_extract import is_ifc_file
from paperless_bim.thumbnail import render_thumbnail


class BimDocumentParser(DocumentParser):
    """Parser for IFC (BIM) files."""

    logging_name = "paperless.parsing.bim"

    def parse(self, document_path: Path, mime_type: str, file_name=None):
        if not is_ifc_file(document_path):
            raise ParseError(
                f"Not a valid IFC file (missing ISO-10303-21 header): "
                f"{document_path}",
            )

        try:
            ifc_text = extract_text(document_path)
        except Exception as exc:  # ifcopenshell can raise broad errors
            raise ParseError(f"Failed to parse IFC file {document_path}: {exc}") from exc

        # Try LLM summary; on failure fall back to raw extracted text so the
        # consumer still stores something searchable.
        summary = None
        try:
            from paperless_bim.summary import summarize_ifc_text

            summary = summarize_ifc_text(ifc_text)
        except Exception as exc:
            self.log.warning(
                "BIM summary step failed (using raw extracted text): %s",
                exc,
            )

        if summary:
            self.text = f"[BIM 摘要]\n{summary}\n\n[IFC 结构化抽取]\n{ifc_text}"
        else:
            self.text = ifc_text

        # The IFC file itself acts as the archive: we don't re-encode.
        self.archive_path = Path(document_path)

        # Try to find a project creation date on the model
        self.date = None

    def extract_metadata(self, document_path, mime_type):
        try:
            return extract_metadata(document_path)
        except Exception as exc:  # pragma: no cover
            self.log.warning(
                "Failed to extract BIM metadata for %s: %s",
                document_path, exc,
            )
            return []

    def get_thumbnail(self, document_path, mime_type, file_name=None):
        thumb_path = Path(self.tempdir) / "thumbnail.svg"
        try:
            render_thumbnail(document_path, thumb_path)
        except Exception as exc:
            raise ParseError(
                f"Failed to render BIM thumbnail for {document_path}: {exc}",
            ) from exc
        return thumb_path

    def get_page_count(self, document_path, mime_type):  # pragma: no cover
        return None

    def get_settings(self):  # pragma: no cover
        from paperless.config import OutputTypeConfig

        return OutputTypeConfig()
