"""Tests for RemoteOCRConfig precedence between app config and Django settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.test import override_settings

from paperless.config import RemoteOCRConfig
from paperless.models import RemoteOCRMode

if TYPE_CHECKING:
    from unittest.mock import MagicMock


@pytest.fixture()
def null_app_config(mocker) -> MagicMock:
    """Mock ApplicationConfiguration with all fields None → falls back to Django settings."""
    return mocker.MagicMock(
        remote_ocr_engine=None,
        remote_ocr_api_key=None,
        remote_ocr_endpoint=None,
        remote_ocr_mode=None,
    )


@pytest.fixture()
def make_remote_ocr_config(mocker):
    def _make(app_config, **django_settings_overrides):
        mocker.patch(
            "paperless.config.BaseConfig._get_config_instance",
            return_value=app_config,
        )
        with override_settings(**django_settings_overrides):
            return RemoteOCRConfig()

    return _make


class TestRemoteOCRConfig:
    def test_falls_back_to_settings(
        self,
        make_remote_ocr_config,
        null_app_config,
    ) -> None:
        cfg = make_remote_ocr_config(
            null_app_config,
            REMOTE_OCR_ENGINE="azureai",
            REMOTE_OCR_API_KEY="env-key",
            REMOTE_OCR_ENDPOINT="https://env.cognitiveservices.azure.com",
            REMOTE_OCR_MODE=RemoteOCRMode.WORKFLOW_ONLY,
        )
        assert cfg.remote_ocr_engine == "azureai"
        assert cfg.remote_ocr_api_key == "env-key"
        assert cfg.remote_ocr_endpoint == "https://env.cognitiveservices.azure.com"
        assert cfg.remote_ocr_mode == RemoteOCRMode.WORKFLOW_ONLY

    def test_app_config_takes_precedence(
        self,
        make_remote_ocr_config,
        mocker,
    ) -> None:
        app_config = mocker.MagicMock(
            remote_ocr_engine="azureai",
            remote_ocr_api_key="db-key",
            remote_ocr_endpoint="https://db.cognitiveservices.azure.com",
            remote_ocr_mode=RemoteOCRMode.WORKFLOW_ONLY,
        )
        cfg = make_remote_ocr_config(
            app_config,
            REMOTE_OCR_ENGINE=None,
            REMOTE_OCR_API_KEY="env-key",
            REMOTE_OCR_ENDPOINT="https://env.cognitiveservices.azure.com",
            REMOTE_OCR_MODE=RemoteOCRMode.ALWAYS,
        )
        assert cfg.remote_ocr_engine == "azureai"
        assert cfg.remote_ocr_api_key == "db-key"
        assert cfg.remote_ocr_endpoint == "https://db.cognitiveservices.azure.com"
        assert cfg.remote_ocr_mode == RemoteOCRMode.WORKFLOW_ONLY

    def test_unset_everywhere(
        self,
        make_remote_ocr_config,
        null_app_config,
    ) -> None:
        cfg = make_remote_ocr_config(
            null_app_config,
            REMOTE_OCR_ENGINE=None,
            REMOTE_OCR_API_KEY=None,
            REMOTE_OCR_ENDPOINT=None,
        )
        assert cfg.remote_ocr_engine is None
        assert cfg.remote_ocr_api_key is None
        assert cfg.remote_ocr_endpoint is None


class TestRemoteOCRByDefault:
    def test_always_mode(self, make_remote_ocr_config, null_app_config) -> None:
        cfg = make_remote_ocr_config(
            null_app_config,
            REMOTE_OCR_MODE=RemoteOCRMode.ALWAYS,
        )

        assert cfg.remote_ocr_by_default is True

    def test_workflow_only_mode(self, make_remote_ocr_config, null_app_config) -> None:
        cfg = make_remote_ocr_config(
            null_app_config,
            REMOTE_OCR_MODE=RemoteOCRMode.WORKFLOW_ONLY,
        )

        assert cfg.remote_ocr_by_default is False
