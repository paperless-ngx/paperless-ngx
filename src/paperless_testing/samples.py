"""Test sample files that more than one app's tests need.

A sample used by a single app stays in that app's ``tests/samples`` tree.
Only a file that two or more apps need lives here, exactly once.
"""

from pathlib import Path

SHARED_SAMPLES_DIR = (Path(__file__).parent / "sample_files").resolve()

SIMPLE_DIGITAL_PDF = SHARED_SAMPLES_DIR / "simple-digital.pdf"
MULTI_PAGE_DIGITAL_PDF = SHARED_SAMPLES_DIR / "multi-page-digital.pdf"
WITH_FORM_PDF = SHARED_SAMPLES_DIR / "with-form.pdf"
MULTI_PAGE_IMAGES_PDF = SHARED_SAMPLES_DIR / "multi-page-images.pdf"
