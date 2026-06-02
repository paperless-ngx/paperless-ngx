import json
import logging
from typing import Any

import lancedb
import pyarrow as pa
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.schema import BaseNode
from llama_index.core.vector_stores.types import BasePydanticVectorStore
from llama_index.core.vector_stores.types import FilterCondition
from llama_index.core.vector_stores.types import FilterOperator
from llama_index.core.vector_stores.types import MetadataFilters
from llama_index.core.vector_stores.types import VectorStoreQuery
from llama_index.core.vector_stores.types import VectorStoreQueryResult
from llama_index.core.vector_stores.utils import metadata_dict_to_node
from llama_index.core.vector_stores.utils import node_to_metadata_dict

logger = logging.getLogger("paperless_ai.vector_store")

DEFAULT_TABLE_NAME = "documents"


def _escape(value: str) -> str:
    return str(value).replace("'", "''")


def _build_where(filters: MetadataFilters | None) -> str | None:
    """Translate the EQ / IN filters we use into a Lance SQL predicate on the
    top-level ``document_id`` column."""
    if filters is None or not filters.filters:
        return None
    clauses: list[str] = []
    for f in filters.filters:
        if f.operator == FilterOperator.IN:
            vals = ",".join(f"'{_escape(v)}'" for v in f.value)
            clauses.append(f"{f.key} IN ({vals})")
        elif f.operator == FilterOperator.EQ:
            clauses.append(f"{f.key} = '{_escape(f.value)}'")
        else:  # pragma: no cover - we only ever build EQ/IN filters
            raise NotImplementedError(f"Unsupported filter operator: {f.operator}")
    joiner = " OR " if filters.condition == FilterCondition.OR else " AND "
    return joiner.join(clauses)


class PaperlessLanceVectorStore(BasePydanticVectorStore):
    """A llama-index vector store backed directly by a LanceDB table.

    Stores one row per node with the node id, its document id (both as the
    ``ref_doc_id`` delete key ``doc_id`` and a top-level filter column
    ``document_id``), the embedding, and the serialised node (text + metadata)
    as JSON. ``stores_text`` lets llama-index run off this store alone, with no
    separate docstore or index store.
    """

    stores_text: bool = True
    flat_metadata: bool = True

    _uri: str = PrivateAttr()
    _table_name: str = PrivateAttr()
    _conn: Any = PrivateAttr()
    _table: Any = PrivateAttr()

    def __init__(self, uri: str, table_name: str = DEFAULT_TABLE_NAME) -> None:
        super().__init__()
        self._uri = uri
        self._table_name = table_name
        self._conn = lancedb.connect(uri)
        existing = list(self._conn.table_names())
        self._table = (
            self._conn.open_table(table_name) if table_name in existing else None
        )

    @property
    def client(self) -> Any:
        return self._conn

    def table_exists(self) -> bool:
        return self._table_name in list(self._conn.table_names())

    def vector_dim(self) -> int | None:
        if self._table is None:
            return None
        return self._table.schema.field("vector").type.list_size

    def drop_table(self) -> None:
        if self.table_exists():
            self._conn.drop_table(self._table_name)
        self._table = None

    @staticmethod
    def _schema(dim: int) -> pa.Schema:
        return pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("doc_id", pa.string()),
                pa.field("document_id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), dim)),
                pa.field("node_content", pa.string()),
            ],
        )

    def _row(self, node: BaseNode) -> dict[str, Any]:
        meta = node_to_metadata_dict(
            node,
            remove_text=False,
            flat_metadata=self.flat_metadata,
        )
        return {
            "id": node.node_id,
            "doc_id": node.ref_doc_id,
            "document_id": str(node.metadata.get("document_id")),
            "vector": node.get_embedding(),
            "node_content": json.dumps(meta),
        }

    def add(self, nodes: list[BaseNode], **add_kwargs: Any) -> list[str]:
        if not nodes:
            return []
        rows = [self._row(node) for node in nodes]
        if self._table is None:
            dim = len(nodes[0].get_embedding())
            self._table = self._conn.create_table(
                self._table_name,
                rows,
                schema=self._schema(dim),
            )
        else:
            self._table.add(rows)
        return [node.node_id for node in nodes]

    def delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        if self._table is not None:
            self._table.delete(f'doc_id = "{_escape(ref_doc_id)}"')

    def delete_nodes(
        self,
        node_ids: list[str] | None = None,
        filters: MetadataFilters | None = None,
        **delete_kwargs: Any,
    ) -> None:
        if self._table is None:
            return
        if node_ids:
            ids = ",".join(f'"{_escape(n)}"' for n in node_ids)
            self._table.delete(f"id IN ({ids})")
        elif filters is not None:
            where = _build_where(filters)
            if where:
                self._table.delete(where)

    def _rows_to_nodes(self, rows: list[dict[str, Any]]) -> list[BaseNode]:
        nodes: list[BaseNode] = []
        for row in rows:
            node = metadata_dict_to_node(json.loads(row["node_content"]))
            node.embedding = list(row["vector"])
            nodes.append(node)
        return nodes

    def get_nodes(
        self,
        node_ids: list[str] | None = None,
        filters: MetadataFilters | None = None,
        **kwargs: Any,
    ) -> list[BaseNode]:
        if self._table is None:
            return []
        query = self._table.search()
        where = _build_where(filters)
        if node_ids:
            ids = ",".join(f'"{_escape(n)}"' for n in node_ids)
            query = query.where(f"id IN ({ids})")
        elif where:
            query = query.where(where)
        return self._rows_to_nodes(query.to_list())

    def query(
        self,
        query: VectorStoreQuery,
        **kwargs: Any,
    ) -> VectorStoreQueryResult:
        if self._table is None:
            return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])
        top_k = query.similarity_top_k or 10
        search = self._table.search(query.query_embedding).limit(top_k)
        where = _build_where(query.filters)
        if where:
            search = search.where(where)
        rows = search.to_list()
        nodes = self._rows_to_nodes(rows)
        # LanceDB returns squared-L2 distance; map to a descending similarity.
        sims = [1.0 / (1.0 + float(row["_distance"])) for row in rows]
        ids = [row["id"] for row in rows]
        return VectorStoreQueryResult(nodes=nodes, similarities=sims, ids=ids)
