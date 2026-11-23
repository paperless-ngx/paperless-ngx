from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from paperless_ai.chat import stream_chat_with_documents

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.mark.asyncio
async def test_closing_after_a_chunk_closes_the_provider_stream() -> None:
    provider_closed = False

    async def provider_stream() -> AsyncIterator[str]:
        nonlocal provider_closed
        try:
            yield "first"
            yield "second"
        finally:
            provider_closed = True

    provider = provider_stream()

    # Like llama-index, forward chunks without closing the stream read from
    async def async_response_gen() -> AsyncIterator[str]:
        async for chunk in provider:
            yield chunk

    response_stream = MagicMock(async_response_gen=async_response_gen)
    response_stream.response_gen = provider
    synthesizer = MagicMock(asynthesize=AsyncMock(return_value=response_stream))
    references = [{"id": 1, "title": "Doc"}]

    with patch(
        "paperless_ai.chat._prepare_chat",
        return_value=(synthesizer, [], references),
    ):
        chunks = stream_chat_with_documents("Any info?", MagicMock())
        assert await anext(chunks) == "first"
        await chunks.aclose()

    assert provider_closed
    with pytest.raises(StopAsyncIteration):
        await anext(chunks)
