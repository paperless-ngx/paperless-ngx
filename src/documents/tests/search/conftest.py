from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING

import pytest
import tantivy

from documents.search._backend import TantivyBackend
from documents.search._backend import reset_backend
from documents.search._schema import build_schema
from documents.search._tokenizer import register_tokenizers

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from pytest_django.fixtures import SettingsWrapper


@pytest.fixture
def index_dir(tmp_path: Path, settings: SettingsWrapper) -> Path:
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


@pytest.fixture(scope="module")
def index() -> tantivy.Index:
    """A real Tantivy index for parse-acceptance tests (module scope for speed)."""
    idx = tantivy.Index(build_schema(), path=tempfile.mkdtemp())
    register_tokenizers(idx, "english")
    return idx
