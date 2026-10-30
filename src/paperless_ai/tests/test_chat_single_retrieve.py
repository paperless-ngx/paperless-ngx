from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.models import Document
from paperless_ai.chat import stream_chat_with_documents
from paperless_testing.factories import DocumentFactory

if TYPE_CHECKING:
    import pytest_mock


@pytest.mark.django_db
class TestChatSingleRetrieve:
    def test_question_retrieves_once_and_synthesizes_those_nodes(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN a document with indexed content
        WHEN a chat question is streamed
        THEN the vector store is searched exactly once
        AND the answer is synthesized from the nodes that search returned
        """
        document = DocumentFactory.create(title="Test Document", content="ignored")
        top_nodes = [
            mocker.MagicMock(
                metadata={"document_id": str(document.pk), "title": "Test Document"},
            ),
        ]
        retriever = mocker.MagicMock()
        retriever.retrieve.return_value = top_nodes
        mocker.patch("paperless_ai.chat.AIClient")
        mocker.patch("paperless_ai.chat.load_or_build_index")
        mocker.patch(
            "llama_index.core.retrievers.VectorIndexRetriever",
            return_value=retriever,
        )
        synthesizer = mocker.patch(
            "llama_index.core.response_synthesizers.get_response_synthesizer",
        ).return_value
        synthesizer.synthesize.return_value.response_gen = iter(["chunk"])

        list(
            stream_chat_with_documents(
                "What is this?",
                Document.objects.filter(pk=document.pk),
            ),
        )

        retriever.retrieve.assert_called_once_with("What is this?")
        synthesizer.synthesize.assert_called_once_with("What is this?", top_nodes)
