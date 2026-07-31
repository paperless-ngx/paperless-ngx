import pytest
from pydantic import ValidationError

from paperless_ai.base_model import DocumentClassifierSchema


@pytest.mark.parametrize(
    "omitted_field",
    [
        "tags",
        "correspondents",
        "document_types",
        "storage_paths",
        "dates",
    ],
)
def test_document_classifier_schema_defaults_omitted_list_field(omitted_field):
    data = {
        "title": "Test Title",
        "tags": ["test"],
        "correspondents": ["Test Correspondent"],
        "document_types": ["Test Document Type"],
        "storage_paths": ["Test Storage Path"],
        "dates": ["2026-07-31"],
    }
    del data[omitted_field]

    result = DocumentClassifierSchema(**data)

    assert getattr(result, omitted_field) == []


def test_document_classifier_schema_requires_title():
    with pytest.raises(ValidationError, match="title"):
        DocumentClassifierSchema()
