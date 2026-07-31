import json
from unittest.mock import ANY
from unittest.mock import MagicMock
from unittest.mock import patch

import httpx
import openai
import pytest
from llama_index.core.llms.llm import ToolSelection

from paperless_ai.client import LLM_SYSTEM_PROMPT
from paperless_ai.client import THINKING_DISABLED_KWARGS
from paperless_ai.client import AIClient
from paperless_ai.exceptions import LLMTimeoutError


@pytest.fixture
def mock_ai_config():
    with patch("paperless_ai.client.AIConfig") as MockAIConfig:
        mock_config = MagicMock()
        mock_config.llm_allow_internal_endpoints = True
        mock_config.llm_context_size = 8192
        mock_config.llm_request_timeout = 120
        MockAIConfig.return_value = mock_config
        yield mock_config


@pytest.fixture
def mock_ollama_llm():
    with patch("llama_index.llms.ollama.Ollama") as MockOllama:
        yield MockOllama


@pytest.fixture
def mock_openai_llm():
    with patch("llama_index.llms.openai_like.OpenAILike") as MockOpenAILike:
        yield MockOpenAILike


def test_get_llm_ollama(mock_ai_config, mock_ollama_llm):
    mock_ai_config.llm_backend = "ollama"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_endpoint = "http://test-url"

    client = AIClient()

    mock_ollama_llm.assert_called_once_with(
        model="test_model",
        base_url="http://test-url",
        context_window=8192,
        request_timeout=120,
        system_prompt=LLM_SYSTEM_PROMPT,
        client=ANY,
        async_client=ANY,
    )
    assert client.llm == mock_ollama_llm.return_value


def test_get_llm_openai(mock_ai_config, mock_openai_llm):
    mock_ai_config.llm_backend = "openai-like"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_api_key = "test_api_key"
    mock_ai_config.llm_endpoint = "http://test-url"

    client = AIClient()

    mock_openai_llm.assert_called_once_with(
        model="test_model",
        api_base="http://test-url",
        api_key="test_api_key",
        timeout=120,
        is_chat_model=True,
        is_function_calling_model=True,
        system_prompt=LLM_SYSTEM_PROMPT,
        additional_kwargs=THINKING_DISABLED_KWARGS,
        http_client=ANY,
        async_http_client=ANY,
    )
    assert client.llm == mock_openai_llm.return_value


def test_get_llm_openai_blocks_internal_endpoint_when_disallowed(mock_ai_config):
    mock_ai_config.llm_backend = "openai-like"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_api_key = "test_api_key"
    mock_ai_config.llm_endpoint = "http://127.0.0.1:1234"
    mock_ai_config.llm_allow_internal_endpoints = False

    with pytest.raises(ValueError, match="non-public address"):
        AIClient()


def test_get_llm_unsupported_backend(mock_ai_config):
    mock_ai_config.llm_backend = "unsupported"

    with pytest.raises(ValueError, match="Unsupported LLM backend: unsupported"):
        AIClient()


def test_run_llm_query_ollama_uses_structured_json(mock_ai_config, mock_ollama_llm):
    mock_ai_config.llm_backend = "ollama"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_endpoint = "http://test-url"

    mock_llm_instance = mock_ollama_llm.return_value
    mock_llm_instance.chat.return_value = MagicMock()
    mock_llm_instance.chat.return_value.message.content = json.dumps(
        {
            "title": "Test Title",
            "tags": ["test", "document"],
            "correspondents": ["John Doe"],
            "document_types": ["report"],
            "storage_paths": ["Reports"],
            "dates": ["2023-01-01"],
        },
    )

    client = AIClient()
    result = client.run_llm_query("test_prompt")

    assert result["title"] == "Test Title"
    mock_llm_instance.chat.assert_called_once_with(
        [ANY],
        format=ANY,
        think=False,
    )


def test_run_llm_query_openai_uses_tools(mock_ai_config, mock_openai_llm):
    mock_ai_config.llm_backend = "openai-like"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_api_key = "test_api_key"
    mock_ai_config.llm_endpoint = "http://test-url"

    mock_llm_instance = mock_openai_llm.return_value

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
    mock_llm_instance.chat_with_tools.assert_called_once()


def _tool_selection() -> ToolSelection:
    return ToolSelection(
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


def _configure_openai(mock_ai_config) -> None:
    mock_ai_config.llm_backend = "openai-like"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_api_key = "test_api_key"
    mock_ai_config.llm_endpoint = "http://test-url"


def _bad_request(message: str) -> openai.BadRequestError:
    request = httpx.Request("POST", "http://test-url/v1/chat/completions")
    response = httpx.Response(
        400,
        request=request,
        json={"error": {"message": message}},
    )
    return openai.BadRequestError(message, response=response, body=None)


def test_run_llm_query_openai_retries_without_thinking_kwargs(
    mock_ai_config,
    mock_openai_llm,
):
    """A provider that rejects the thinking argument still gets an answer."""
    _configure_openai(mock_ai_config)

    mock_llm_instance = mock_openai_llm.return_value
    mock_llm_instance.additional_kwargs = dict(THINKING_DISABLED_KWARGS)
    mock_llm_instance.chat_with_tools.side_effect = [
        _bad_request("unrecognized request argument supplied: chat_template_kwargs"),
        MagicMock(),
    ]
    mock_llm_instance.get_tool_calls_from_response.return_value = [_tool_selection()]

    client = AIClient()
    result = client.run_llm_query("test_prompt")

    assert result["title"] == "Test Title"
    assert mock_llm_instance.chat_with_tools.call_count == 2
    assert "extra_body" not in mock_llm_instance.additional_kwargs


def test_run_llm_query_openai_does_not_retry_unrelated_bad_request(
    mock_ai_config,
    mock_openai_llm,
):
    _configure_openai(mock_ai_config)

    mock_llm_instance = mock_openai_llm.return_value
    mock_llm_instance.additional_kwargs = dict(THINKING_DISABLED_KWARGS)
    mock_llm_instance.chat_with_tools.side_effect = _bad_request("model not found")

    client = AIClient()

    with pytest.raises(openai.BadRequestError):
        client.run_llm_query("test_prompt")

    assert mock_llm_instance.chat_with_tools.call_count == 1


def test_run_llm_query_openai_reports_reasoning_only_response(
    mock_ai_config,
    mock_openai_llm,
):
    """A thinking model that answers in the reasoning channel gets a real hint."""
    _configure_openai(mock_ai_config)

    response = MagicMock()
    response.message.content = ""
    response.message.additional_kwargs = {"reasoning_content": "Let me think..."}

    mock_llm_instance = mock_openai_llm.return_value
    mock_llm_instance.additional_kwargs = dict(THINKING_DISABLED_KWARGS)
    mock_llm_instance.chat_with_tools.return_value = response
    mock_llm_instance.get_tool_calls_from_response.side_effect = ValueError(
        "Expected at least one tool call, but got 0 tool calls.",
    )

    client = AIClient()

    with pytest.raises(ValueError, match="thinking is still active"):
        client.run_llm_query("test_prompt")


def test_run_llm_query_openai_keeps_original_error_without_reasoning(
    mock_ai_config,
    mock_openai_llm,
):
    _configure_openai(mock_ai_config)

    response = MagicMock()
    response.message.content = "some answer"
    response.message.additional_kwargs = {}

    mock_llm_instance = mock_openai_llm.return_value
    mock_llm_instance.additional_kwargs = dict(THINKING_DISABLED_KWARGS)
    mock_llm_instance.chat_with_tools.return_value = response
    mock_llm_instance.get_tool_calls_from_response.side_effect = ValueError(
        "Expected at least one tool call, but got 0 tool calls.",
    )

    client = AIClient()

    with pytest.raises(ValueError, match=r"^Expected at least one tool call"):
        client.run_llm_query("test_prompt")


def test_run_llm_query_openai_timeout_raises_local_error(
    mock_ai_config,
    mock_openai_llm,
):
    mock_ai_config.llm_backend = "openai-like"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_api_key = "test_api_key"
    mock_ai_config.llm_endpoint = "http://test-url"

    request = httpx.Request("POST", "http://test-url/v1/chat/completions")
    mock_openai_llm.return_value.chat_with_tools.side_effect = openai.APITimeoutError(
        request,
    )

    client = AIClient()

    with pytest.raises(LLMTimeoutError):
        client.run_llm_query("test_prompt")


def test_run_llm_query_httpx_timeout_raises_local_error(
    mock_ai_config,
    mock_ollama_llm,
):
    mock_ai_config.llm_backend = "ollama"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_endpoint = "http://test-url"

    mock_llm_instance = mock_ollama_llm.return_value
    mock_llm_instance.chat.side_effect = httpx.ReadTimeout("timed out")

    client = AIClient()

    with pytest.raises(LLMTimeoutError):
        client.run_llm_query("test_prompt")
