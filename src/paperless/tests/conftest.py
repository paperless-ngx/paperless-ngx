"""
Fixtures defined here are available to every test module under
src/paperless/tests/ (including sub-packages such as parsers/).

Session-scoped fixtures for the shared samples directory live here so
sub-package conftest files can reference them without duplicating path logic.
Parser-specific fixtures (concrete parser instances, format-specific sample
files) live in paperless/tests/parsers/conftest.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from paperless.parsers.registry import reset_parser_registry

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    """Absolute path to the shared parser sample files directory.

    Sub-package conftest files derive format-specific paths from this root,
    e.g. ``samples_dir / "text" / "test.txt"``.

    Returns
    -------
    Path
        Directory containing all sample documents used by parser tests.
    """
    return (Path(__file__).parent / "samples").resolve()


@pytest.fixture(scope="session")
def tagged_no_text_pdf_file(samples_dir: Path) -> Path:
    """Path to a tagged PDF whose only "text" is pdftotext layout padding.

    Reproduces GH #13387: ``/MarkInfo /Marked true`` is set, but the only
    extractable content is a form-feed byte, not real text. Lives here
    rather than in parsers/conftest.py so both parser tests and
    paperless/tests/test_parser_utils.py can use it.

    Returns
    -------
    Path
        Absolute path to ``tesseract/tagged-but-no-text.pdf``.
    """
    return samples_dir / "tesseract" / "tagged-but-no-text.pdf"


@pytest.fixture(autouse=True)
def clean_registry() -> Generator[None, None, None]:
    """Reset the parser registry before and after every test.

    This prevents registry state from leaking between tests that call
    get_parser_registry() or init_builtin_parsers().
    """
    reset_parser_registry()
    yield
    reset_parser_registry()
