"""
Shared utilities for Paperless-ngx document parsers.

Functions here are format-neutral helpers that multiple parsers need.
Keeping them here avoids parsers inheriting from each other just to
share implementation.
"""

from __future__ import annotations

import codecs
import logging
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final

if TYPE_CHECKING:
    from paperless.parsers import MetadataEntry

logger = logging.getLogger("paperless.parsers.utils")

# Minimum character count for a PDF to be considered "born-digital" (has real text).
# Used by both the consumer (archive decision) and the tesseract parser (skip-OCR decision).
PDF_TEXT_MIN_LENGTH: Final[int] = 50


def is_tagged_pdf(
    path: Path,
    log: logging.Logger | None = None,
) -> bool:
    """Return True if the PDF declares itself as tagged (born-digital indicator).

    Tagged PDFs (e.g. exported from Word or LibreOffice) have ``/MarkInfo``
    with ``/Marked true`` in the document root.  This is a reliable signal
    that the document has a logical structure and embedded text — running OCR
    on it is unnecessary and archive generation can be skipped.

    https://github.com/ocrmypdf/OCRmyPDF/blob/4e974ebd465a5921b2e79004f098f5d203010282/src/ocrmypdf/pdfinfo/info.py#L449

    Parameters
    ----------
    path:
        Absolute path to the PDF file.
    log:
        Logger for warnings.  Falls back to the module-level logger when omitted.

    Returns
    -------
    bool
        ``True`` when the PDF is tagged, ``False`` otherwise or on any error.
    """
    import pikepdf

    _log = log or logger
    try:
        with pikepdf.open(path) as pdf:
            mark_info = pdf.Root.get("/MarkInfo")
            if mark_info is None:
                return False
            return bool(mark_info.get("/Marked", False))
    except Exception:
        _log.warning("Could not check PDF tag status for %s", path, exc_info=True)
        return False


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


def post_process_text(text: str | None) -> str | None:
    """Normalize extracted PDF/OCR text: collapse whitespace, strip padding.

    Returns ``None`` for ``None`` or whitespace-only input, so callers can
    treat "no text" and "only layout padding" the same way.
    """
    if not text:
        return None

    collapsed_spaces = re.sub(r"([^\S\r\n]+)", " ", text)
    no_leading_whitespace = re.sub(r"([\n\r]+)([^\S\n\r]+)", "\\1", collapsed_spaces)
    no_trailing_whitespace = re.sub(r"([^\S\n\r]+)$", "", no_leading_whitespace)

    # replace \0 prevents issues with saving to postgres.
    # text may contain \0 when this character is present in PDF files.
    result = no_trailing_whitespace.strip().replace("\0", " ")
    return result or None


def is_born_digital_text(
    text: str | None,
    path: Path,
    log: logging.Logger | None = None,
) -> bool:
    """Decide whether already-extracted, normalized PDF text counts as born-digital.

    This is the single source of truth for "does this PDF already have real
    text", used both to decide whether to produce an archive file and to
    decide whether OCR can be skipped. Both decisions must agree, or a
    tagged-but-textless PDF can end up with no archive AND a forced OCR pass
    (see GH #13387): raw ``pdftotext -layout`` output can be non-empty
    (whitespace/form-feed padding) even when there is no real content, so
    *text* must already be normalized via :func:`post_process_text`, not the
    raw extraction.

    Parameters
    ----------
    text:
        The normalized extracted text (or ``None``) to evaluate.
    path:
        Absolute path to the PDF file, used for the tagged-PDF check.
    log:
        Logger for warnings.  Falls back to the module-level logger when omitted.

    Returns
    -------
    bool
        Whether the PDF counts as born-digital (has real text, and is either
        tagged or exceeds ``PDF_TEXT_MIN_LENGTH``).
    """
    if not text:
        return False
    return is_tagged_pdf(path, log=log) or len(text) > PDF_TEXT_MIN_LENGTH


def pdf_born_digital_text(
    path: Path,
    log: logging.Logger | None = None,
) -> tuple[str | None, bool]:
    """Extract a PDF's text and decide whether it should be treated as born-digital.

    Convenience wrapper around :func:`is_born_digital_text` for callers that
    don't already have the PDF's text extracted (e.g. the archive-generation
    decision, which runs before any parser has touched the file).

    Parameters
    ----------
    path:
        Absolute path to the PDF file.
    log:
        Logger for warnings.  Falls back to the module-level logger when omitted.

    Returns
    -------
    tuple[str | None, bool]
        The normalized extracted text (or ``None``), and whether the PDF
        counts as born-digital.
    """
    text = post_process_text(extract_pdf_text(path, log=log))
    return text, is_born_digital_text(text, path, log=log)


def read_file_handle_unicode_errors(
    filepath: Path,
    log: logging.Logger | None = None,
) -> str:
    """Read a file as text, detecting encoding via BOM and stripping NUL bytes.

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
        File content as a string, with NUL bytes removed so the result is
        safe to store in PostgreSQL text fields.
    """
    _log = log or logger
    raw = filepath.read_bytes()

    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encoding = "utf-16"
    elif raw.startswith(codecs.BOM_UTF8):
        encoding = "utf-8-sig"
    else:
        encoding = "utf-8"

    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError as e:
        _log.warning("Unicode error during text reading, continuing: %s", e)
        text = raw.decode("utf-8", errors="replace")

    # PostgreSQL rejects NUL (0x00) bytes in text fields
    return text.replace("\x00", "")


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
