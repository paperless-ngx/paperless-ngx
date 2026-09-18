import shutil
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

import filelock
import pytest
from pytest_django.fixtures import Settings

from paperless_testing.factories import DocumentFactory

if TYPE_CHECKING:
    from documents.models import Document
    from paperless_testing.dirs import PaperlessDirs


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    """Path to the shared test sample documents."""
    return Path(__file__).parent / "samples" / "documents"


@pytest.fixture()
def sample_doc(
    paperless_dirs: "PaperlessDirs",
    samples_dir: Path,
) -> "Document":
    """Create a document with valid files and matching checksums."""
    with filelock.FileLock(paperless_dirs.media_lock):
        shutil.copy(
            samples_dir / "originals" / "0000001.pdf",
            paperless_dirs.originals_dir / "0000001.pdf",
        )
        shutil.copy(
            samples_dir / "archive" / "0000001.pdf",
            paperless_dirs.archive_dir / "0000001.pdf",
        )
        shutil.copy(
            samples_dir / "thumbnails" / "0000001.webp",
            paperless_dirs.thumbnail_dir / "0000001.webp",
        )

    return DocumentFactory(
        title="test",
        checksum="1093cf6e32adbd16b06969df09215d42c4a3a8938cc18b39455953f08d1ff2ab",
        archive_checksum="706124ecde3c31616992fa979caed17a726b1c9ccdba70e82a4ff796cea97ccf",
        content="test content",
        pk=1,
        filename="0000001.pdf",
        mime_type="application/pdf",
        archive_filename="0000001.pdf",
    )


@pytest.fixture()
def _search_index(
    tmp_path: Path,
    settings: Settings,
) -> Generator[None, None, None]:
    """Create a temp index directory and point INDEX_DIR at it.

    Resets the backend singleton before and after so each test gets a clean
    index rather than reusing a stale singleton from another test.
    """
    from documents.search import reset_backend

    index_dir = tmp_path / "index"
    index_dir.mkdir()
    settings.INDEX_DIR = index_dir
    reset_backend()
    yield
    reset_backend()


@pytest.fixture
def indexed_document(_search_index: None) -> "Document":
    """One searchable document, for tests about what the search endpoint
    returns rather than about what it finds.
    """
    from documents.search import get_backend

    doc = DocumentFactory.create(title="quarterly invoice", content="acme corp")
    get_backend().add_or_update(doc)
    return doc
