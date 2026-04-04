import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llama_index.core.llms import ChatMessage
    from llama_index.llms.ollama import Ollama
    from llama_index.llms.openai import OpenAI

from paperless.config import AIConfig
from paperless.network import validate_outbound_http_url
from paperless_ai.base_model import DocumentClassifierSchema

logger = logging.getLogger("paperless_ai.client")


class AIClient:
    """
    A client for interacting with an LLM backend.
    """

    def __init__(self) -> None:
        self.settings = AIConfig()
        self.llm = self.get_llm()

    def get_llm(self) -> "Ollama | OpenAI":
        if self.settings.llm_backend == "ollama":
            from llama_index.llms.ollama import Ollama

            endpoint = self.settings.llm_endpoint or "http://localhost:11434"
            validate_outbound_http_url(
                endpoint,
                allow_internal=self.settings.llm_allow_internal_endpoints,
            )
            return Ollama(
                model=self.settings.llm_model or "llama3.1",
                base_url=endpoint,
                request_timeout=120,
            )
        elif self.settings.llm_backend == "openai":
            from llama_index.llms.openai import OpenAI

            endpoint = self.settings.llm_endpoint or None
            if endpoint:
                validate_outbound_http_url(
                    endpoint,
                    allow_internal=self.settings.llm_allow_internal_endpoints,
                )
            return OpenAI(
                model=self.settings.llm_model or "gpt-3.5-turbo",
                api_base=endpoint,
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

        from llama_index.core.llms import ChatMessage
        from llama_index.core.program.function_program import get_function_tool

        user_msg = ChatMessage(role="user", content=prompt)
        tool = get_function_tool(DocumentClassifierSchema)
        result = self.llm.chat_with_tools(
            tools=[tool],
            user_msg=user_msg,
            chat_history=[],
        )
        tool_calls = self.llm.get_tool_calls_from_response(
            result,
            error_on_no_tool_call=True,
        )
        logger.debug("LLM query result: %s", tool_calls)
        parsed = DocumentClassifierSchema(**tool_calls[0].tool_kwargs)
        return parsed.model_dump()

    def run_chat(self, messages: list["ChatMessage"]) -> str:
        logger.debug(
            "Running chat query against %s with model %s",
            self.settings.llm_backend,
            self.settings.llm_model,
        )
        result = self.llm.chat(messages)
        logger.debug("Chat result: %s", result)
        return result
