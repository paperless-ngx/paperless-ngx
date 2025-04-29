import logging

from llama_index.core.llms import ChatMessage
from llama_index.llms.ollama import Ollama
from llama_index.llms.openai import OpenAI

from paperless.config import AIConfig

logger = logging.getLogger("paperless_ai.client")


class AIClient:
    """
    A client for interacting with an LLM backend.
    """

    def __init__(self):
        self.settings = AIConfig()
        self.llm = self.get_llm()

    def get_llm(self):
        if self.settings.llm_backend == "ollama":
            return Ollama(
                model=self.settings.llm_model or "llama3",
                base_url=self.settings.llm_url or "http://localhost:11434",
                request_timeout=120,
            )
        elif self.settings.llm_backend == "openai":
            return OpenAI(
                model=self.settings.llm_model or "gpt-3.5-turbo",
                api_key=self.settings.llm_api_key,
            )
        else:
            raise ValueError(f"Unsupported LLM backend: {self.settings.llm_backend}")

    def run_llm_query(self, prompt: str) -> str:
        logger.debug(
            "Running LLM query against %s with model %s",
            self.settings.llm_backend,
            self.settings.llm_model,
        )
        result = self.llm.complete(prompt)
        logger.debug("LLM query result: %s", result)
        return result

    def run_chat(self, messages: list[ChatMessage]) -> str:
        logger.debug(
            "Running chat query against %s with model %s",
            self.settings.llm_backend,
            self.settings.llm_model,
        )
        result = self.llm.chat(messages)
        logger.debug("Chat result: %s", result)
        return result
