"""Tests for v3 system checks: deprecated environment variable warnings."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from paperless.checks import check_deprecated_convert_env_vars
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


class TestDeprecatedConvertEnvVarWarnings:
    def test_no_deprecated_vars_returns_empty(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - Neither deprecated convert variable is set
        WHEN:
            - The deprecated convert check runs
        THEN:
            - No warnings are returned
        """
        mocker.patch.dict(os.environ, {}, clear=True)
        assert check_deprecated_convert_env_vars(None) == []

    def test_empty_value_returns_empty(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A deprecated convert variable is set to an empty string
        WHEN:
            - The deprecated convert check runs
        THEN:
            - No warnings are returned
        """
        mocker.patch.dict(
            os.environ,
            {"PAPERLESS_CONVERT_TMPDIR": ""},
            clear=True,
        )
        assert check_deprecated_convert_env_vars(None) == []

    @pytest.mark.parametrize(
        ("env_var", "env_value", "expected_id"),
        [
            pytest.param(
                "PAPERLESS_CONVERT_MEMORY_LIMIT",
                "32",
                "paperless.W004",
                id="memory-limit-warns",
            ),
            pytest.param(
                "PAPERLESS_CONVERT_TMPDIR",
                "/var/tmp/paperless",
                "paperless.W005",
                id="tmpdir-warns",
            ),
        ],
    )
    def test_deprecated_var_produces_one_warning(
        self,
        mocker: MockerFixture,
        env_var: str,
        env_value: str,
        expected_id: str,
    ) -> None:
        """
        GIVEN:
            - One deprecated convert variable is set
        WHEN:
            - The deprecated convert check runs
        THEN:
            - Exactly one warning naming that variable is returned
        """
        mocker.patch.dict(os.environ, {env_var: env_value}, clear=True)
        result = check_deprecated_convert_env_vars(None)

        assert len(result) == 1
        assert result[0].id == expected_id
        assert env_var in result[0].msg
        assert "no effect" in result[0].msg

    def test_both_vars_produce_two_warnings(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - Both deprecated convert variables are set
        WHEN:
            - The deprecated convert check runs
        THEN:
            - One warning per variable is returned
        """
        mocker.patch.dict(
            os.environ,
            {
                "PAPERLESS_CONVERT_MEMORY_LIMIT": "32",
                "PAPERLESS_CONVERT_TMPDIR": "/var/tmp/paperless",
            },
            clear=True,
        )
        result = check_deprecated_convert_env_vars(None)

        assert {w.id for w in result} == {"paperless.W004", "paperless.W005"}
