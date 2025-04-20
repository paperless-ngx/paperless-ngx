import httpx
from django.conf import settings


def run_llm_query(prompt: str) -> str:
    if settings.LLM_BACKEND == "ollama":
        return _run_ollama_query(prompt)
    return _run_openai_query(prompt)


def _run_ollama_query(prompt: str) -> str:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json={
                "model": settings.LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


def _run_openai_query(prompt: str) -> str:
    if not settings.LLM_API_KEY:
        raise RuntimeError("PAPERLESS_LLM_API_KEY is not set")

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{settings.OPENAI_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
