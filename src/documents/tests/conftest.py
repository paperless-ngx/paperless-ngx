import shutil
import zoneinfo
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import filelock
import pytest
from django.contrib.auth import get_user_model
from pytest_django.fixtures import SettingsWrapper
from rest_framework.test import APIClient

from documents.tests.factories import DocumentFactory

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
        checksum="42995833e01aea9b3edee44bbfdd7ce1",
        archive_checksum="62acb0bcbfbcaa62ca6ad3668e4e404b",
        content="test content",
        pk=1,
        filename="0000001.pdf",
        mime_type="application/pdf",
        archive_filename="0000001.pdf",
    )


@pytest.fixture()
def settings_timezone(settings: SettingsWrapper) -> zoneinfo.ZoneInfo:
    return zoneinfo.ZoneInfo(settings.TIME_ZONE)


@pytest.fixture
def rest_api_client():
    """
    The basic DRF ApiClient
    """
    yield APIClient()


@pytest.fixture
def authenticated_rest_api_client(rest_api_client: APIClient):
    """
    The basic DRF ApiClient which has been authenticated
    """
    UserModel = get_user_model()
    user = UserModel.objects.create_user(username="testuser", password="password")
    rest_api_client.force_authenticate(user=user)
    yield rest_api_client
