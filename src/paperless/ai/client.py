import logging

import httpx

from paperless.config import AIConfig

logger = logging.getLogger("paperless.ai.client")


class AIClient:
    """
    A client for interacting with an LLM backend.
    """

    def __init__(self):
        self.settings = AIConfig()

    def run_llm_query(self, prompt: str) -> str:
        logger.debug(
            "Running LLM query against %s with model %s",
            self.settings.llm_backend,
            self.settings.llm_model,
        )
        match self.settings.llm_backend:
            case "openai":
                result = self._run_openai_query(prompt)
            case "ollama":
                result = self._run_ollama_query(prompt)
            case _:
                raise ValueError(
                    f"Unsupported LLM backend: {self.settings.llm_backend}",
                )
        logger.debug("LLM query result: %s", result)
        return result

    def _run_ollama_query(self, prompt: str) -> str:
        url = self.settings.llm_url or "http://localhost:11434"
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{url}/api/generate",
                json={
                    "model": self.settings.llm_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json()["response"]

    def _run_openai_query(self, prompt: str) -> str:
        if not self.settings.llm_api_key:
            raise RuntimeError("PAPERLESS_LLM_API_KEY is not set")

        url = self.settings.llm_url or "https://api.openai.com"

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
