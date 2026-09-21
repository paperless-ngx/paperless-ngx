"""
Parser fixtures that are used across multiple test modules in this package
are defined here.  Format-specific sample-file fixtures are grouped by parser
so it is easy to see which files belong to which test module.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from django.test import override_settings

from paperless.parsers.mail import MailDocumentParser
from paperless.parsers.remote import RemoteDocumentParser
from paperless.parsers.tesseract import RasterisedDocumentParser
from paperless.parsers.text import TextDocumentParser
from paperless.parsers.tika import TikaDocumentParser

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Generator
    from pathlib import Path
    from unittest.mock import MagicMock

    from pytest_django.fixtures import Settings
    from pytest_mock import MockerFixture

    #: Type for the ``make_tesseract_parser`` fixture factory.
    MakeTesseractParser = Callable[..., Generator[RasterisedDocumentParser, None, None]]


# ------------------------------------------------------------------
# Text parser sample files
# ------------------------------------------------------------------


@pytest.fixture(scope="session")
def text_samples_dir(parser_samples_dir: Path) -> Path:
    """Absolute path to the text parser sample files directory.

    Returns
    -------
    Path
        ``<parser_samples_dir>/text/``
    """
    return parser_samples_dir / "text"


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
def empty_remote_ocr_app_config(mocker: MockerFixture) -> MagicMock:
    # empty app config without accessing db
    app_config = mocker.MagicMock(
        remote_ocr_engine=None,
        remote_ocr_api_key=None,
        remote_ocr_endpoint=None,
        remote_ocr_mode=None,
    )
    mocker.patch(
        "paperless.config.BaseConfig._get_config_instance",
        return_value=app_config,
    )
    return app_config


@pytest.fixture()
def azure_settings(
    settings: Settings,
    empty_remote_ocr_app_config: MagicMock,
) -> Settings:
    """Configure Django settings for a valid Azure AI OCR engine.

    Sets ``REMOTE_OCR_ENGINE``, ``REMOTE_OCR_API_KEY``, and
    ``REMOTE_OCR_ENDPOINT`` to test values.  Settings are restored
    automatically after the test by pytest-django.

    Returns
    -------
    Settings
        The modified settings object (for chaining further overrides).
    """
    settings.REMOTE_OCR_ENGINE = "azureai"
    settings.REMOTE_OCR_API_KEY = "test-api-key"
    settings.REMOTE_OCR_ENDPOINT = "https://test.cognitiveservices.azure.com"
    return settings


@pytest.fixture()
def no_engine_settings(
    settings: Settings,
    empty_remote_ocr_app_config: MagicMock,
) -> Settings:
    """Configure Django settings with no remote engine configured.

    Returns
    -------
    Settings
        The modified settings object.
    """
    settings.REMOTE_OCR_ENGINE = None
    settings.REMOTE_OCR_API_KEY = None
    settings.REMOTE_OCR_ENDPOINT = None
    return settings


# ------------------------------------------------------------------
# Tika parser sample files
# ------------------------------------------------------------------


@pytest.fixture(scope="session")
def tika_samples_dir(parser_samples_dir: Path) -> Path:
    """Absolute path to the Tika parser sample files directory.

    Returns
    -------
    Path
        ``<parser_samples_dir>/tika/``
    """
    return parser_samples_dir / "tika"


@pytest.fixture(scope="session")
def sample_odt_file(tika_samples_dir: Path) -> Path:
    """Path to a sample ODT file.

    Returns
    -------
    Path
        Absolute path to ``tika/sample.odt``.
    """
    return tika_samples_dir / "sample.odt"


@pytest.fixture(scope="session")
def sample_docx_file(tika_samples_dir: Path) -> Path:
    """Path to a sample DOCX file.

    Returns
    -------
    Path
        Absolute path to ``tika/sample.docx``.
    """
    return tika_samples_dir / "sample.docx"


@pytest.fixture(scope="session")
def sample_doc_file(tika_samples_dir: Path) -> Path:
    """Path to a sample DOC file.

    Returns
    -------
    Path
        Absolute path to ``tika/sample.doc``.
    """
    return tika_samples_dir / "sample.doc"


@pytest.fixture(scope="session")
def sample_broken_odt(tika_samples_dir: Path) -> Path:
    """Path to a broken ODT file that triggers the multi-part fallback.

    Returns
    -------
    Path
        Absolute path to ``tika/multi-part-broken.odt``.
    """
    return tika_samples_dir / "multi-part-broken.odt"


# ------------------------------------------------------------------
# Tika parser instance
# ------------------------------------------------------------------


@pytest.fixture()
def tika_parser() -> Generator[TikaDocumentParser, None, None]:
    """Yield a TikaDocumentParser and clean up its temporary directory afterwards.

    Yields
    ------
    TikaDocumentParser
        A ready-to-use parser instance.
    """
    with TikaDocumentParser() as parser:
        yield parser


# ------------------------------------------------------------------
# Mail parser sample files
# ------------------------------------------------------------------


@pytest.fixture(scope="session")
def mail_samples_dir(parser_samples_dir: Path) -> Path:
    """Absolute path to the mail parser sample files directory.

    Returns
    -------
    Path
        ``<parser_samples_dir>/mail/``
    """
    return parser_samples_dir / "mail"


@pytest.fixture(scope="session")
def broken_email_file(mail_samples_dir: Path) -> Path:
    """Path to a broken/malformed EML sample file.

    Returns
    -------
    Path
        Absolute path to ``mail/broken.eml``.
    """
    return mail_samples_dir / "broken.eml"


@pytest.fixture(scope="session")
def simple_txt_email_file(mail_samples_dir: Path) -> Path:
    """Path to a plain-text email sample file.

    Returns
    -------
    Path
        Absolute path to ``mail/simple_text.eml``.
    """
    return mail_samples_dir / "simple_text.eml"


@pytest.fixture(scope="session")
def simple_txt_email_pdf_file(mail_samples_dir: Path) -> Path:
    """Path to the expected PDF rendition of the plain-text email.

    Returns
    -------
    Path
        Absolute path to ``mail/simple_text.eml.pdf``.
    """
    return mail_samples_dir / "simple_text.eml.pdf"


@pytest.fixture(scope="session")
def simple_txt_email_thumbnail_file(mail_samples_dir: Path) -> Path:
    """Path to the expected thumbnail for the plain-text email.

    Returns
    -------
    Path
        Absolute path to ``mail/simple_text.eml.pdf.webp``.
    """
    return mail_samples_dir / "simple_text.eml.pdf.webp"


@pytest.fixture(scope="session")
def html_email_file(mail_samples_dir: Path) -> Path:
    """Path to an HTML email sample file.

    Returns
    -------
    Path
        Absolute path to ``mail/html.eml``.
    """
    return mail_samples_dir / "html.eml"


@pytest.fixture(scope="session")
def html_email_pdf_file(mail_samples_dir: Path) -> Path:
    """Path to the expected PDF rendition of the HTML email.

    Returns
    -------
    Path
        Absolute path to ``mail/html.eml.pdf``.
    """
    return mail_samples_dir / "html.eml.pdf"


@pytest.fixture(scope="session")
def html_email_thumbnail_file(mail_samples_dir: Path) -> Path:
    """Path to the expected thumbnail for the HTML email.

    Returns
    -------
    Path
        Absolute path to ``mail/html.eml.pdf.webp``.
    """
    return mail_samples_dir / "html.eml.pdf.webp"


@pytest.fixture(scope="session")
def html_email_html_file(mail_samples_dir: Path) -> Path:
    """Path to the HTML body of the HTML email sample.

    Returns
    -------
    Path
        Absolute path to ``mail/html.eml.html``.
    """
    return mail_samples_dir / "html.eml.html"


@pytest.fixture(scope="session")
def merged_pdf_first(mail_samples_dir: Path) -> Path:
    """Path to the first PDF used in PDF-merge tests.

    Returns
    -------
    Path
        Absolute path to ``mail/first.pdf``.
    """
    return mail_samples_dir / "first.pdf"


@pytest.fixture(scope="session")
def merged_pdf_second(mail_samples_dir: Path) -> Path:
    """Path to the second PDF used in PDF-merge tests.

    Returns
    -------
    Path
        Absolute path to ``mail/second.pdf``.
    """
    return mail_samples_dir / "second.pdf"


# ------------------------------------------------------------------
# Mail parser instance
# ------------------------------------------------------------------


@pytest.fixture()
def mail_parser() -> Generator[MailDocumentParser, None, None]:
    """Yield a MailDocumentParser and clean up its temporary directory afterwards.

    Yields
    ------
    MailDocumentParser
        A ready-to-use parser instance.
    """
    with MailDocumentParser() as parser:
        yield parser


@pytest.fixture(scope="session")
def nginx_base_url() -> Generator[str, None, None]:
    """
    The base URL for the nginx HTTP server we expect to be alive
    """
    yield "http://localhost:8080"


# ------------------------------------------------------------------
# Tesseract parser sample files
# ------------------------------------------------------------------


@pytest.fixture(scope="session")
def tesseract_samples_dir(parser_samples_dir: Path) -> Path:
    """Absolute path to the tesseract parser sample files directory.

    Returns
    -------
    Path
        ``<parser_samples_dir>/tesseract/``
    """
    return parser_samples_dir / "tesseract"


@pytest.fixture(scope="session")
def multi_page_images_pdf_file(tesseract_samples_dir: Path) -> Path:
    """Path to a multi-page PDF with images.

    Returns
    -------
    Path
        Absolute path to ``tesseract/multi-page-images.pdf``.
    """
    return tesseract_samples_dir / "multi-page-images.pdf"


@pytest.fixture(scope="session")
def simple_digital_pdf_file(tesseract_samples_dir: Path) -> Path:
    """Path to a simple digital PDF sample file.

    Returns
    -------
    Path
        Absolute path to ``tesseract/simple-digital.pdf``.
    """
    return tesseract_samples_dir / "simple-digital.pdf"


@pytest.fixture(scope="session")
def simple_no_dpi_png_file(tesseract_samples_dir: Path) -> Path:
    """Path to a simple PNG without DPI information.

    Returns
    -------
    Path
        Absolute path to ``tesseract/simple-no-dpi.png``.
    """
    return tesseract_samples_dir / "simple-no-dpi.png"


@pytest.fixture(scope="session")
def simple_png_file(tesseract_samples_dir: Path) -> Path:
    """Path to a simple PNG sample file.

    Returns
    -------
    Path
        Absolute path to ``tesseract/simple.png``.
    """
    return tesseract_samples_dir / "simple.png"


# ------------------------------------------------------------------
# Tesseract parser instance and settings helpers
# ------------------------------------------------------------------


@pytest.fixture()
def null_app_config(mocker: MockerFixture) -> MagicMock:
    """Return a MagicMock with all OcrConfig fields set to None.

    This allows the parser to fall back to Django settings instead of
    hitting the database.

    Returns
    -------
    MagicMock
        Mock config with all fields as None
    """
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
def tesseract_parser(
    mocker: MockerFixture,
    null_app_config: MagicMock,
) -> Generator[RasterisedDocumentParser, None, None]:
    """Yield a RasterisedDocumentParser and clean up its temporary directory afterwards.

    Patches the config system to avoid database access.

    Yields
    ------
    RasterisedDocumentParser
        A ready-to-use parser instance.
    """
    mocker.patch(
        "paperless.config.BaseConfig._get_config_instance",
        return_value=null_app_config,
    )
    with RasterisedDocumentParser() as parser:
        yield parser


@pytest.fixture()
def make_tesseract_parser(
    mocker: MockerFixture,
    null_app_config: MagicMock,
) -> MakeTesseractParser:
    """Return a factory for creating RasterisedDocumentParser with Django settings overrides.

    This fixture is useful for tests that need to create parsers with different
    settings configurations.

    Returns
    -------
    Callable[..., contextmanager[RasterisedDocumentParser]]
        A context manager factory that accepts Django settings overrides
    """
    mocker.patch(
        "paperless.config.BaseConfig._get_config_instance",
        return_value=null_app_config,
    )

    @contextmanager
    def _make_parser(**django_settings_overrides):
        with override_settings(**django_settings_overrides):
            with RasterisedDocumentParser() as parser:
                yield parser

    return _make_parser
