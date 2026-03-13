"""
Parser fixtures that are used across multiple test modules in this package
are defined here.  Format-specific sample-file fixtures are grouped by parser
so it is easy to see which files belong to which test module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from paperless.parsers.remote import RemoteDocumentParser
from paperless.parsers.text import TextDocumentParser

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from pytest_django.fixtures import SettingsWrapper


# ------------------------------------------------------------------
# Text parser sample files
# ------------------------------------------------------------------


@pytest.fixture(scope="session")
def text_samples_dir(samples_dir: Path) -> Path:
    """Absolute path to the text parser sample files directory.

    Returns
    -------
    Path
        ``<samples_dir>/text/``
    """
    return samples_dir / "text"


@pytest.fixture(scope="session")
def sample_txt_file(text_samples_dir: Path) -> Path:
    """Path to a valid UTF-8 plain-text sample file.

    Returns
    -------
    Path
        Absolute path to ``text/test.txt``.
    """
    return text_samples_dir / "test.txt"


@pytest.fixture(scope="session")
def malformed_txt_file(text_samples_dir: Path) -> Path:
    """Path to a text file containing invalid UTF-8 bytes.

    Returns
    -------
    Path
        Absolute path to ``text/decode_error.txt``.
    """
    return text_samples_dir / "decode_error.txt"


# ------------------------------------------------------------------
# Text parser instance
# ------------------------------------------------------------------


@pytest.fixture()
def text_parser() -> Generator[TextDocumentParser, None, None]:
    """Yield a TextDocumentParser and clean up its temporary directory afterwards.

    Yields
    ------
    TextDocumentParser
        A ready-to-use parser instance.
    """
    with TextDocumentParser() as parser:
        yield parser


# ------------------------------------------------------------------
# Remote parser sample files
# ------------------------------------------------------------------


@pytest.fixture(scope="session")
def remote_samples_dir(samples_dir: Path) -> Path:
    """Absolute path to the remote parser sample files directory.

    Returns
    -------
    Path
        ``<samples_dir>/remote/``
    """
    return samples_dir / "remote"


@pytest.fixture(scope="session")
def sample_pdf_file(remote_samples_dir: Path) -> Path:
    """Path to a simple digital PDF sample file.

    Returns
    -------
    Path
        Absolute path to ``remote/simple-digital.pdf``.
    """
    return remote_samples_dir / "simple-digital.pdf"


# ------------------------------------------------------------------
# Remote parser instance
# ------------------------------------------------------------------


@pytest.fixture()
def remote_parser() -> Generator[RemoteDocumentParser, None, None]:
    """Yield a RemoteDocumentParser and clean up its temporary directory afterwards.

    Yields
    ------
    RemoteDocumentParser
        A ready-to-use parser instance.
    """
    with RemoteDocumentParser() as parser:
        yield parser


# ------------------------------------------------------------------
# Remote parser settings helpers
# ------------------------------------------------------------------


@pytest.fixture()
def azure_settings(settings: SettingsWrapper) -> SettingsWrapper:
    """Configure Django settings for a valid Azure AI OCR engine.

    Sets ``REMOTE_OCR_ENGINE``, ``REMOTE_OCR_API_KEY``, and
    ``REMOTE_OCR_ENDPOINT`` to test values.  Settings are restored
    automatically after the test by pytest-django.

    Returns
    -------
    SettingsWrapper
        The modified settings object (for chaining further overrides).
    """
    settings.REMOTE_OCR_ENGINE = "azureai"
    settings.REMOTE_OCR_API_KEY = "test-api-key"
    settings.REMOTE_OCR_ENDPOINT = "https://test.cognitiveservices.azure.com"
    return settings


@pytest.fixture()
def no_engine_settings(settings: SettingsWrapper) -> SettingsWrapper:
    """Configure Django settings with no remote engine configured.

    Returns
    -------
    SettingsWrapper
        The modified settings object.
    """
    settings.REMOTE_OCR_ENGINE = None
    settings.REMOTE_OCR_API_KEY = None
    settings.REMOTE_OCR_ENDPOINT = None
    return settings
