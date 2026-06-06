import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from llama_index.core.schema import TextNode

from paperless_ai import chat
from paperless_ai.chat import CHAT_ERROR_MESSAGE
from paperless_ai.chat import CHAT_METADATA_DELIMITER
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


@pytest.mark.django_db
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
        # Simulate get_nodes returning nodes (content exists)
        mock_index.vector_store.get_nodes.return_value = [mock_node]
        mock_load_index.return_value = mock_index

        mock_retriever_instance = MagicMock()
        mock_retriever_instance.retrieve.return_value = [
            MagicMock(
                metadata={
                    "document_id": str(mock_document.pk),
                    "title": "Test Document",
                },
            ),
        ]

        mock_response_stream = MagicMock()
        mock_response_stream.response_gen = iter(["chunk1", "chunk2"])
        mock_query_engine = MagicMock()
        mock_query_engine_cls.return_value = mock_query_engine
        mock_query_engine.query.return_value = mock_response_stream

        with patch(
            "llama_index.core.retrievers.VectorIndexRetriever",
            return_value=mock_retriever_instance,
        ):
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


@pytest.mark.django_db
def test_stream_chat_with_multiple_documents_retrieval(patch_embed_nodes) -> None:
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

        mock_node1 = TextNode(
            text="Content for doc 1.",
            metadata={"document_id": "1", "title": "Document 1"},
        )
        mock_node2 = TextNode(
            text="Content for doc 2.",
            metadata={"document_id": "2", "title": "Document 2"},
        )
        mock_index = MagicMock()
        # Simulate get_nodes returning nodes (content exists)
        mock_index.vector_store.get_nodes.return_value = [mock_node1, mock_node2]
        mock_load_index.return_value = mock_index

        mock_retriever_instance = MagicMock()
        mock_retriever_instance.retrieve.return_value = [
            MagicMock(metadata={"document_id": "1", "title": "Document 1"}),
            MagicMock(metadata={"document_id": "2", "title": "Document 2"}),
        ]

        mock_response_stream = MagicMock()
        mock_response_stream.response_gen = iter(["chunk1", "chunk2"])

        mock_query_engine = MagicMock()
        mock_query_engine_cls.return_value = mock_query_engine
        mock_query_engine.query.return_value = mock_response_stream

        doc1 = MagicMock(pk=1, title="Document 1", filename="doc1.pdf")
        doc2 = MagicMock(pk=2, title="Document 2", filename="doc2.pdf")

        with patch(
            "llama_index.core.retrievers.VectorIndexRetriever",
            return_value=mock_retriever_instance,
        ):
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


def test_stream_chat_empty_document_list() -> None:
    with patch("paperless_ai.chat.load_or_build_index") as mock_load_index:
        output = list(stream_chat_with_documents("Any info?", []))
        mock_load_index.assert_not_called()
        assert output == ["Sorry, I couldn't find any content to answer your question."]


def test_stream_chat_no_matching_nodes() -> None:
    with (
        patch("paperless_ai.chat.AIConfig"),
        patch("paperless_ai.chat.AIClient") as mock_client_cls,
        patch("paperless_ai.chat.load_or_build_index") as mock_load_index,
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.llm = MagicMock()

        mock_index = MagicMock()
        # No matching nodes in the store
        mock_index.vector_store.get_nodes.return_value = []
        mock_load_index.return_value = mock_index

        output = list(stream_chat_with_documents("Any info?", [MagicMock(pk=1)]))

        assert output == ["Sorry, I couldn't find any content to answer your question."]


def test_stream_chat_unexpected_failure_returns_generic_error(caplog) -> None:
    with (
        patch("paperless_ai.chat.AIConfig"),
        patch("paperless_ai.chat.AIClient") as mock_client_cls,
        patch("paperless_ai.chat.load_or_build_index") as mock_load_index,
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.llm = MagicMock()

        mock_index = MagicMock()
        # Nodes found so we get past the pre-check
        mock_index.vector_store.get_nodes.return_value = [MagicMock()]
        mock_load_index.return_value = mock_index

        with patch(
            "llama_index.core.retrievers.VectorIndexRetriever",
        ) as mock_retriever_cls:
            mock_retriever = MagicMock()
            mock_retriever.retrieve.side_effect = RuntimeError(
                "private provider detail",
            )
            mock_retriever_cls.return_value = mock_retriever

            output = list(stream_chat_with_documents("Any info?", [MagicMock(pk=1)]))

        assert output == [CHAT_ERROR_MESSAGE]
        assert "Failed to stream document chat response" in caplog.text
        assert "private provider detail" in caplog.text


@pytest.mark.django_db
class TestStreamChatRetrieval:
    def test_no_nodes_yields_no_content_message(
        self,
        temp_llm_index_dir,
        mock_embed_model,
    ) -> None:
        from documents.tests.factories import DocumentFactory

        doc = DocumentFactory.create(content="hello world")
        # Nothing indexed for this document yet.
        out = list(chat.stream_chat_with_documents("question?", [doc]))
        assert chat.CHAT_NO_CONTENT_MESSAGE in out

    def test_chat_filter_contains_only_requested_document_ids(
        self,
        temp_llm_index_dir,
        mock_embed_model,
        mocker,
    ) -> None:
        """The MetadataFilter passed to the retriever must be scoped to the
        requested documents only — content from other indexed documents must
        not be surfaced.
        """
        from documents.tests.factories import DocumentFactory
        from paperless_ai import indexing

        included = DocumentFactory.create(content="included document content")
        excluded = DocumentFactory.create(content="excluded document content")
        indexing.llm_index_add_or_update_document(included)
        indexing.llm_index_add_or_update_document(excluded)

        # VectorIndexRetriever is imported inside _stream_chat_with_documents;
        # patch it at the llama_index source so the lazy import picks it up.
        captured_filters = []
        mock_retriever = mocker.MagicMock()
        mock_retriever.retrieve.return_value = []

        def capture_retriever(*args, **kwargs):
            captured_filters.append(kwargs.get("filters"))
            return mock_retriever

        mocker.patch("paperless_ai.chat.AIClient")
        mocker.patch(
            "llama_index.core.retrievers.VectorIndexRetriever",
            side_effect=capture_retriever,
        )

        list(chat.stream_chat_with_documents("question?", [included]))

        assert captured_filters, "VectorIndexRetriever was never constructed"
        filt = captured_filters[0]
        assert filt is not None, "Retriever must receive a MetadataFilters"
        filter_values = filt.filters[0].value
        assert str(included.pk) in filter_values
        assert str(excluded.pk) not in filter_values
