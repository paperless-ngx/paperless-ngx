from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.search._backend import TantivyBackend
from documents.search._backend import reset_backend

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
def backend(index_dir: Path) -> Generator[TantivyBackend, None, None]:
    b = TantivyBackend()
    with b:
        yield b
    reset_backend()
