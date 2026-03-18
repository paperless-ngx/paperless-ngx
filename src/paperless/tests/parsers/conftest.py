"""
Parser fixtures that are used across multiple test modules in this package
are defined here.  Format-specific sample-file fixtures are grouped by parser
so it is easy to see which files belong to which test module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from paperless.parsers.mail import MailDocumentParser
from paperless.parsers.text import TextDocumentParser
from paperless.parsers.tika import TikaDocumentParser

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


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
# Tika parser sample files
# ------------------------------------------------------------------


@pytest.fixture(scope="session")
def tika_samples_dir(samples_dir: Path) -> Path:
    """Absolute path to the Tika parser sample files directory.

    Returns
    -------
    Path
        ``<samples_dir>/tika/``
    """
    return samples_dir / "tika"


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
def mail_samples_dir(samples_dir: Path) -> Path:
    """Absolute path to the mail parser sample files directory.

    Returns
    -------
    Path
        ``<samples_dir>/mail/``
    """
    return samples_dir / "mail"


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
