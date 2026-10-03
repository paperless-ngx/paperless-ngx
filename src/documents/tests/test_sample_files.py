import hashlib
from pathlib import Path

from paperless_testing.samples import SIMPLE_DIGITAL_PDF
from paperless_testing.samples import install_document_samples

EXPECTED_MEDIA_FILES = [
    "originals/0000001.pdf",
    "originals/0000002.pdf",
    "originals/0000003.pdf",
    "originals/0000004.pdf",
    "originals/0000005.pdf",
    "originals/0000006.pdf",
    "archive/0000001.pdf",
    "thumbnails/0000001.webp",
    "thumbnails/0000002.webp",
    "thumbnails/0000003.webp",
    "thumbnails/0000004.webp",
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_install_recreates_every_historical_opaque_name(tmp_path: Path) -> None:
    install_document_samples(tmp_path)
    for relpath in EXPECTED_MEDIA_FILES:
        assert (tmp_path / relpath).is_file(), relpath


def test_install_uses_the_shared_bytes(tmp_path: Path) -> None:
    install_document_samples(tmp_path)
    assert _sha(tmp_path / "originals" / "0000001.pdf") == _sha(SIMPLE_DIGITAL_PDF)
