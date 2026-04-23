from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from documents.search._schema import SCHEMA_VERSION
from documents.search._schema import needs_rebuild

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import SettingsWrapper

pytestmark = pytest.mark.search


class TestNeedsRebuild:
    """needs_rebuild covers all sentinel-file states that require a full reindex."""

    def test_returns_true_when_settings_file_missing(self, index_dir: Path) -> None:
        assert needs_rebuild(index_dir) is True

    def test_returns_false_when_version_and_language_match(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEARCH_LANGUAGE = "en"
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": SCHEMA_VERSION, "language": "en"}),
        )
        assert needs_rebuild(index_dir) is False

    def test_returns_true_on_schema_version_mismatch(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEARCH_LANGUAGE = None
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": SCHEMA_VERSION - 1, "language": None}),
        )
        assert needs_rebuild(index_dir) is True

    def test_returns_true_when_version_is_not_an_integer(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEARCH_LANGUAGE = None
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": "not-a-number", "language": None}),
        )
        assert needs_rebuild(index_dir) is True

    def test_returns_true_when_language_key_missing(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEARCH_LANGUAGE = "en"
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": SCHEMA_VERSION}),
        )
        assert needs_rebuild(index_dir) is True

    def test_returns_true_when_language_differs(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEARCH_LANGUAGE = "de"
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": SCHEMA_VERSION, "language": "en"}),
        )
        assert needs_rebuild(index_dir) is True
