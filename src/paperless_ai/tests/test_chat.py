from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode

from paperless_ai.chat import stream_chat_with_documents


@pytest.fixture(autouse=True)
def patch_embed_model():
    from llama_index.core import settings as llama_settings
    from llama_index.core.embeddings.mock_embed_model import MockEmbedding

    # Use a real BaseEmbedding subclass to satisfy llama-index 0.14 validation
    llama_settings.Settings.embed_model = MockEmbedding(embed_dim=1536)
    yield
    llama_settings.Settings.embed_model = None


@pytest.fixture(autouse=True)
def patch_embed_nodes():
    with patch(
        "llama_index.core.indices.vector_store.base.embed_nodes",
    ) as mock_embed_nodes:
        mock_embed_nodes.side_effect = lambda nodes, *_args, **_kwargs: {
            node.node_id: [0.1] * 1536 for node in nodes
        }
        yield


@pytest.fixture
def mock_document():
    doc = MagicMock()
    doc.pk = 1
    doc.title = "Test Document"
    doc.filename = "test_file.pdf"
    doc.content = "This is the document content."
    return doc


def test_stream_chat_with_one_document_full_content(mock_document) -> None:
    with (
        patch("paperless_ai.chat.AIClient") as mock_client_cls,
        patch("paperless_ai.chat.load_or_build_index") as mock_load_index,
        patch(
            "paperless_ai.chat.RetrieverQueryEngine.from_args",
        ) as mock_query_engine_cls,
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.llm = MagicMock()

        mock_node = TextNode(
            text="This is node content.",
            metadata={"document_id": str(mock_document.pk), "title": "Test Document"},
        )
        mock_index = MagicMock()
        mock_index.docstore.docs.values.return_value = [mock_node]
        mock_load_index.return_value = mock_index

        mock_response_stream = MagicMock()
        mock_response_stream.response_gen = iter(["chunk1", "chunk2"])
        mock_query_engine = MagicMock()
        mock_query_engine_cls.return_value = mock_query_engine
        mock_query_engine.query.return_value = mock_response_stream

        output = list(stream_chat_with_documents("What is this?", [mock_document]))

        assert output == ["chunk1", "chunk2"]


def test_stream_chat_with_multiple_documents_retrieval(patch_embed_nodes) -> None:
    with (
        patch("paperless_ai.chat.AIClient") as mock_client_cls,
        patch("paperless_ai.chat.load_or_build_index") as mock_load_index,
        patch(
            "paperless_ai.chat.RetrieverQueryEngine.from_args",
        ) as mock_query_engine_cls,
        patch.object(VectorStoreIndex, "as_retriever") as mock_as_retriever,
    ):
        # Mock AIClient and LLM
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.llm = MagicMock()

        # Create two real TextNodes
        mock_node1 = TextNode(
            text="Content for doc 1.",
            metadata={"document_id": "1", "title": "Document 1"},
        )
        mock_node2 = TextNode(
            text="Content for doc 2.",
            metadata={"document_id": "2", "title": "Document 2"},
        )
        mock_index = MagicMock()
        mock_index.docstore.docs.values.return_value = [mock_node1, mock_node2]
        mock_load_index.return_value = mock_index

        # Patch as_retriever to return a retriever whose retrieve() returns mock_node1 and mock_node2
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [mock_node1, mock_node2]
        mock_as_retriever.return_value = mock_retriever

        # Mock response stream
        mock_response_stream = MagicMock()
        mock_response_stream.response_gen = iter(["chunk1", "chunk2"])

        # Mock RetrieverQueryEngine
        mock_query_engine = MagicMock()
        mock_query_engine_cls.return_value = mock_query_engine
        mock_query_engine.query.return_value = mock_response_stream

        # Fake documents
        doc1 = MagicMock(pk=1)
        doc2 = MagicMock(pk=2)

        output = list(stream_chat_with_documents("What's up?", [doc1, doc2]))

        assert output == ["chunk1", "chunk2"]


def test_stream_chat_no_matching_nodes() -> None:
    with (
        patch("paperless_ai.chat.AIClient") as mock_client_cls,
        patch("paperless_ai.chat.load_or_build_index") as mock_load_index,
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.llm = MagicMock()

        mock_index = MagicMock()
        # No matching nodes
        mock_index.docstore.docs.values.return_value = []
        mock_load_index.return_value = mock_index

        output = list(stream_chat_with_documents("Any info?", [MagicMock(pk=1)]))

        assert output == ["Sorry, I couldn't find any content to answer your question."]
