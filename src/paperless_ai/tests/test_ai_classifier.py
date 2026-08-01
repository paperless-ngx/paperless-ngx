import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.test import override_settings

from documents.models import Document
from paperless.config import AIConfig
from paperless_ai.ai_classifier import _extract_document_metadata
from paperless_ai.ai_classifier import _get_system_metadata
from paperless_ai.ai_classifier import build_localization_prompt
from paperless_ai.ai_classifier import build_prompt_with_rag
from paperless_ai.ai_classifier import build_prompt_without_rag
from paperless_ai.ai_classifier import get_ai_document_classification
from paperless_ai.ai_classifier import get_context_for_document
from paperless_ai.ai_classifier import get_language_name


@pytest.fixture
def mock_document():
    doc = MagicMock(spec=Document)
    doc.title = "Test Title"
    doc.filename = "test_file.pdf"
    doc.created = "2023-01-01"
    doc.added = "2023-01-02"
    doc.modified = "2023-01-03"

    tag1 = MagicMock()
    tag1.name = "Tag1"
    tag2 = MagicMock()
    tag2.name = "Tag2"
    doc.tags.all = MagicMock(return_value=[tag1, tag2])
    doc.tags.exists = MagicMock(return_value=True)

    doc.document_type = MagicMock()
    doc.document_type.name = "Invoice"
    doc.correspondent = MagicMock()
    doc.correspondent.name = "Test Correspondent"
    doc.storage_path = MagicMock()
    doc.storage_path.name = "/archive/invoices"
    doc.archive_serial_number = "12345"
    doc.content = "This is the document content."

    cf1 = MagicMock(__str__=lambda x: "Value1")
    cf1.field = MagicMock()
    cf1.field.name = "Field1"
    cf1.value = "Value1"
    cf2 = MagicMock(__str__=lambda x: "Value2")
    cf2.field = MagicMock()
    cf2.field.name = "Field2"
    cf2.value = "Value2"
    doc.custom_fields.all = MagicMock(return_value=[cf1, cf2])

    return doc


@pytest.fixture
def mock_similar_documents():
    doc1 = MagicMock()
    doc1.content = "Content of document 1"
    doc1.title = "Title 1"
    doc1.filename = "file1.txt"

    doc2 = MagicMock()
    doc2.content = "Content of document 2"
    doc2.title = None
    doc2.filename = "file2.txt"

    doc3 = MagicMock()
    doc3.content = None
    doc3.title = None
    doc3.filename = None

    return [doc1, doc2, doc3]


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
@override_settings(
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_get_ai_document_classification_success(mock_run_llm_query, mock_document):
    mock_run_llm_query.side_effect = [
        {
            "title": "Test Title",
            "tags": ["test", "document"],
            "correspondents": ["John Doe"],
            "document_types": ["report"],
            "storage_paths": ["Reports"],
            "dates": ["2023-01-01"],
        },
        {
            "title": "Testtitel",
            "tags": ["Test", "Document"],
            "correspondents": ["Jane Doe"],
            "document_types": ["Bericht"],
            "storage_paths": ["Berichte"],
            "dates": ["2024-01-01"],
        },
    ]

    result = get_ai_document_classification(mock_document, output_language="de-de")

    assert result["title"] == "Testtitel"
    assert result["tags"] == ["Test", "Document"]
    assert result["correspondents"] == ["John Doe"]
    assert result["document_types"] == ["Bericht"]
    assert result["storage_paths"] == ["Berichte"]
    assert result["dates"] == ["2023-01-01"]
    classification_prompt = mock_run_llm_query.call_args_list[0].args[0]
    localization_prompt = mock_run_llm_query.call_args_list[1].args[0]
    assert "Write suggested titles" not in classification_prompt
    assert "Rewrite only these generated fields in German" in localization_prompt
    assert "Do not translate correspondents, tags or dates" in localization_prompt


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
@override_settings(
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_get_ai_document_classification_keeps_originals_when_localization_empty(
    mock_run_llm_query,
    mock_document,
):
    mock_run_llm_query.side_effect = [
        {
            "title": "Test Title",
            "tags": ["test", "document"],
            "correspondents": ["John Doe"],
            "document_types": ["report"],
            "storage_paths": ["Reports"],
            "dates": ["2023-01-01"],
        },
        {
            "title": "",
            "tags": [],
            "correspondents": [],
            "document_types": [],
            "storage_paths": [],
            "dates": [],
        },
    ]

    result = get_ai_document_classification(mock_document, output_language="de-de")

    assert result["title"] == "Test Title"
    assert result["tags"] == ["test", "document"]
    assert result["correspondents"] == ["John Doe"]
    assert result["document_types"] == ["report"]
    assert result["storage_paths"] == ["Reports"]
    assert result["dates"] == ["2023-01-01"]


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
def test_get_ai_document_classification_failure(mock_run_llm_query, mock_document):
    mock_run_llm_query.side_effect = Exception("LLM query failed")

    # assert raises an exception
    with pytest.raises(Exception):
        get_ai_document_classification(mock_document)


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
@patch("paperless_ai.ai_classifier.build_prompt_with_rag")
@override_settings(
    LLM_EMBEDDING_BACKEND="huggingface",
    LLM_EMBEDDING_MODEL="some_model",
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_use_rag_if_configured(
    mock_build_prompt_with_rag,
    mock_run_llm_query,
    mock_document,
):
    mock_build_prompt_with_rag.return_value = "Prompt with RAG"
    mock_run_llm_query.return_value.text = json.dumps({})
    get_ai_document_classification(mock_document)
    mock_build_prompt_with_rag.assert_called_once()


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
@patch("paperless_ai.ai_classifier.build_prompt_without_rag")
@patch("paperless.config.AIConfig")
@override_settings(
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_use_without_rag_if_not_configured(
    mock_ai_config,
    mock_build_prompt_without_rag,
    mock_run_llm_query,
    mock_document,
):
    mock_ai_config.llm_embedding_backend = None
    mock_build_prompt_without_rag.return_value = "Prompt without RAG"
    mock_run_llm_query.return_value.text = json.dumps({})
    get_ai_document_classification(mock_document)
    mock_build_prompt_without_rag.assert_called_once()


@pytest.mark.django_db
@override_settings(
    LLM_EMBEDDING_BACKEND="huggingface",
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_prompt_with_without_rag(mock_document):
    with patch(
        "paperless_ai.ai_classifier.get_context_for_document",
        return_value="Context from similar documents",
    ), patch("paperless_ai.ai_classifier._get_system_metadata", return_value={
        "tags": ["Tag1"],
        "document_types": ["Invoice"],
        "correspondents": ["Test"],
        "storage_paths": ["/path"],
    }):
        config = AIConfig()
        prompt = build_prompt_without_rag(mock_document, config)
        assert "Additional context from similar documents" not in prompt
        assert "for generated" not in prompt

        prompt = build_prompt_with_rag(mock_document, config)
        assert "Additional context from similar documents" in prompt

        prompt = build_localization_prompt(
            {
                "title": "Test Title",
                "tags": ["test", "document"],
                "correspondents": ["John Doe"],
                "document_types": ["report"],
                "storage_paths": ["Reports"],
                "dates": ["2023-01-01"],
            },
            output_language="de-de",
        )
        assert "Rewrite only these generated fields in German" in prompt


def test_get_language_name_falls_back_to_language_code():
    assert get_language_name("zz-zz") == "zz-zz"


def test_build_localization_prompt_preserves_unicode_characters():
    prompt = build_localization_prompt(
        {
            "title": "Gebührenbescheid",
            "tags": [],
            "correspondents": [],
            "document_types": [],
            "storage_paths": [],
            "dates": [],
        },
        output_language="de-de",
    )

    assert "Gebührenbescheid" in prompt
    assert "\\u00fc" not in prompt


@patch("paperless_ai.ai_classifier.query_similar_documents")
def test_get_context_for_document(
    mock_query_similar_documents,
    mock_document,
    mock_similar_documents,
):
    mock_query_similar_documents.return_value = mock_similar_documents

    result = get_context_for_document(mock_document, max_docs=2)

    expected_result = (
        "TITLE: Title 1\nContent of document 1\n\n"
        "TITLE: file2.txt\nContent of document 2"
    )
    assert result == expected_result
    mock_query_similar_documents.assert_called_once()


def test_get_context_for_document_no_similar_docs(mock_document):
    with patch("paperless_ai.ai_classifier.query_similar_documents", return_value=[]):
        result = get_context_for_document(mock_document)
        assert result == ""


def test_extract_document_metadata(mock_document):
    result = _extract_document_metadata(mock_document)

    assert result["tags"] == ["Tag1", "Tag2"]
    assert result["document_type"] == "Invoice"
    assert result["correspondent"] == "Test Correspondent"
    assert result["storage_path"] == "/archive/invoices"


def test_extract_document_metadata_with_empty_values():
    doc = MagicMock(spec=Document)
    doc.tags.exists = MagicMock(return_value=False)
    doc.tags.all = MagicMock(return_value=[])
    doc.document_type = None
    doc.correspondent = None
    doc.storage_path = None

    result = _extract_document_metadata(doc)

    assert result["tags"] == []
    assert result["document_type"] is None
    assert result["correspondent"] is None
    assert result["storage_path"] is None


@pytest.mark.django_db
@patch("paperless_ai.ai_classifier._get_system_metadata")
def test_prompt_without_rag_includes_existing_metadata(
    mock_system_metadata,
    mock_document,
):
    mock_system_metadata.return_value = {
        "tags": ["Tag1", "Tag2", "Tax"],
        "document_types": ["Invoice", "Contract"],
        "correspondents": ["Test Correspondent", "Acme Corp"],
        "storage_paths": ["/archive/invoices", "/archive/contracts"],
    }
    config = AIConfig()
    prompt = build_prompt_without_rag(mock_document, config)

    assert "Existing Metadata:" in prompt
    assert "Tags: Tag1, Tag2" in prompt
    assert "Document Type: Invoice" in prompt
    assert "Correspondent: Test Correspondent" in prompt
    assert "Storage Path: /archive/invoices" in prompt
    assert "Use the existing metadata as hints" in prompt
    # System-wide metadata
    assert "Available Tags in System:" in prompt
    assert "Tag1, Tag2, Tax" in prompt
    assert "Available Document Types in System:" in prompt
    assert "Invoice, Contract" in prompt
    assert "Available Correspondents in System:" in prompt
    assert "Test Correspondent, Acme Corp" in prompt
    assert "Available Storage Paths in System:" in prompt
    assert "/archive/invoices, /archive/contracts" in prompt


@pytest.mark.django_db
@patch("paperless_ai.ai_classifier._get_system_metadata")
def test_prompt_without_rag_handles_missing_metadata(mock_system_metadata):
    mock_system_metadata.return_value = {
        "tags": ["Finance"],
        "document_types": ["Memo"],
        "correspondents": [],
        "storage_paths": [],
    }
    doc = MagicMock(spec=Document)
    doc.filename = "test.pdf"
    doc.content = "Some content."
    doc.tags.exists = MagicMock(return_value=False)
    doc.tags.all = MagicMock(return_value=[])
    doc.document_type = None
    doc.correspondent = None
    doc.storage_path = None

    config = AIConfig()
    prompt = build_prompt_without_rag(doc, config)

    assert "Existing Metadata:" in prompt
    assert "Tags: Not set" in prompt
    assert "Document Type: Not set" in prompt
    assert "Correspondent: Not set" in prompt
    assert "Storage Path: Not set" in prompt
    assert "Available Tags in System:" in prompt
    assert "Finance" in prompt


@pytest.mark.django_db
@patch("paperless_ai.ai_classifier._get_system_metadata")
@patch("paperless_ai.ai_classifier.get_context_for_document")
def test_prompt_with_rag_includes_existing_metadata(
    mock_get_context,
    mock_system_metadata,
    mock_document,
):
    mock_get_context.return_value = "Similar document context."
    mock_system_metadata.return_value = {
        "tags": ["Tag1", "Tag2"],
        "document_types": ["Invoice"],
        "correspondents": ["Test Correspondent"],
        "storage_paths": ["/archive/invoices"],
    }

    config = AIConfig()
    prompt = build_prompt_with_rag(mock_document, config)

    # RAG prompt should include both existing metadata and additional context
    assert "Existing Metadata:" in prompt
    assert "Tags: Tag1, Tag2" in prompt
    assert "Document Type: Invoice" in prompt
    assert "Available Tags in System:" in prompt
    assert "Additional context from similar documents" in prompt


@patch("paperless_ai.ai_classifier.Tag.objects")
@patch("paperless_ai.ai_classifier.DocumentType.objects")
@patch("paperless_ai.ai_classifier.Correspondent.objects")
@patch("paperless_ai.ai_classifier.StoragePath.objects")
def test_get_system_metadata(
    mock_storage_paths,
    mock_correspondents,
    mock_doc_types,
    mock_tags,
):
    # Configure mock querysets - tags chain is values_list().exclude().order_by()
    mock_tags.values_list.return_value.exclude.return_value.order_by.return_value = [
        "Finance",
        "Tax",
    ]
    mock_doc_types.values_list.return_value.order_by.return_value = [
        "Invoice",
        "Contract",
    ]
    mock_correspondents.values_list.return_value.order_by.return_value = [
        "Acme Corp",
        "Test Corp",
    ]
    mock_storage_paths.values_list.return_value.order_by.return_value = [
        "/archive/finance",
    ]

    result = _get_system_metadata()

    assert result["tags"] == ["Finance", "Tax"]
    assert result["document_types"] == ["Invoice", "Contract"]
    assert result["correspondents"] == ["Acme Corp", "Test Corp"]
    assert result["storage_paths"] == ["/archive/finance"]
