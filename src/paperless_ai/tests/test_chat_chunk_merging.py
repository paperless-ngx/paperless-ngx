"""Chat answers are generated from all retrieved chunks in as few LLM calls as the
configured context window allows, and fall back to the embedding chunk size when the
server rejects the larger prompt."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING

import httpx
import openai
import pytest
from asgiref.sync import async_to_sync
from llama_index.core.llms import CompletionResponse
from llama_index.core.llms import MockLLM
from llama_index.core.schema import NodeWithScore
from llama_index.core.schema import TextNode
from llama_index.core.utils import get_tokenizer
from pydantic import PrivateAttr

from documents.models import Document
from paperless_ai.chat import CHAT_ERROR_MESSAGE
from paperless_ai.chat import stream_chat_with_documents
from paperless_ai.indexing import RAG_NUM_OUTPUT
from paperless_testing.factories import DocumentFactory

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator

    import pytest_mock

CHUNK_COUNT = 5
# About 900 tokens for the estimator llama_index uses, so five of them fit in the
# default 8192 window but not in the default 1024 token chunk size limit.
CHUNK_TEXT = " ".join(["word"] * 900)


def _bad_request() -> openai.BadRequestError:
    request = httpx.Request("POST", "http://llm.invalid/v1/completions")
    return openai.BadRequestError(
        "request exceeds the available context size",
        response=httpx.Response(400, request=request),
        body=None,
    )


class ScriptedLLM(MockLLM):
    """Records every prompt it is sent and fails on request, the way a real server
    does: eagerly for a plain completion, lazily on the first token of a stream."""

    _prompts: list[str] = PrivateAttr(default_factory=list)
    _max_prompt_chars: int | None = PrivateAttr(default=None)
    _error: Exception | None = PrivateAttr(default=None)
    _tokens_before_error: int = PrivateAttr(default=0)

    def __init__(
        self,
        *,
        max_prompt_chars: int | None = None,
        error: Exception | None = None,
        tokens_before_error: int = 0,
    ) -> None:
        super().__init__()
        self._max_prompt_chars = max_prompt_chars
        self._error = error
        self._tokens_before_error = tokens_before_error

    @property
    def prompts(self) -> list[str]:
        return self._prompts

    def _failure(self, prompt: str) -> Exception | None:
        if self._max_prompt_chars is not None and len(prompt) > self._max_prompt_chars:
            return _bad_request()
        return self._error

    def complete(
        self,
        prompt: str,
        formatted: bool = False,  # noqa: FBT001, FBT002 (mirrors the base class)
        **kwargs: object,
    ) -> CompletionResponse:
        self._prompts.append(prompt)
        failure = self._failure(prompt)
        if failure is not None:
            raise failure
        return CompletionResponse(text="answer")

    def stream_complete(
        self,
        prompt: str,
        formatted: bool = False,  # noqa: FBT001, FBT002 (mirrors the base class)
        **kwargs: object,
    ) -> Iterator[CompletionResponse]:
        self._prompts.append(prompt)
        failure = self._failure(prompt)

        def generate() -> Iterator[CompletionResponse]:
            for index in range(self._tokens_before_error):
                yield CompletionResponse(text="partial", delta=f"partial{index}")
            if failure is not None:
                raise failure
            yield CompletionResponse(text="answer", delta="answer")

        return generate()


@pytest.fixture
def run_chat(
    mocker: pytest_mock.MockerFixture,
) -> Callable[..., list[str]]:
    """Stream one chat question through the real synthesizer, with retrieval,
    the index and the AI configuration stubbed."""

    def run(llm: ScriptedLLM, *, context_size: int = 8192) -> list[str]:
        document = DocumentFactory.create(title="Test Document", content="ignored")
        nodes = [
            NodeWithScore(
                node=TextNode(
                    text=CHUNK_TEXT,
                    metadata={"document_id": str(document.pk), "title": "Test"},
                ),
                score=0.9,
            )
            for _ in range(CHUNK_COUNT)
        ]
        retriever = mocker.MagicMock()
        retriever.retrieve.return_value = nodes

        mocker.patch("paperless_ai.chat.read_store")
        mocker.patch("paperless_ai.chat.load_or_build_index")
        mocker.patch(
            "paperless_ai.chat.AIConfig",
            return_value=SimpleNamespace(
                llm_context_size=context_size,
                llm_embedding_chunk_size=1024,
            ),
        )
        mocker.patch("paperless_ai.chat.AIClient").return_value.llm = llm
        mocker.patch(
            "llama_index.core.retrievers.VectorIndexRetriever",
            return_value=retriever,
        )

        async def drain() -> list[str]:
            return [
                chunk
                async for chunk in stream_chat_with_documents(
                    "What is this?",
                    Document.objects.filter(pk=document.pk),
                )
            ]

        # Driven from sync test code so the blocking setup runs on the test's own
        # thread, inside the test's DB transaction.
        return async_to_sync(drain)()

    return run


@pytest.mark.django_db
class TestChunkMerging:
    def test_retrieved_chunks_are_answered_in_a_single_llm_call(
        self,
        run_chat: Callable[..., list[str]],
    ) -> None:
        """
        GIVEN five retrieved chunks that together fit the configured context window
        WHEN a chat question is answered
        THEN the LLM is called once, with every chunk in the prompt
        """
        llm = ScriptedLLM()

        output = run_chat(llm, context_size=8192)

        assert CHAT_ERROR_MESSAGE not in output
        assert len(llm.prompts) == 1
        assert llm.prompts[0].count(CHUNK_TEXT) == CHUNK_COUNT

    def test_small_context_window_spreads_the_chunks_over_several_calls(
        self,
        run_chat: Callable[..., list[str]],
    ) -> None:
        """
        GIVEN a context window too small for all the retrieved chunks at once
        WHEN a chat question is answered
        THEN the chunks are spread over several LLM calls
        AND every prompt leaves room in the window for the answer
        """
        context_size = 4096
        tokenize = get_tokenizer()
        llm = ScriptedLLM()

        output = run_chat(llm, context_size=context_size)

        assert CHAT_ERROR_MESSAGE not in output
        assert len(llm.prompts) > 1
        assert all(
            len(tokenize(prompt)) <= context_size - RAG_NUM_OUTPUT
            for prompt in llm.prompts
        )


@pytest.mark.django_db
class TestContextWindowFallback:
    def test_rejected_prompt_is_retried_with_the_embedding_chunk_size(
        self,
        run_chat: Callable[..., list[str]],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN a server whose real context window is smaller than the configured one
        WHEN the merged prompt is rejected with a bad request
        THEN the question is answered again from smaller prompts
        AND a warning names the context size setting
        """
        max_prompt_chars = 12_000
        llm = ScriptedLLM(max_prompt_chars=max_prompt_chars)

        with caplog.at_level(logging.WARNING, logger="paperless_ai.chat"):
            output = run_chat(llm, context_size=8192)

        assert CHAT_ERROR_MESSAGE not in output
        assert "answer" in output
        assert len(llm.prompts[0]) > max_prompt_chars
        assert all(len(prompt) <= max_prompt_chars for prompt in llm.prompts[1:])
        assert "PAPERLESS_AI_LLM_CONTEXT_SIZE" in caplog.text

    def test_a_rejection_of_the_retry_yields_the_generic_error(
        self,
        run_chat: Callable[..., list[str]],
    ) -> None:
        """
        GIVEN a server that rejects every prompt
        WHEN a chat question is answered
        THEN the merged prompt is retried exactly once
        AND the user gets the generic error message
        """
        llm = ScriptedLLM(max_prompt_chars=0)

        output = run_chat(llm)

        assert output == [CHAT_ERROR_MESSAGE]
        assert len(llm.prompts) == 2

    def test_other_errors_are_not_retried(
        self,
        run_chat: Callable[..., list[str]],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN an LLM that fails with something other than a bad request
        WHEN a chat question is answered
        THEN there is no retry
        AND the user gets the generic error message
        """
        llm = ScriptedLLM(error=RuntimeError("provider is down"))

        with caplog.at_level(logging.WARNING, logger="paperless_ai.chat"):
            output = run_chat(llm)

        assert output == [CHAT_ERROR_MESSAGE]
        assert len(llm.prompts) == 1
        assert "PAPERLESS_AI_LLM_CONTEXT_SIZE" not in caplog.text

    def test_a_failure_after_tokens_were_streamed_is_not_retried(
        self,
        run_chat: Callable[..., list[str]],
    ) -> None:
        """
        GIVEN an answer that has started streaming to the user
        WHEN the stream then fails with a bad request
        THEN the answer is not started over
        """
        llm = ScriptedLLM(error=_bad_request(), tokens_before_error=1)

        output = run_chat(llm)

        assert output == ["partial0", CHAT_ERROR_MESSAGE]
        assert len(llm.prompts) == 1
