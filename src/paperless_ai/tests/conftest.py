from pathlib import Path

import pytest
from pytest_django.fixtures import SettingsWrapper

from documents.models import Document
from documents.tests.factories import CorrespondentFactory
from documents.tests.factories import DocumentFactory
from documents.tests.factories import DocumentTypeFactory


@pytest.fixture
def temp_llm_index_dir(tmp_path: Path, settings: SettingsWrapper) -> Path:
    settings.LLM_INDEX_DIR = tmp_path
    return tmp_path


@pytest.fixture
def document() -> Document:
    return DocumentFactory.build(
        title="Test Title",
        filename="test_file.pdf",
        correspondent=CorrespondentFactory.build(name="Test Correspondent"),
        document_type=DocumentTypeFactory.build(name="Invoice"),
        archive_serial_number=12345,
        content="This is the document content.",
    )


@pytest.fixture
def similar_documents() -> list[Document]:
    return [
        DocumentFactory.build(
            title="Title 1",
            content="Content of document 1",
            filename="file1.txt",
        ),
        DocumentFactory.build(
            title="",
            content="Content of document 2",
            filename="file2.txt",
        ),
        DocumentFactory.build(title="", content="", filename=None),
    ]
