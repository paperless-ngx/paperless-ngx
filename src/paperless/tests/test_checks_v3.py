"""Tests for v3 system checks: deprecated v2 OCR env var warnings."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from paperless.checks import check_deprecated_v2_ocr_env_vars

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class TestDeprecatedV2OcrEnvVarWarnings:
    def test_no_deprecated_vars_returns_empty(self, mocker: MockerFixture) -> None:
        """No warnings when neither deprecated variable is set."""
        mocker.patch.dict(os.environ, {"PAPERLESS_OCR_MODE": "auto"}, clear=True)
        result = check_deprecated_v2_ocr_env_vars(None)
        assert result == []

    @pytest.mark.parametrize(
        ("env_var", "env_value", "expected_id", "expected_fragment"),
        [
            pytest.param(
                "PAPERLESS_OCR_SKIP_ARCHIVE_FILE",
                "always",
                "paperless.W002",
                "PAPERLESS_OCR_SKIP_ARCHIVE_FILE",
                id="skip-archive-file-warns",
            ),
            pytest.param(
                "PAPERLESS_OCR_MODE",
                "skip",
                "paperless.W003",
                "skip",
                id="ocr-mode-skip-warns",
            ),
            pytest.param(
                "PAPERLESS_OCR_MODE",
                "skip_noarchive",
                "paperless.W003",
                "skip_noarchive",
                id="ocr-mode-skip-noarchive-warns",
            ),
        ],
    )
    def test_deprecated_var_produces_one_warning(
        self,
        mocker: MockerFixture,
        env_var: str,
        env_value: str,
        expected_id: str,
        expected_fragment: str,
    ) -> None:
        """Each deprecated setting in isolation produces exactly one warning."""
        mocker.patch.dict(os.environ, {env_var: env_value}, clear=True)
        result = check_deprecated_v2_ocr_env_vars(None)

        assert len(result) == 1
        warning = result[0]
        assert warning.id == expected_id
        assert expected_fragment in warning.msg
