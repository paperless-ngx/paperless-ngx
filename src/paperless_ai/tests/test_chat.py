import json
from unittest.mock import MagicMock

import pytest
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode
from pytest_mock import MockerFixture

from paperless_ai.chat import CHAT_METADATA_DELIMITER
from paperless_ai.chat import stream_chat_with_documents


@pytest.fixture(autouse=True)
def patch_embed_model():
    from llama_index.core import settings as llama_settings
    from llama_index.core.embeddings.mock_embed_model import MockEmbedding

    llama_settings.Settings.embed_model = MockEmbedding(embed_dim=1536)
    yield
    llama_settings.Settings.embed_model = None


@pytest.fixture(autouse=True)
def patch_embed_nodes(mocker: MockerFixture):
    mock = mocker.patch("llama_index.core.indices.vector_store.base.embed_nodes")
    mock.side_effect = lambda nodes, *_args, **_kwargs: {
        node.node_id: [0.1] * 1536 for node in nodes
    }


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


def test_stream_chat_with_one_document_full_content(mocker: MockerFixture) -> None:
    mock_document = MagicMock()
    mock_document.pk = 1
    mock_document.title = "Test Document"
    mock_document.filename = "test_file.pdf"
    mock_document.content = "This is the document content."

    mock_client = MagicMock()
    mocker.patch("paperless_ai.chat.AIClient", return_value=mock_client)

    mock_node = TextNode(
        text="This is node content.",
        metadata={"document_id": str(mock_document.pk), "title": "Test Document"},
    )
    mock_index = MagicMock()
    mock_index.docstore.docs.values.return_value = [mock_node]
    mocker.patch("paperless_ai.chat.load_or_build_index", return_value=mock_index)

    mock_response_stream = MagicMock()
    mock_response_stream.response_gen = iter(["chunk1", "chunk2"])
    mock_query_engine = MagicMock()
    mock_query_engine.query.return_value = mock_response_stream
    mocker.patch(
        "llama_index.core.query_engine.RetrieverQueryEngine.from_args",
        return_value=mock_query_engine,
    )

    output = list(stream_chat_with_documents("What is this?", [mock_document]))

    assert_chat_output(
        output,
        expected_chunks=["chunk1", "chunk2"],
        expected_references=[{"id": mock_document.pk, "title": "Test Document"}],
    )


def test_stream_chat_with_multiple_documents_retrieval(
    patch_embed_nodes,
    mocker: MockerFixture,
) -> None:
    mock_client = MagicMock()
    mocker.patch("paperless_ai.chat.AIClient", return_value=mock_client)

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
    mocker.patch("paperless_ai.chat.load_or_build_index", return_value=mock_index)

    mock_retriever = MagicMock()
    mock_duplicate_node = TextNode(
        text="More content for doc 1.",
        metadata={"document_id": "1", "title": "Document 1 Duplicate"},
    )
    mock_foreign_node = TextNode(
        text="Content for doc 3.",
        metadata={"document_id": "3", "title": "Document 3"},
    )
    mock_retriever.retrieve.return_value = [
        mock_node1,
        mock_duplicate_node,
        mock_node2,
        mock_foreign_node,
    ]
    mocker.patch.object(VectorStoreIndex, "as_retriever", return_value=mock_retriever)

    mock_response_stream = MagicMock()
    mock_response_stream.response_gen = iter(["chunk1", "chunk2"])
    mock_query_engine = MagicMock()
    mock_query_engine.query.return_value = mock_response_stream
    mocker.patch(
        "llama_index.core.query_engine.RetrieverQueryEngine.from_args",
        return_value=mock_query_engine,
    )

    doc1 = MagicMock(pk=1, title="Document 1", filename="doc1.pdf")
    doc2 = MagicMock(pk=2, title="Document 2", filename="doc2.pdf")

    output = list(stream_chat_with_documents("What's up?", [doc1, doc2]))

    assert_chat_output(
        output,
        expected_chunks=["chunk1", "chunk2"],
        expected_references=[
            {"id": 1, "title": "Document 1"},
            {"id": 2, "title": "Document 2"},
        ],
    )


def test_stream_chat_no_matching_nodes(mocker: MockerFixture) -> None:
    mock_client = MagicMock()
    mocker.patch("paperless_ai.chat.AIClient", return_value=mock_client)

    mock_index = MagicMock()
    mock_index.docstore.docs.values.return_value = []
    mocker.patch("paperless_ai.chat.load_or_build_index", return_value=mock_index)

    output = list(stream_chat_with_documents("Any info?", [MagicMock(pk=1)]))

    assert output == ["Sorry, I couldn't find any content to answer your question."]
