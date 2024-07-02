from collections.abc import Generator
from pathlib import Path

import pytest

from paperless_tika.parsers import TikaDocumentParser


@pytest.fixture()
def tika_parser() -> Generator[TikaDocumentParser, None, None]:
    try:
        parser = TikaDocumentParser(logging_group=None)
        yield parser
    finally:
        parser.cleanup()


@pytest.fixture(scope="session")
def sample_dir() -> Path:
    return (Path(__file__).parent / Path("samples")).resolve()


@pytest.fixture(scope="session")
def sample_odt_file(sample_dir: Path) -> Path:
    return sample_dir / "sample.odt"


@pytest.fixture(scope="session")
def sample_docx_file(sample_dir: Path) -> Path:
    return sample_dir / "sample.docx"


@pytest.fixture(scope="session")
def sample_doc_file(sample_dir: Path) -> Path:
    return sample_dir / "sample.doc"


@pytest.fixture(scope="session")
def sample_broken_odt(sample_dir: Path) -> Path:
    return sample_dir / "multi-part-broken.odt"
