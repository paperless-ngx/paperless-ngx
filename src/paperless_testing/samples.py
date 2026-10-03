"""Test sample files that more than one app's tests need.

A sample used by a single app stays in that app's ``tests/samples`` tree.
Only a file that two or more apps need lives here, exactly once.
"""

import shutil
from pathlib import Path

SHARED_SAMPLES_DIR = (Path(__file__).parent / "sample_files").resolve()

SIMPLE_DIGITAL_PDF = SHARED_SAMPLES_DIR / "simple-digital.pdf"
MULTI_PAGE_DIGITAL_PDF = SHARED_SAMPLES_DIR / "multi-page-digital.pdf"
WITH_FORM_PDF = SHARED_SAMPLES_DIR / "with-form.pdf"
MULTI_PAGE_IMAGES_PDF = SHARED_SAMPLES_DIR / "multi-page-images.pdf"
THUMBNAIL_WEBP = SHARED_SAMPLES_DIR / "thumbnail.webp"

# The fake media tree under documents/tests/samples/documents keeps only the
# files unique to it. The files that duplicate a shared sample are laid back
# down under their historical opaque names (DB rows and exporter manifests
# refer to them) by install_document_samples().
_DOCUMENT_SAMPLES_DIR = (
    Path(__file__).parent.parent / "documents" / "tests" / "samples" / "documents"
).resolve()

_SHARED_AS_MEDIA = (
    ("originals/0000001.pdf", SIMPLE_DIGITAL_PDF),
    ("originals/0000002.pdf", MULTI_PAGE_DIGITAL_PDF),
    ("originals/0000003.pdf", WITH_FORM_PDF),
    ("archive/0000001.pdf", MULTI_PAGE_IMAGES_PDF),
    ("thumbnails/0000001.webp", THUMBNAIL_WEBP),
    ("thumbnails/0000002.webp", THUMBNAIL_WEBP),
    ("thumbnails/0000003.webp", THUMBNAIL_WEBP),
    ("thumbnails/0000004.webp", THUMBNAIL_WEBP),
)


def install_document_samples(dest: Path) -> None:
    """Populate ``dest`` with the full fake media tree.

    Replaces ``shutil.copytree(<samples>/documents, dest)`` in tests.
    """
    shutil.copytree(_DOCUMENT_SAMPLES_DIR, dest, dirs_exist_ok=True)
    for relpath, source in _SHARED_AS_MEDIA:
        target = dest / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
