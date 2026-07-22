"""Tests for OcrConfig archive_file_generation field behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.test import override_settings

from paperless.config import OcrConfig

if TYPE_CHECKING:
    from unittest.mock import MagicMock


@pytest.fixture()
def null_app_config(mocker) -> MagicMock:
    """Mock ApplicationConfiguration with all fields None → falls back to Django settings."""
    return mocker.MagicMock(
        output_type=None,
        pages=None,
        language=None,
        mode=None,
        archive_file_generation=None,
        image_dpi=None,
        unpaper_clean=None,
        deskew=None,
        rotate_pages=None,
        rotate_pages_threshold=None,
        max_image_pixels=None,
        color_conversion_strategy=None,
        user_args=None,
    )


@pytest.fixture()
def make_ocr_config(mocker, null_app_config):
    mocker.patch(
        "paperless.config.BaseConfig._get_config_instance",
        return_value=null_app_config,
    )

    def _make(**django_settings_overrides):
        with override_settings(**django_settings_overrides):
            return OcrConfig()

    return _make


class TestOcrConfigArchiveFileGeneration:
    def test_auto_from_settings(self, make_ocr_config) -> None:
        cfg = make_ocr_config(OCR_MODE="auto", ARCHIVE_FILE_GENERATION="auto")
        assert cfg.archive_file_generation == "auto"

    def test_always_from_settings(self, make_ocr_config) -> None:
        cfg = make_ocr_config(ARCHIVE_FILE_GENERATION="always")
        assert cfg.archive_file_generation == "always"

    def test_never_from_settings(self, make_ocr_config) -> None:
        cfg = make_ocr_config(ARCHIVE_FILE_GENERATION="never")
        assert cfg.archive_file_generation == "never"

    def test_db_value_overrides_setting(self, make_ocr_config, null_app_config) -> None:
        null_app_config.archive_file_generation = "never"
        cfg = make_ocr_config(ARCHIVE_FILE_GENERATION="always")
        assert cfg.archive_file_generation == "never"
