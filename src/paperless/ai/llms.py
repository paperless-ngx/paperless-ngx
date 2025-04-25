import json

import httpx
from llama_index.core.base.llms.types import ChatMessage
from llama_index.core.base.llms.types import ChatResponse
from llama_index.core.base.llms.types import ChatResponseGen
from llama_index.core.base.llms.types import CompletionResponse
from llama_index.core.base.llms.types import CompletionResponseGen
from llama_index.core.base.llms.types import LLMMetadata
from llama_index.core.llms.llm import LLM
from llama_index.core.prompts import SelectorPromptTemplate
from pydantic import Field


class OllamaLLM(LLM):
    model: str = Field(default="llama3")
    base_url: str = Field(default="http://localhost:11434")

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            model_name=self.model,
            is_chat_model=False,
            context_window=4096,
            num_output=512,
            is_function_calling_model=False,
        )

    def complete(self, prompt: str, **kwargs) -> CompletionResponse:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            return CompletionResponse(text=data["response"])

    def stream(self, prompt: str, **kwargs) -> CompletionResponseGen:
        return self.stream_complete(prompt, **kwargs)

    def stream_complete(
        self,
        prompt: SelectorPromptTemplate,
        **kwargs,
    ) -> CompletionResponseGen:
        headers = {"Content-Type": "application/json"}
        data = {
            "model": self.model,
            "prompt": prompt.format(llm=self),
            "stream": True,
        }

        with httpx.stream(
            "POST",
            f"{self.base_url}/api/generate",
            headers=headers,
            json=data,
            timeout=60.0,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if "response" in chunk:
                    yield CompletionResponse(text=chunk["response"])

    def chat(
        self,
        messages: list[ChatMessage],
        **kwargs,
    ) -> ChatResponse:  # pragma: no cover
        raise NotImplementedError("chat not supported")

    def stream_chat(
        self,
        messages: list[ChatMessage],
        **kwargs,
    ) -> ChatResponseGen:  # pragma: no cover
        raise NotImplementedError("stream_chat not supported")

    async def achat(
        self,
        messages: list[ChatMessage],
        **kwargs,
    ) -> ChatResponse:  # pragma: no cover
        raise NotImplementedError("async chat not supported")

    async def astream_chat(
        self,
        messages: list[ChatMessage],
        **kwargs,
    ) -> ChatResponseGen:  # pragma: no cover
        raise NotImplementedError("async stream_chat not supported")

    async def acomplete(
        self,
        prompt: str,
        **kwargs,
    ) -> CompletionResponse:  # pragma: no cover
        raise NotImplementedError("async complete not supported")

    async def astream_complete(
        self,
        prompt: str,
        **kwargs,
    ) -> CompletionResponseGen:  # pragma: no cover
        raise NotImplementedError("async stream_complete not supported")
