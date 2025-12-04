from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from llama_index.core.llms import ChatMessage
from llama_index.core.llms.llm import ToolSelection

from paperless_ai.client import AIClient


@pytest.fixture
def mock_ai_config():
    with patch("paperless_ai.client.AIConfig") as MockAIConfig:
        mock_config = MagicMock()
        MockAIConfig.return_value = mock_config
        yield mock_config


@pytest.fixture
def mock_ollama_llm():
    with patch("paperless_ai.client.Ollama") as MockOllama:
        yield MockOllama


@pytest.fixture
def mock_openai_llm():
    with patch("paperless_ai.client.OpenAI") as MockOpenAI:
        yield MockOpenAI


def test_get_llm_ollama(mock_ai_config, mock_ollama_llm):
    mock_ai_config.llm_backend = "ollama"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_endpoint = "http://test-url"

    client = AIClient()

    mock_ollama_llm.assert_called_once_with(
        model="test_model",
        base_url="http://test-url",
        request_timeout=120,
    )
    assert client.llm == mock_ollama_llm.return_value


def test_get_llm_openai(mock_ai_config, mock_openai_llm):
    mock_ai_config.llm_backend = "openai"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_api_key = "test_api_key"
    mock_ai_config.llm_endpoint = "http://test-url"

    client = AIClient()

    mock_openai_llm.assert_called_once_with(
        model="test_model",
        api_base="http://test-url",
        api_key="test_api_key",
    )
    assert client.llm == mock_openai_llm.return_value


def test_get_llm_unsupported_backend(mock_ai_config):
    mock_ai_config.llm_backend = "unsupported"

    with pytest.raises(ValueError, match="Unsupported LLM backend: unsupported"):
        AIClient()


def test_run_llm_query(mock_ai_config, mock_ollama_llm):
    mock_ai_config.llm_backend = "ollama"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_endpoint = "http://test-url"

    mock_llm_instance = mock_ollama_llm.return_value

    tool_selection = ToolSelection(
        tool_id="call_test",
        tool_name="DocumentClassifierSchema",
        tool_kwargs={
            "title": "Test Title",
            "tags": ["test", "document"],
            "correspondents": ["John Doe"],
            "document_types": ["report"],
            "storage_paths": ["Reports"],
            "dates": ["2023-01-01"],
        },
    )

    mock_llm_instance.chat_with_tools.return_value = MagicMock()
    mock_llm_instance.get_tool_calls_from_response.return_value = [tool_selection]

    client = AIClient()
    result = client.run_llm_query("test_prompt")

    assert result["title"] == "Test Title"


def test_run_chat(mock_ai_config, mock_ollama_llm):
    mock_ai_config.llm_backend = "ollama"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_endpoint = "http://test-url"

    mock_llm_instance = mock_ollama_llm.return_value
    mock_llm_instance.chat.return_value = "test_chat_result"

    client = AIClient()
    messages = [ChatMessage(role="user", content="Hello")]
    result = client.run_chat(messages)

    mock_llm_instance.chat.assert_called_once_with(messages)
    assert result == "test_chat_result"
