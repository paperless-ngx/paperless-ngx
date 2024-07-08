import os
from collections.abc import Generator
from pathlib import Path

import pytest

from paperless_mail.mail import MailAccountHandler
from paperless_mail.models import MailAccount
from paperless_mail.parsers import MailDocumentParser


@pytest.fixture(scope="session")
def sample_dir() -> Path:
    return (Path(__file__).parent / Path("samples")).resolve()


@pytest.fixture(scope="session")
def broken_email_file(sample_dir: Path) -> Path:
    return sample_dir / "broken.eml"


@pytest.fixture(scope="session")
def simple_txt_email_file(sample_dir: Path) -> Path:
    return sample_dir / "simple_text.eml"


@pytest.fixture(scope="session")
def simple_txt_email_pdf_file(sample_dir: Path) -> Path:
    return sample_dir / "simple_text.eml.pdf"


@pytest.fixture(scope="session")
def simple_txt_email_thumbnail_file(sample_dir: Path) -> Path:
    return sample_dir / "simple_text.eml.pdf.webp"


@pytest.fixture(scope="session")
def html_email_file(sample_dir: Path) -> Path:
    return sample_dir / "html.eml"


@pytest.fixture(scope="session")
def html_email_pdf_file(sample_dir: Path) -> Path:
    return sample_dir / "html.eml.pdf"


@pytest.fixture(scope="session")
def html_email_thumbnail_file(sample_dir: Path) -> Path:
    return sample_dir / "html.eml.pdf.webp"


@pytest.fixture(scope="session")
def html_email_html_file(sample_dir: Path) -> Path:
    return sample_dir / "html.eml.html"


@pytest.fixture(scope="session")
def merged_pdf_first(sample_dir: Path) -> Path:
    return sample_dir / "first.pdf"


@pytest.fixture(scope="session")
def merged_pdf_second(sample_dir: Path) -> Path:
    return sample_dir / "second.pdf"


@pytest.fixture()
def mail_parser() -> MailDocumentParser:
    return MailDocumentParser(logging_group=None)


@pytest.fixture()
def live_mail_account() -> Generator[MailAccount, None, None]:
    try:
        account = MailAccount.objects.create(
            name="test",
            imap_server=os.environ["PAPERLESS_MAIL_TEST_HOST"],
            username=os.environ["PAPERLESS_MAIL_TEST_USER"],
            password=os.environ["PAPERLESS_MAIL_TEST_PASSWD"],
            imap_port=993,
        )
        yield account
    finally:
        account.delete()


@pytest.fixture()
def mail_account_handler() -> MailAccountHandler:
    return MailAccountHandler()
