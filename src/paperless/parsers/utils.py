"""
Shared utilities for Paperless-ngx document parsers.

Functions here are format-neutral helpers that multiple parsers need.
Keeping them here avoids parsers inheriting from each other just to
share implementation.
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paperless.parsers import MetadataEntry

logger = logging.getLogger("paperless.parsers.utils")

# Minimum character count for a PDF to be considered "born-digital" (has real text).
# Used by both the consumer (archive decision) and the tesseract parser (skip-OCR decision).
PDF_TEXT_MIN_LENGTH = 50


def extract_pdf_text(
    path: Path,
    log: logging.Logger | None = None,
) -> str | None:
    """Run pdftotext on *path* and return the extracted text, or None on failure.

    Parameters
    ----------
    path:
        Absolute path to the PDF file.
    log:
        Logger for warnings.  Falls back to the module-level logger when omitted.

    Returns
    -------
    str | None
        Extracted text, or ``None`` if pdftotext fails or the file is not a PDF.
    """
    from documents.utils import run_subprocess

    _log = log or logger
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "text.txt"
            run_subprocess(
                [
                    "pdftotext",
                    "-q",
                    "-layout",
                    "-enc",
                    "UTF-8",
                    str(path),
                    str(out_path),
                ],
                logger=_log,
            )
            text = read_file_handle_unicode_errors(out_path, log=_log)
            return text or None
    except Exception:
        _log.warning(
            "Error while getting text from PDF document with pdftotext",
            exc_info=True,
        )
        return None


def read_file_handle_unicode_errors(
    filepath: Path,
    log: logging.Logger | None = None,
) -> str:
    """Read a file as UTF-8 text, replacing invalid bytes rather than raising.

    Parameters
    ----------
    filepath:
        Absolute path to the file to read.
    log:
        Logger to use for warnings.  Falls back to the module-level logger
        when omitted.

    Returns
    -------
    str
        File content as a string, with any invalid UTF-8 sequences replaced
        by the Unicode replacement character.
    """
    _log = log or logger
    try:
        return filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        _log.warning("Unicode error during text reading, continuing: %s", e)
        return filepath.read_bytes().decode("utf-8", errors="replace")


def get_page_count_for_pdf(
    document_path: Path,
    log: logging.Logger | None = None,
) -> int | None:
    """Return the number of pages in a PDF file using pikepdf.

    Parameters
    ----------
    document_path:
        Absolute path to the PDF file.
    log:
        Logger to use for warnings.  Falls back to the module-level logger
        when omitted.

    Returns
    -------
    int | None
        Page count, or ``None`` if the file cannot be opened or is not a
        valid PDF.
    """
    import pikepdf

    _log = log or logger

    try:
        with pikepdf.Pdf.open(document_path) as pdf:
            return len(pdf.pages)
    except Exception as e:
        _log.warning("Unable to determine PDF page count for %s: %s", document_path, e)
        return None


def extract_pdf_metadata(
    document_path: Path,
    log: logging.Logger | None = None,
) -> list[MetadataEntry]:
    """Extract XMP/PDF metadata from a PDF file using pikepdf.

    Reads all XMP metadata entries from the document and returns them as a
    list of ``MetadataEntry`` dicts.  The method never raises — any failure
    to open the file or read a specific key is logged and skipped.

    Parameters
    ----------
    document_path:
        Absolute path to the PDF file.
    log:
        Logger to use for warnings and debug messages.  Falls back to the
        module-level logger when omitted.

    Returns
    -------
    list[MetadataEntry]
        Zero or more metadata entries.  Returns ``[]`` if the file cannot
        be opened or contains no readable XMP metadata.
    """
    import pikepdf

    from paperless.parsers import MetadataEntry

    _log = log or logger
    result: list[MetadataEntry] = []
    namespace_pattern = re.compile(r"\{(.*)\}(.*)")

    try:
        pdf = pikepdf.open(document_path)
        meta = pdf.open_metadata()
    except Exception as e:
        _log.warning("Could not open PDF metadata for %s: %s", document_path, e)
        return []

    for key, value in meta.items():
        if isinstance(value, list):
            value = " ".join(str(e) for e in value)
        value = str(value)

        try:
            m = namespace_pattern.match(key)
            if m is None:
                continue

            namespace = m.group(1)
            key_value = m.group(2)

            try:
                namespace.encode("utf-8")
                key_value.encode("utf-8")
            except UnicodeEncodeError as enc_err:  # pragma: no cover
                _log.debug("Skipping metadata key %s: %s", key, enc_err)
                continue

            result.append(
                MetadataEntry(
                    namespace=namespace,
                    prefix=meta.REVERSE_NS[namespace],
                    key=key_value,
                    value=value,
                ),
            )
        except Exception as e:
            _log.warning(
                "Error reading metadata key %s value %s: %s",
                key,
                value,
                e,
            )

    return result
