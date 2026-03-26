"""Tests for v3 system checks: deprecated v2 OCR env var warnings."""

from __future__ import annotations

import pytest
from django.core import checks as django_checks


@pytest.mark.django_db
class TestDeprecatedV2OcrEnvVarWarnings:
    def test_old_skip_archive_file_env_warns(self, monkeypatch) -> None:
        monkeypatch.setenv("PAPERLESS_OCR_SKIP_ARCHIVE_FILE", "always")
        all_checks = django_checks.run_checks()
        warns = [
            e
            for e in all_checks
            if "PAPERLESS_OCR_SKIP_ARCHIVE_FILE" in str(getattr(e, "msg", ""))
        ]
        assert warns

    def test_old_skip_mode_env_warns(self, monkeypatch) -> None:
        monkeypatch.setenv("PAPERLESS_OCR_MODE", "skip")
        all_checks = django_checks.run_checks()
        warns = [
            e
            for e in all_checks
            if "skip" in str(getattr(e, "msg", "")).lower()
            and "OCR_MODE" in str(getattr(e, "msg", ""))
        ]
        assert warns

    def test_old_skip_noarchive_mode_env_warns(self, monkeypatch) -> None:
        monkeypatch.setenv("PAPERLESS_OCR_MODE", "skip_noarchive")
        all_checks = django_checks.run_checks()
        warns = [
            e for e in all_checks if "skip_noarchive" in str(getattr(e, "msg", ""))
        ]
        assert warns

    def test_no_deprecated_vars_no_warning(self, monkeypatch) -> None:
        monkeypatch.delenv("PAPERLESS_OCR_SKIP_ARCHIVE_FILE", raising=False)
        monkeypatch.setenv("PAPERLESS_OCR_MODE", "auto")
        all_checks = django_checks.run_checks()
        deprecated_warns = [
            e
            for e in all_checks
            if "PAPERLESS_OCR_SKIP_ARCHIVE_FILE" in str(getattr(e, "msg", ""))
            or (
                "skip" in str(getattr(e, "msg", "")).lower()
                and "OCR_MODE" in str(getattr(e, "msg", ""))
            )
        ]
        assert not deprecated_warns
