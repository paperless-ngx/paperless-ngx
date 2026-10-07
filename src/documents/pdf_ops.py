"""
Pure PDF page operations used by documents.bulk_edit.

This module deliberately knows nothing about Django, Celery or the documents
app: callers resolve documents, choose output paths and queue work. Every
function that writes a PDF removes unreferenced resources before saving.

pikepdf is always called as ``pikepdf.open(...)`` / ``pikepdf.new()`` (never
``from pikepdf import open``) so tests can patch those module attributes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import NamedTuple

import pikepdf

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable
    from collections.abc import Mapping
    from collections.abc import Sequence
    from pathlib import Path
    from types import TracebackType


class PageSpec(NamedTuple):
    """One page of an output PDF: a 1-indexed source page, optionally rotated."""

    page: int
    rotate: int = 0  # relative degrees, 0 leaves the page alone


def _require_positive(pages: Iterable[int]) -> None:
    for page in pages:
        if page < 1:
            raise ValueError(f"Page numbers start at 1, got {page}")


def rotate_pdf(src: Path, dst: Path, degrees: int) -> None:
    """
    Rotate every page relatively on the opened document, not a rebuild, so Info,
    XMP and outlines are kept. ``src`` is not modified.
    """
    with pikepdf.open(src) as pdf:
        for page in pdf.pages:
            page.rotate(degrees, relative=True)
        pdf.remove_unreferenced_resources()
        pdf.save(dst)


def remove_pages(src: Path, dst: Path, pages: Iterable[int]) -> None:
    """
    Remove 1-indexed pages from the opened document, not a rebuild, so Info, XMP
    and outlines are kept. ``src`` is not modified.

    Duplicates are ignored. Pages are removed highest first so earlier removals
    never shift the index of later ones.
    """
    unique = sorted(set(pages))
    _require_positive(unique)
    with pikepdf.open(src) as pdf:
        for page_num in reversed(unique):
            del pdf.pages[page_num - 1]
        pdf.remove_unreferenced_resources()
        pdf.save(dst)


def build_pdfs(
    src: Path,
    outputs: Sequence[tuple[Sequence[PageSpec], Callable[[], Path]]],
) -> list[Path]:
    """
    Build one new PDF per output from pages of ``src``, opening ``src`` once.

    Each output is ``(page_specs, make_dst)``. Every page number is checked against
    ``src`` before any output is built, and ``make_dst`` is called after that
    output's pages are copied and immediately before it is saved, so a bad page
    number in any output never leaves a destination behind. Document-level data
    (Info, XMP, outlines) is not carried over. Returns the written paths in output
    order.
    """
    for specs, _ in outputs:
        _require_positive(spec.page for spec in specs)

    written: list[Path] = []
    with pikepdf.open(src) as source:
        page_count = len(source.pages)
        for specs, _ in outputs:
            for spec in specs:
                if spec.page > page_count:
                    raise IndexError(
                        f"Page {spec.page} is out of range, the PDF has "
                        f"{page_count} pages",
                    )
        for specs, make_dst in outputs:
            dst = pikepdf.new()
            for spec in specs:
                dst.pages.append(source.pages[spec.page - 1])
                if spec.rotate:
                    dst.pages[-1].rotate(spec.rotate, relative=True)
            dst.remove_unreferenced_resources()
            path = make_dst()
            dst.save(path)
            dst.close()
            written.append(path)
    return written


def validate_page_operations(
    operations: Sequence[Mapping[str, int]],
    *,
    single_output: bool,
) -> int:
    """
    Validate ``edit_pdf`` style operations and return the output document count.

    Each operation has ``page`` and optionally ``rotate`` and ``doc`` (the output
    document index, default 0). The bounds rule is kept as it was: a ``doc`` index
    must be below the number of operations.
    """
    if not operations:
        raise ValueError("Output document index is out of bounds")

    max_idx = max(op.get("doc", 0) for op in operations)
    if single_output and max_idx > 0:
        raise ValueError("Multiple output documents specified")

    if any(
        op.get("doc", 0) < 0 or op.get("doc", 0) >= len(operations) for op in operations
    ):
        raise ValueError("Output document index is out of bounds")

    return max_idx + 1


def needs_decrypt(src: Path) -> bool:
    """
    True if ``src`` is encrypted. A PDF that needs a password to open at all
    counts as encrypted.
    """
    try:
        with pikepdf.open(src) as pdf:
            return bool(pdf.is_encrypted)
    except pikepdf.PasswordError:
        return True


def decrypt_pdf(src: Path, make_dst: Callable[[], Path], password: str) -> Path:
    """
    Write an unencrypted copy of ``src`` and return its path.

    ``make_dst`` is only called once the password has been accepted, so a wrong
    password never leaves a destination behind.
    """
    with pikepdf.open(src, password=password) as pdf:
        pdf.remove_unreferenced_resources()
        dst = make_dst()
        pdf.save(dst)
    return dst


class PdfMerger:
    """
    Accumulates the pages of several PDFs into one new PDF.

    ``add`` raises if a source cannot be read; deciding whether to skip it is the
    caller's policy. Use as a context manager so the merged PDF is closed.
    """

    def __init__(self) -> None:
        self._pdf = pikepdf.new()
        self._version: str = self._pdf.pdf_version

    def __enter__(self) -> PdfMerger:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._pdf.close()

    def add(self, path: Path) -> None:
        with pikepdf.open(str(path)) as pdf:
            self._version = max(self._version, pdf.pdf_version)
            self._pdf.pages.extend(pdf.pages)

    def save(self, dst: Path) -> None:
        self._pdf.remove_unreferenced_resources()
        self._pdf.save(dst, min_version=self._version)
