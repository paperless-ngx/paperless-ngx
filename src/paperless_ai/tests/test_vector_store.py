from pathlib import Path

import pytest
from llama_index.core.schema import NodeRelationship
from llama_index.core.schema import RelatedNodeInfo
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import FilterOperator
from llama_index.core.vector_stores.types import MetadataFilter
from llama_index.core.vector_stores.types import MetadataFilters
from llama_index.core.vector_stores.types import VectorStoreQuery

from paperless_ai.vector_store import PaperlessLanceVectorStore

DIM = 8


def _node(node_id: str, document_id: str, text: str, vec: float) -> TextNode:
    node = TextNode(id_=node_id, text=text, metadata={"document_id": document_id})
    node.set_content(text)
    node.embedding = [vec] * DIM
    # Use relationships so ref_doc_id resolves correctly (it's a read-only property)
    node.relationships = {
        NodeRelationship.SOURCE: RelatedNodeInfo(node_id=document_id),
    }
    return node


class TestPaperlessLanceVectorStoreCrud:
    @pytest.fixture
    def store(self, tmp_path: Path) -> PaperlessLanceVectorStore:
        return PaperlessLanceVectorStore(uri=str(tmp_path / "idx"))

    def test_add_then_query_returns_node(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add([_node("1-0", "1", "alpha", 0.1), _node("2-0", "2", "beta", 0.9)])

        result = store.query(
            VectorStoreQuery(query_embedding=[0.1] * DIM, similarity_top_k=1),
        )

        assert len(result.nodes) == 1
        assert result.nodes[0].metadata["document_id"] == "1"

    def test_query_empty_table_returns_empty_no_raise(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        result = store.query(
            VectorStoreQuery(query_embedding=[0.1] * DIM, similarity_top_k=5),
        )
        assert result.nodes == []
        assert result.ids == []

    def test_delete_removes_all_chunks_of_document(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add([_node("1-0", "1", "a", 0.1), _node("1-1", "1", "b", 0.2)])
        store.add([_node("2-0", "2", "c", 0.9)])

        store.delete("1")

        assert store.client.open_table("documents").count_rows() == 1

    def test_query_with_in_filter_scopes_results(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add([_node("1-0", "1", "a", 0.1), _node("2-0", "2", "b", 0.1)])

        result = store.query(
            VectorStoreQuery(
                query_embedding=[0.1] * DIM,
                similarity_top_k=5,
                filters=MetadataFilters(
                    filters=[
                        MetadataFilter(
                            key="document_id",
                            operator=FilterOperator.IN,
                            value=["2"],
                        ),
                    ],
                ),
            ),
        )

        assert [n.metadata["document_id"] for n in result.nodes] == ["2"]

    def test_get_nodes_filter_returns_empty_cleanly(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add([_node("1-0", "1", "a", 0.1)])
        nodes = store.get_nodes(
            filters=MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="document_id",
                        operator=FilterOperator.IN,
                        value=["999"],
                    ),
                ],
            ),
        )
        assert nodes == []

    def test_fresh_instance_filters_existing_table(
        self,
        tmp_path: Path,
    ) -> None:
        uri = str(tmp_path / "idx")
        PaperlessLanceVectorStore(uri=uri).add(
            [_node("1-0", "1", "a", 0.1), _node("2-0", "2", "b", 0.1)],
        )

        reopened = PaperlessLanceVectorStore(uri=uri)
        result = reopened.query(
            VectorStoreQuery(
                query_embedding=[0.1] * DIM,
                similarity_top_k=5,
                filters=MetadataFilters(
                    filters=[
                        MetadataFilter(
                            key="document_id",
                            operator=FilterOperator.IN,
                            value=["1"],
                        ),
                    ],
                ),
            ),
        )
        assert [n.metadata["document_id"] for n in result.nodes] == ["1"]

    def test_table_exists_and_drop(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        assert store.table_exists() is False
        store.add([_node("1-0", "1", "a", 0.1)])
        assert store.table_exists() is True
        assert store.vector_dim() == DIM
        store.drop_table()
        assert store.table_exists() is False
