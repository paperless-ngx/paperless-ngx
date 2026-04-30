import shutil
import zoneinfo
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import filelock
import pytest
from django.contrib.auth import get_user_model
from pytest_django.fixtures import SettingsWrapper
from rest_framework.test import APIClient

from documents.tests.factories import DocumentFactory
from documents.tests.factories import UserFactory

UserModelT = get_user_model()

if TYPE_CHECKING:
    from documents.models import Document


@dataclass(frozen=True, slots=True)
class PaperlessDirs:
    """Standard Paperless-ngx directory layout for tests."""

    media: Path
    originals: Path
    archive: Path
    thumbnails: Path


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    """Path to the shared test sample documents."""
    return Path(__file__).parent / "samples" / "documents"


@pytest.fixture()
def paperless_dirs(tmp_path: Path) -> PaperlessDirs:
    """Create and return the directory structure for testing."""
    media = tmp_path / "media"
    dirs = PaperlessDirs(
        media=media,
        originals=media / "documents" / "originals",
        archive=media / "documents" / "archive",
        thumbnails=media / "documents" / "thumbnails",
    )
    for d in (dirs.originals, dirs.archive, dirs.thumbnails):
        d.mkdir(parents=True)
    return dirs


@pytest.fixture()
def _media_settings(paperless_dirs: PaperlessDirs, settings) -> None:
    """Configure Django settings to point at temp directories."""
    settings.MEDIA_ROOT = paperless_dirs.media
    settings.ORIGINALS_DIR = paperless_dirs.originals
    settings.ARCHIVE_DIR = paperless_dirs.archive
    settings.THUMBNAIL_DIR = paperless_dirs.thumbnails
    settings.MEDIA_LOCK = paperless_dirs.media / "media.lock"
    settings.IGNORABLE_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
    settings.APP_LOGO = ""


@pytest.fixture()
def sample_doc(
    paperless_dirs: PaperlessDirs,
    _media_settings: None,
    samples_dir: Path,
) -> "Document":
    """Create a document with valid files and matching checksums."""
    with filelock.FileLock(paperless_dirs.media / "media.lock"):
        shutil.copy(
            samples_dir / "originals" / "0000001.pdf",
            paperless_dirs.originals / "0000001.pdf",
        )
        shutil.copy(
            samples_dir / "archive" / "0000001.pdf",
            paperless_dirs.archive / "0000001.pdf",
        )
        shutil.copy(
            samples_dir / "thumbnails" / "0000001.webp",
            paperless_dirs.thumbnails / "0000001.webp",
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
    settings: SettingsWrapper,
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


@pytest.fixture()
def settings_timezone(settings: SettingsWrapper) -> zoneinfo.ZoneInfo:
    return zoneinfo.ZoneInfo(settings.TIME_ZONE)


@pytest.fixture
def rest_api_client():
    """
    The basic DRF ApiClient
    """
    yield APIClient()


@pytest.fixture()
def regular_user(db) -> UserModelT:
    """Unprivileged authenticated user for permission boundary tests."""
    return UserFactory.create()


@pytest.fixture()
def admin_client(rest_api_client: APIClient, admin_user: UserModelT) -> APIClient:
    """Admin client pre-authenticated and sending the v10 Accept header."""
    rest_api_client.force_authenticate(user=admin_user)
    rest_api_client.credentials(HTTP_ACCEPT="application/json; version=10")
    return rest_api_client


@pytest.fixture()
def v9_client(rest_api_client: APIClient, admin_user: UserModelT) -> APIClient:
    """Admin client pre-authenticated and sending the v9 Accept header."""
    rest_api_client.force_authenticate(user=admin_user)
    rest_api_client.credentials(HTTP_ACCEPT="application/json; version=9")
    return rest_api_client


@pytest.fixture()
def user_client(rest_api_client: APIClient, regular_user: UserModelT) -> APIClient:
    """Regular-user client pre-authenticated and sending the v10 Accept header."""
    rest_api_client.force_authenticate(user=regular_user)
    rest_api_client.credentials(HTTP_ACCEPT="application/json; version=10")
    return rest_api_client


@pytest.fixture(scope="session", autouse=True)
def faker_session_locale():
    """Set Faker locale for reproducibility."""
    return "en_US"


@pytest.fixture(scope="session", autouse=True)
def faker_seed():
    return 12345
