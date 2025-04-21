import json
from unittest.mock import patch

import pytest
from django.conf import settings

from paperless.ai.client import _run_ollama_query
from paperless.ai.client import _run_openai_query
from paperless.ai.client import run_llm_query


@pytest.fixture
def mock_settings():
    settings.LLM_BACKEND = "openai"
    settings.LLM_MODEL = "gpt-3.5-turbo"
    settings.LLM_API_KEY = "test-api-key"
    settings.OPENAI_URL = "https://api.openai.com"
    settings.OLLAMA_URL = "https://ollama.example.com"
    yield settings


@patch("paperless.ai.client._run_openai_query")
@patch("paperless.ai.client._run_ollama_query")
def test_run_llm_query_openai(mock_ollama_query, mock_openai_query, mock_settings):
    mock_openai_query.return_value = "OpenAI response"
    result = run_llm_query("Test prompt")
    assert result == "OpenAI response"
    mock_openai_query.assert_called_once_with("Test prompt")
    mock_ollama_query.assert_not_called()


@patch("paperless.ai.client._run_openai_query")
@patch("paperless.ai.client._run_ollama_query")
def test_run_llm_query_ollama(mock_ollama_query, mock_openai_query, mock_settings):
    mock_settings.LLM_BACKEND = "ollama"
    mock_ollama_query.return_value = "Ollama response"
    result = run_llm_query("Test prompt")
    assert result == "Ollama response"
    mock_ollama_query.assert_called_once_with("Test prompt")
    mock_openai_query.assert_not_called()


def test_run_llm_query_unsupported_backend(mock_settings):
    mock_settings.LLM_BACKEND = "unsupported"
    with pytest.raises(ValueError, match="Unsupported LLM backend: unsupported"):
        run_llm_query("Test prompt")


def test_run_openai_query(httpx_mock, mock_settings):
    httpx_mock.add_response(
        url=f"{mock_settings.OPENAI_URL}/v1/chat/completions",
        json={
            "choices": [{"message": {"content": "OpenAI response"}}],
        },
    )

    result = _run_openai_query("Test prompt")
    assert result == "OpenAI response"

    request = httpx_mock.get_request()
    assert request.method == "POST"
    assert request.url == f"{mock_settings.OPENAI_URL}/v1/chat/completions"
    assert request.headers["Authorization"] == f"Bearer {mock_settings.LLM_API_KEY}"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == {
        "model": mock_settings.LLM_MODEL,
        "messages": [{"role": "user", "content": "Test prompt"}],
        "temperature": 0.3,
    }


def test_run_ollama_query(httpx_mock, mock_settings):
    httpx_mock.add_response(
        url=f"{mock_settings.OLLAMA_URL}/api/chat",
        json={"message": {"content": "Ollama response"}},
    )

    result = _run_ollama_query("Test prompt")
    assert result == "Ollama response"

    request = httpx_mock.get_request()
    assert request.method == "POST"
    assert request.url == f"{mock_settings.OLLAMA_URL}/api/chat"
    assert json.loads(request.content) == {
        "model": mock_settings.LLM_MODEL,
        "messages": [{"role": "user", "content": "Test prompt"}],
        "stream": False,
    }
