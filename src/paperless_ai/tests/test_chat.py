import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from llama_index.core.schema import TextNode

from paperless_ai.chat import CHAT_ERROR_MESSAGE
from paperless_ai.chat import CHAT_METADATA_DELIMITER
from paperless_ai.chat import _get_document_filtered_retriever
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
        yield mock_embed_nodes


@pytest.fixture
def mock_document():
    doc = MagicMock()
    doc.pk = 1
    doc.title = "Test Document"
    doc.filename = "test_file.pdf"
    doc.content = "This is the document content."
    return doc


def assert_chat_output(
    output: list[str],
    *,
    expected_chunks: list[str],
    expected_references: list[dict[str, int | str]],
) -> None:
    assert output[:-1] == expected_chunks

    trailer = output[-1]
    assert trailer.startswith(CHAT_METADATA_DELIMITER)
    assert json.loads(trailer.removeprefix(CHAT_METADATA_DELIMITER)) == {
        "references": expected_references,
    }


def add_vector_query_results(mock_index, nodes: list[TextNode]) -> None:
    mock_index.index_struct.nodes_dict = {
        str(vector_id): node.node_id for vector_id, node in enumerate(nodes)
    }
    mock_index.docstore.docs.get.side_effect = {
        node.node_id: node for node in nodes
    }.get
    mock_index.vector_store._faiss_index.ntotal = len(nodes)
    mock_index.vector_store.query.return_value = MagicMock(
        ids=list(mock_index.index_struct.nodes_dict),
        similarities=[0.1] * len(nodes),
    )
    mock_index._embed_model.get_agg_embedding_from_queries.return_value = [0.1] * 1536


def test_document_filtered_retriever_expands_filters_and_caches() -> None:
    allowed_node1 = TextNode(
        text="Allowed content 1.",
        metadata={"document_id": "1", "title": "Allowed 1"},
    )
    allowed_node2 = TextNode(
        text="Allowed content 2.",
        metadata={"document_id": "2", "title": "Allowed 2"},
    )
    foreign_node = TextNode(
        text="Foreign content.",
        metadata={"document_id": "3", "title": "Foreign"},
    )
    missing_node = TextNode(
        text="Missing content.",
        metadata={"document_id": "1", "title": "Missing"},
    )

    mock_index = MagicMock()
    mock_index.index_struct.nodes_dict = {
        "0": foreign_node.node_id,
        "1": missing_node.node_id,
        "2": allowed_node1.node_id,
        "3": allowed_node2.node_id,
    }
    mock_index.docstore.docs.get.side_effect = {
        allowed_node1.node_id: allowed_node1,
        allowed_node2.node_id: allowed_node2,
        foreign_node.node_id: foreign_node,
    }.get
    mock_index.vector_store._faiss_index.ntotal = 4
    mock_index.vector_store.query.side_effect = [
        MagicMock(ids=["0", "2"], similarities=[0.9, 0.8]),
        MagicMock(ids=["0", "1", "3"], similarities=[0.9, 0.7, 0.6]),
    ]
    mock_index._embed_model.get_agg_embedding_from_queries.return_value = [0.1] * 1536

    retriever = _get_document_filtered_retriever(
        mock_index,
        {"1", "2"},
        similarity_top_k=2,
    )

    nodes = retriever.retrieve("question")
    cached_nodes = retriever.retrieve("question")

    assert [node.node.node_id for node in nodes] == [
        allowed_node1.node_id,
        allowed_node2.node_id,
    ]
    assert cached_nodes == nodes
    assert mock_index.vector_store.query.call_count == 2
    assert mock_index._embed_model.get_agg_embedding_from_queries.call_count == 1


def test_document_filtered_retriever_handles_empty_faiss_index() -> None:
    mock_index = MagicMock()
    mock_index.vector_store._faiss_index.ntotal = 0
    mock_index._embed_model.get_agg_embedding_from_queries.return_value = [0.1] * 1536

    retriever = _get_document_filtered_retriever(
        mock_index,
        {"1"},
        similarity_top_k=2,
    )

    assert retriever.retrieve("question") == []
    mock_index.vector_store.query.assert_not_called()


def test_stream_chat_with_one_document_retrieval(
    mock_document,
    patch_embed_nodes,
) -> None:
    with (
        patch("paperless_ai.chat.AIClient") as mock_client_cls,
        patch("paperless_ai.chat.load_or_build_index") as mock_load_index,
        patch(
            "llama_index.core.query_engine.RetrieverQueryEngine.from_args",
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
        add_vector_query_results(mock_index, [mock_node])
        mock_load_index.return_value = mock_index

        mock_response_stream = MagicMock()
        mock_response_stream.response_gen = iter(["chunk1", "chunk2"])
        mock_query_engine = MagicMock()
        mock_query_engine_cls.return_value = mock_query_engine
        mock_query_engine.query.return_value = mock_response_stream

        output = list(stream_chat_with_documents("What is this?", [mock_document]))

        mock_query_engine.query.assert_called_once_with("What is this?")
        patch_embed_nodes.assert_not_called()
        assert_chat_output(
            output,
            expected_chunks=["chunk1", "chunk2"],
            expected_references=[
                {"id": mock_document.pk, "title": "Test Document"},
            ],
        )


def test_stream_chat_with_multiple_documents_retrieval(patch_embed_nodes) -> None:
    with (
        patch("paperless_ai.chat.AIClient") as mock_client_cls,
        patch("paperless_ai.chat.load_or_build_index") as mock_load_index,
        patch(
            "llama_index.core.query_engine.RetrieverQueryEngine.from_args",
        ) as mock_query_engine_cls,
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
        mock_duplicate_node = TextNode(
            text="More content for doc 1.",
            metadata={"document_id": "1", "title": "Document 1 Duplicate"},
        )
        mock_foreign_node = TextNode(
            text="Content for doc 3.",
            metadata={"document_id": "3", "title": "Document 3"},
        )
        mock_index = MagicMock()
        mock_index.docstore.docs.values.return_value = [
            mock_node1,
            mock_node2,
            mock_duplicate_node,
            mock_foreign_node,
        ]
        add_vector_query_results(
            mock_index,
            [mock_node1, mock_duplicate_node, mock_node2, mock_foreign_node],
        )
        mock_load_index.return_value = mock_index

        # Mock response stream
        mock_response_stream = MagicMock()
        mock_response_stream.response_gen = iter(["chunk1", "chunk2"])

        # Mock RetrieverQueryEngine
        mock_query_engine = MagicMock()
        mock_query_engine_cls.return_value = mock_query_engine
        mock_query_engine.query.return_value = mock_response_stream

        # Fake documents
        doc1 = MagicMock(pk=1, title="Document 1", filename="doc1.pdf")
        doc2 = MagicMock(pk=2, title="Document 2", filename="doc2.pdf")

        output = list(stream_chat_with_documents("What's up?", [doc1, doc2]))

        mock_query_engine.query.assert_called_once_with("What's up?")
        patch_embed_nodes.assert_not_called()
        assert_chat_output(
            output,
            expected_chunks=["chunk1", "chunk2"],
            expected_references=[
                {"id": 1, "title": "Document 1"},
                {"id": 2, "title": "Document 2"},
            ],
        )


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


def test_stream_chat_unexpected_failure_returns_generic_error(caplog) -> None:
    with (
        patch("paperless_ai.chat.AIClient") as mock_client_cls,
        patch("paperless_ai.chat.load_or_build_index") as mock_load_index,
        patch(
            "paperless_ai.chat._get_document_filtered_retriever",
        ) as mock_get_retriever,
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.llm = MagicMock()

        mock_node = TextNode(
            text="This is node content.",
            metadata={"document_id": "1", "title": "Test Document"},
        )
        mock_index = MagicMock()
        mock_index.docstore.docs.values.return_value = [mock_node]
        mock_load_index.return_value = mock_index

        mock_retriever = MagicMock()
        mock_retriever.retrieve.side_effect = RuntimeError("private provider detail")
        mock_get_retriever.return_value = mock_retriever

        output = list(stream_chat_with_documents("Any info?", [MagicMock(pk=1)]))

        assert output == [CHAT_ERROR_MESSAGE]
        assert "Failed to stream document chat response" in caplog.text
        assert "private provider detail" in caplog.text
