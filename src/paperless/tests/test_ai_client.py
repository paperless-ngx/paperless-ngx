import json
from unittest.mock import patch

import pytest
from django.conf import settings

from paperless.ai.client import AIClient


@pytest.fixture
def mock_settings():
    settings.LLM_BACKEND = "openai"
    settings.LLM_MODEL = "gpt-3.5-turbo"
    settings.LLM_API_KEY = "test-api-key"
    yield settings


@pytest.mark.django_db
@patch("paperless.ai.client.AIClient._run_openai_query")
@patch("paperless.ai.client.AIClient._run_ollama_query")
def test_run_llm_query_openai(mock_ollama_query, mock_openai_query, mock_settings):
    mock_settings.LLM_BACKEND = "openai"
    mock_openai_query.return_value = "OpenAI response"
    client = AIClient()
    result = client.run_llm_query("Test prompt")
    assert result == "OpenAI response"
    mock_openai_query.assert_called_once_with("Test prompt")
    mock_ollama_query.assert_not_called()


@pytest.mark.django_db
@patch("paperless.ai.client.AIClient._run_openai_query")
@patch("paperless.ai.client.AIClient._run_ollama_query")
def test_run_llm_query_ollama(mock_ollama_query, mock_openai_query, mock_settings):
    mock_settings.LLM_BACKEND = "ollama"
    mock_ollama_query.return_value = "Ollama response"
    client = AIClient()
    result = client.run_llm_query("Test prompt")
    assert result == "Ollama response"
    mock_ollama_query.assert_called_once_with("Test prompt")
    mock_openai_query.assert_not_called()


@pytest.mark.django_db
def test_run_llm_query_unsupported_backend(mock_settings):
    mock_settings.LLM_BACKEND = "unsupported"
    client = AIClient()
    with pytest.raises(ValueError, match="Unsupported LLM backend: unsupported"):
        client.run_llm_query("Test prompt")


@pytest.mark.django_db
def test_run_openai_query(httpx_mock, mock_settings):
    mock_settings.LLM_BACKEND = "openai"
    httpx_mock.add_response(
        url="https://api.openai.com/v1/chat/completions",
        json={
            "choices": [{"message": {"content": "OpenAI response"}}],
        },
    )

    client = AIClient()
    result = client.run_llm_query("Test prompt")
    assert result == "OpenAI response"

    request = httpx_mock.get_request()
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {mock_settings.LLM_API_KEY}"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == {
        "model": mock_settings.LLM_MODEL,
        "messages": [{"role": "user", "content": "Test prompt"}],
        "temperature": 0.3,
    }


@pytest.mark.django_db
def test_run_ollama_query(httpx_mock, mock_settings):
    mock_settings.LLM_BACKEND = "ollama"
    httpx_mock.add_response(
        url="http://localhost:11434/api/chat",
        json={"message": {"content": "Ollama response"}},
    )

    client = AIClient()
    result = client.run_llm_query("Test prompt")
    assert result == "Ollama response"

    request = httpx_mock.get_request()
    assert request.method == "POST"
    assert json.loads(request.content) == {
        "model": mock_settings.LLM_MODEL,
        "messages": [{"role": "user", "content": "Test prompt"}],
        "stream": False,
    }
