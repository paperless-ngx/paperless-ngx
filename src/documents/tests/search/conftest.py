from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.search._backend import TantivyBackend
from documents.search._backend import reset_backend
from documents.tests.factories import DocumentFactory

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Generator
    from pathlib import Path

    from pytest_django.fixtures import Settings

    from documents.models import Document


@pytest.fixture
def index_dir(tmp_path: Path, settings: Settings) -> Path:
    path = tmp_path / "index"
    path.mkdir()
    settings.INDEX_DIR = path
    return path


@pytest.fixture
def backend() -> Generator[TantivyBackend, None, None]:
    b = TantivyBackend()  # path=None → in-memory index
    b.open()
    try:
        yield b
    finally:
        b.close()
        reset_backend()


@pytest.fixture
def long_cjk_run() -> str:
    """A CJK run too long for the content analyzer to keep.

    48 characters, 144 UTF-8 bytes: one token longer than remove_long's
    129-byte limit, so the content side analyzes to nothing and only the
    bigram field can match it.
    """
    return "東京都の公共文書について" * 4


@pytest.fixture
def index_document(backend: TantivyBackend) -> Callable[..., Document]:
    """Build a Document with DocumentFactory and add it to the index.

    The factory supplies a unique checksum, so a test only passes the
    fields its assertion actually depends on.
    """

    def _index(**kwargs: object) -> Document:
        doc = DocumentFactory(**kwargs)
        backend.add_or_update(doc)
        return doc

    return _index


@pytest.fixture
def matched_ids(backend: TantivyBackend) -> Callable[[str], set[int]]:
    """Run a query as no particular user and return the matching pks."""

    def _matched_ids(query: str) -> set[int]:
        return set(backend.search_ids(query, user=None))

    return _matched_ids
