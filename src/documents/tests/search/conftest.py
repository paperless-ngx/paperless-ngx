from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import tantivy

from documents.search._backend import TantivyBackend
from documents.search._backend import reset_backend
from documents.search._schema import build_schema
from documents.search._tokenizer import register_tokenizers
from paperless_testing.factories import DocumentFactory

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Generator

    from pytest_django.fixtures import Settings

    from documents.models import Document
    from paperless_testing.dirs import PaperlessDirs


@pytest.fixture
def backend(paperless_dirs: PaperlessDirs) -> Generator[TantivyBackend, None, None]:
    b = TantivyBackend(path=paperless_dirs.index_dir)
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


@pytest.fixture(scope="module")
def query_index() -> tantivy.Index:
    """An in-memory, unstemmed index for the parse-only tests.

    These never index a document, so one index per module is shared
    read-only across that module's tests.
    """
    idx = tantivy.Index(build_schema(), path=None)
    register_tokenizers(idx, "")
    return idx


@pytest.fixture
def fuzzy_enabled(settings: Settings) -> None:
    """Enable the fuzzy blend clause. The threshold doubles as a minimum
    score filter, so it is set to 0.0: every hit passes and the test sees
    the clause's matching behaviour, not the filter's."""
    settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = 0.0
