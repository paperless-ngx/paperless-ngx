import ipaddress
import json
from unittest.mock import ANY
from unittest.mock import MagicMock
from unittest.mock import patch

import httpx
import ollama
import openai
import pytest
from llama_index.core.llms.llm import ToolSelection

from paperless.network import BlockReason
from paperless.network import OutboundRequestBlockedError
from paperless_ai.client import LLM_SYSTEM_PROMPT
from paperless_ai.client import PLACEHOLDER_API_KEY
from paperless_ai.client import AIClient
from paperless_ai.exceptions import LLMBlockedError
from paperless_ai.exceptions import LLMProviderError
from paperless_ai.exceptions import LLMTimeoutError
from paperless_testing.outbound import guard_of


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
        http_client=ANY,
        async_http_client=ANY,
    )
    assert client.llm == mock_openai_llm.return_value


@pytest.mark.parametrize("configured_key", [None, ""])
def test_get_llm_openai_without_api_key_sends_placeholder(
    mock_ai_config,
    mock_openai_llm,
    configured_key,
):
    """openai SDK rejects empty key, see #13831."""
    mock_ai_config.llm_backend = "openai-like"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_api_key = configured_key
    mock_ai_config.llm_endpoint = "http://test-url"

    AIClient()

    assert mock_openai_llm.call_args.kwargs["api_key"] == PLACEHOLDER_API_KEY


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
            "tags": ["document"],
            "matched_tags": ["document"],
            "tag_ids": [1],
            "correspondents": ["John Doe"],
            "document_types": ["report"],
            "storage_paths": ["Reports"],
            "dates": ["2023-01-01"],
        },
    )

    client = AIClient()
    result = client.run_llm_query(
        "test_prompt",
        allowed_candidate_ids={"tags": {1}},
    )

    assert result["title"] == "Test Title"
    assert result["tags"] == {"existing_ids": [1], "new_names": []}
    mock_llm_instance.chat.assert_called_once_with(
        [ANY],
        format=ANY,
        think=False,
    )
    messages = mock_llm_instance.chat.call_args.args[0]
    assert messages[0].content == "test_prompt"


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
            "tags": ["document"],
            "matched_tags": ["document"],
            "tag_ids": [1],
            "correspondents": ["John Doe"],
            "document_types": ["report"],
            "storage_paths": ["Reports"],
            "dates": ["2023-01-01"],
        },
    )

    mock_llm_instance.chat_with_tools.return_value = MagicMock()
    mock_llm_instance.get_tool_calls_from_response.return_value = [tool_selection]

    client = AIClient()
    result = client.run_llm_query(
        "test_prompt",
        allowed_candidate_ids={"tags": {1}},
    )

    assert result["title"] == "Test Title"
    assert result["tags"] == {"existing_ids": [1], "new_names": []}
    mock_llm_instance.chat_with_tools.assert_called_once()
    kwargs = mock_llm_instance.chat_with_tools.call_args.kwargs
    offered_tool_name = kwargs["tools"][0].metadata.name
    assert kwargs["user_msg"].content == (
        "test_prompt\n\n"
        f"Answer by calling the {offered_tool_name} tool. "
        "Do not write the answer as text."
    )


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


def test_run_llm_query_openai_status_error_raises_provider_error(
    mock_ai_config,
    mock_openai_llm,
):
    mock_ai_config.llm_backend = "openai-like"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_endpoint = "http://test-url"

    request = httpx.Request("POST", "http://test-url/v1/chat/completions")
    body = {"error": {"message": "Thinking mode does not support this tool_choice"}}
    mock_openai_llm.return_value.chat_with_tools.side_effect = openai.BadRequestError(
        "Error code: 400",
        response=httpx.Response(400, request=request, json=body),
        body=body,
    )

    client = AIClient()

    with pytest.raises(LLMProviderError) as exc_info:
        client.run_llm_query("test_prompt")
    assert str(exc_info.value) == ""
    assert isinstance(exc_info.value.__cause__, openai.BadRequestError)


def test_run_llm_query_ollama_response_error_raises_provider_error(
    mock_ai_config,
    mock_ollama_llm,
):
    mock_ai_config.llm_backend = "ollama"
    mock_ai_config.llm_model = "test_model"
    mock_ai_config.llm_endpoint = "http://test-url"

    response_error = ollama.ResponseError(
        "confidential provider response",
        status_code=400,
    )
    mock_ollama_llm.return_value.chat.side_effect = response_error

    client = AIClient()

    with pytest.raises(LLMProviderError) as exc_info:
        client.run_llm_query("test_prompt")
    assert str(exc_info.value) == ""
    assert exc_info.value.__cause__ is response_error


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


class TestGuardedLLMClients:
    @pytest.mark.parametrize(
        ("endpoint", "allow_internal"),
        [
            pytest.param("http://test-url", True, id="internal-allowed"),
            pytest.param("http://93.184.216.34:11434", False, id="internal-blocked"),
        ],
    )
    def test_ollama_clients_are_guarded(
        self,
        mock_ai_config: MagicMock,
        mock_ollama_llm: MagicMock,
        endpoint: str,
        *,
        allow_internal: bool,
    ) -> None:
        """
        GIVEN:
            - The Ollama backend
        WHEN:
            - The LLM is built
        THEN:
            - Its sync and async clients use guarded transports with the setting
        """
        mock_ai_config.llm_backend = "ollama"
        mock_ai_config.llm_model = "test_model"
        mock_ai_config.llm_endpoint = endpoint
        mock_ai_config.llm_allow_internal_endpoints = allow_internal

        AIClient()

        kwargs = mock_ollama_llm.call_args.kwargs
        assert guard_of(kwargs["client"]._client)._allow_internal is allow_internal
        assert (
            guard_of(kwargs["async_client"]._client)._allow_internal is allow_internal
        )

    @pytest.mark.parametrize(
        ("endpoint", "allow_internal"),
        [
            pytest.param("http://test-url", True, id="internal-allowed"),
            pytest.param("http://93.184.216.34:8080", False, id="internal-blocked"),
        ],
    )
    def test_openai_like_clients_are_guarded(
        self,
        mock_ai_config: MagicMock,
        mock_openai_llm: MagicMock,
        endpoint: str,
        *,
        allow_internal: bool,
    ) -> None:
        """
        GIVEN:
            - The OpenAI-like backend with an endpoint
        WHEN:
            - The LLM is built
        THEN:
            - Its sync and async http clients use guarded transports
        """
        mock_ai_config.llm_backend = "openai-like"
        mock_ai_config.llm_model = "test_model"
        mock_ai_config.llm_api_key = "key"
        mock_ai_config.llm_endpoint = endpoint
        mock_ai_config.llm_allow_internal_endpoints = allow_internal

        AIClient()

        kwargs = mock_openai_llm.call_args.kwargs
        assert guard_of(kwargs["http_client"])._allow_internal is allow_internal
        assert guard_of(kwargs["async_http_client"])._allow_internal is allow_internal


def _block() -> OutboundRequestBlockedError:
    return OutboundRequestBlockedError(
        host="llm.example",
        port=443,
        reason=BlockReason.NON_PUBLIC_ADDRESS,
        address=ipaddress.ip_address("10.0.0.1"),
    )


class TestBlockedLLMRequests:
    def test_ollama_block_becomes_llm_blocked_error(
        self,
        mock_ai_config: MagicMock,
        mock_ollama_llm: MagicMock,
    ) -> None:
        """
        GIVEN:
            - The Ollama backend and a connection blocked by policy
        WHEN:
            - An LLM query runs
        THEN:
            - LLMBlockedError is raised with a message, chained to the block
            - The message, which tracked tasks store, names the destination but
              not the resolved internal address
        """
        mock_ai_config.llm_backend = "ollama"
        mock_ai_config.llm_model = "test_model"
        mock_ai_config.llm_endpoint = "http://test-url"
        block = _block()
        mock_ollama_llm.return_value.chat.side_effect = block

        with pytest.raises(LLMBlockedError) as exc_info:
            AIClient().run_llm_query("test_prompt")

        assert exc_info.value.__cause__ is block
        assert "llm.example:443" in str(exc_info.value)
        assert "10.0.0.1" not in str(exc_info.value)

    def test_openai_wrapped_block_becomes_llm_blocked_error(
        self,
        mock_ai_config: MagicMock,
        mock_openai_llm: MagicMock,
    ) -> None:
        """
        GIVEN:
            - The OpenAI-like backend, whose SDK wraps the block in
              APIConnectionError
        WHEN:
            - An LLM query runs
        THEN:
            - LLMBlockedError is raised
        """
        mock_ai_config.llm_backend = "openai-like"
        mock_ai_config.llm_model = "test_model"
        mock_ai_config.llm_api_key = "key"
        mock_ai_config.llm_endpoint = "http://test-url"
        wrapped = openai.APIConnectionError(
            request=httpx.Request("POST", "http://test-url/v1/chat/completions"),
        )
        wrapped.__cause__ = _block()
        mock_openai_llm.return_value.chat_with_tools.side_effect = wrapped

        with pytest.raises(LLMBlockedError):
            AIClient().run_llm_query("test_prompt")
