from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest

from documents.models import Document
from paperless_ai.chat import stream_chat_with_documents
from paperless_testing.factories import DocumentFactory

if TYPE_CHECKING:
    from collections.abc import Iterator

    import pytest_mock


@pytest.mark.django_db
class TestChatReadLock:
    def test_read_lock_is_released_before_the_answer_streams(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN a document with indexed content
        WHEN a chat question is streamed
        THEN the index read lock is held for the vector search only
        AND is released before the answer is synthesized and streamed
        """
        events: list[str] = []
        document = DocumentFactory.create(title="Test Document", content="ignored")

        @contextmanager
        def fake_read_store() -> Iterator[object]:
            events.append("lock acquired")
            try:
                yield mocker.MagicMock()
            finally:
                events.append("lock released")

        retriever = mocker.MagicMock()
        retriever.retrieve.side_effect = lambda _query: (
            events.append("retrieve")
            or [
                mocker.MagicMock(
                    metadata={
                        "document_id": str(document.pk),
                        "title": "Test Document",
                    },
                ),
            ]
        )

        def synthesize(*_args: object) -> object:
            events.append("synthesize")
            return mocker.MagicMock(response_gen=iter(["chunk"]))

        mocker.patch("paperless_ai.chat.read_store", fake_read_store)
        mocker.patch("paperless_ai.chat.AIClient")
        mocker.patch("paperless_ai.chat.load_or_build_index")
        mocker.patch(
            "llama_index.core.retrievers.VectorIndexRetriever",
            return_value=retriever,
        )
        mocker.patch(
            "llama_index.core.response_synthesizers.get_response_synthesizer",
        ).return_value.synthesize.side_effect = synthesize

        list(
            stream_chat_with_documents(
                "What is this?",
                Document.objects.filter(pk=document.pk),
            ),
        )

        assert events == [
            "lock acquired",
            "retrieve",
            "lock released",
            "synthesize",
        ]
