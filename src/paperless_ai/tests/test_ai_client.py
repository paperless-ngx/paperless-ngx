from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from paperless_ai.base_model import DocumentClassifierSchema
from paperless_ai.client import AIClient

VALID_SUGGESTIONS = {
    "title": "Test Title",
    "tags": ["test", "document"],
    "correspondents": ["John Doe"],
    "document_types": ["report"],
    "storage_paths": ["Reports"],
    "dates": ["2023-01-01"],
}

LLM_SETTINGS = {
    "llm_backend": "openai-like",
    "llm_model": "some_model",
    "llm_api_key": None,
    "llm_endpoint": None,
    "llm_request_timeout": 60,
    "llm_allow_internal_endpoints": True,
}


@pytest.fixture
def openai_like_settings():
    return SimpleNamespace(**LLM_SETTINGS)


def test_run_llm_query_uses_grammar_enforced_structured_output(openai_like_settings):
    """
    GIVEN:
        - An openai-like backend
        - A structured output call that returns a valid DocumentClassifierSchema
    WHEN:
        - run_llm_query() is called
    THEN:
        - The grammar-enforced response_format path is used, not tool calls
        - The parsed schema object is mapped to ClassificationSuggestions
        - The raw prompt is sent as the user message
    """
    with patch("paperless_ai.client.AIConfig") as mock_config:
        mock_config.return_value = openai_like_settings
        client = AIClient()
    parsed = DocumentClassifierSchema(**VALID_SUGGESTIONS)
    structured = MagicMock()
    structured.chat.return_value = SimpleNamespace(raw=parsed)
    client.llm = MagicMock()
    client.llm.as_structured_llm.return_value = structured

    result = client.run_llm_query("Classification prompt")

    client.llm.as_structured_llm.assert_called_once_with(DocumentClassifierSchema)
    client.llm.chat_with_tools.assert_not_called()
    messages = structured.chat.call_args_list[0].args[0]
    assert messages[0].content == "Classification prompt"
    assert result["title"] == "Test Title"
    assert result["tags"]["new_names"] == ["test", "document"]
    assert result["correspondents"]["new_names"] == ["John Doe"]


def test_get_llm_forces_structure_outputs_for_self_hosted_models(
    openai_like_settings,
):
    """
    GIVEN:
        - An openai-like backend with a non-OpenAI model name, which llama_index
          does not cover with its is_json_schema_supported allowlist
    WHEN:
        - AIClient is constructed
    THEN:
        - The LLM instance reports structured outputs as supported, so the
          grammar-enforced response_format path is used instead of tool calls
    """
    openai_like_settings.llm_model = "gemma-4-E4B-it-QAT-MLX-4bit"
    with patch("paperless_ai.client.AIConfig") as mock_config:
        mock_config.return_value = openai_like_settings
        client = AIClient()

    assert client.llm._should_use_structure_outputs() is True
