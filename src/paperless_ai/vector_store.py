import json
import logging
from collections.abc import Sequence
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

# Below this many chunks, LanceDB's exact (brute-force) search is sufficient and
# faster than building an ANN index (per LanceDB guidance, ~100K vectors).
ANN_INDEX_MIN_ROWS = 100_000
# IVF_PQ default; num_sub_vectors must evenly divide the embedding dimension.
ANN_PQ_SUB_VECTORS = 96


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

    Implemented surface of ``BasePydanticVectorStore``
    ---------------------------------------------------
    Only the methods actively used by this codebase are implemented.
    ``delete_nodes`` and the ``node_ids`` lookup path of ``get_nodes`` are
    part of the llama-index interface contract and may be needed if a future
    retriever or extension invokes them — add them then, with tests.
    """

    stores_text: bool = True
    flat_metadata: bool = False

    _uri: str = PrivateAttr()
    _table_name: str = PrivateAttr()
    _conn: Any = PrivateAttr()
    _table: Any = PrivateAttr()

    def __init__(self, uri: str, table_name: str = DEFAULT_TABLE_NAME) -> None:
        super().__init__(stores_text=True, flat_metadata=False)
        self._uri = uri
        self._table_name = table_name
        self._conn = lancedb.connect(uri)
        existing = self._conn.list_tables().tables
        self._table = (
            self._conn.open_table(table_name) if table_name in existing else None
        )

    @property
    def client(self) -> Any:
        return self._conn

    def table_exists(self) -> bool:
        return self._table_name in self._conn.list_tables().tables

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

    def add(self, nodes: Sequence[BaseNode], **add_kwargs: Any) -> list[str]:
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

    def upsert_document(self, document_id: str, nodes: list[BaseNode]) -> list[str]:
        """Atomically replace all stored chunks of ``document_id`` with ``nodes``.

        A single ``merge_insert`` commit: matching node ids are updated, new ids
        inserted, and any existing rows for this document that are not in the new
        set are deleted (``when_not_matched_by_source_delete``). This prunes stale
        trailing chunks when an edit reduces a document's chunk count, with no
        transient empty state for concurrent lock-free readers.
        """
        if not nodes:
            # No indexable content: remove any existing chunks for this document.
            if self._table is not None:
                self._table.delete(f"document_id = '{_escape(document_id)}'")
            return []
        rows = [self._row(node) for node in nodes]
        if self._table is None:
            dim = len(nodes[0].get_embedding())
            self._table = self._conn.create_table(
                self._table_name,
                rows,
                schema=self._schema(dim),
            )
            return [node.node_id for node in nodes]
        (
            self._table.merge_insert("id")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .when_not_matched_by_source_delete(
                f"document_id = '{_escape(document_id)}'",
            )
            .execute(rows)
        )
        return [node.node_id for node in nodes]

    def delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        if self._table is not None:
            self._table.delete(f"doc_id = '{_escape(ref_doc_id)}'")

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
        if node_ids is not None:  # pragma: no cover
            # node_ids lookup is not implemented; see class docstring.
            raise NotImplementedError(
                "PaperlessLanceVectorStore does not support node_ids lookup",
            )
        if self._table is None:
            return []
        where = _build_where(filters)
        query = self._table.search()
        if where:
            query = query.where(where)
        return self._rows_to_nodes(query.to_list())

    def has_nodes(self, filters: MetadataFilters | None = None) -> bool:
        """Return True if at least one matching node exists (cheap existence check)."""
        if self._table is None:
            return False
        where = _build_where(filters)
        query = self._table.search()
        if where:
            query = query.where(where)
        return len(query.limit(1).to_list()) > 0

    def query(
        self,
        query: VectorStoreQuery,
        **kwargs: Any,
    ) -> VectorStoreQueryResult:
        if self._table is None:
            return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])
        top_k = query.similarity_top_k if query.similarity_top_k is not None else 10
        search = self._table.search(query.query_embedding).limit(top_k)
        where = _build_where(query.filters)
        if where:
            search = search.where(where)
        rows = search.to_list()
        nodes = self._rows_to_nodes(rows)
        # LanceDB returns an L2 distance (smaller = closer); map to a descending similarity.
        sims = [1.0 / (1.0 + float(row["_distance"])) for row in rows]
        ids = [row["id"] for row in rows]
        return VectorStoreQueryResult(nodes=nodes, similarities=sims, ids=ids)

    def _has_vector_index(self) -> bool:
        return any("vector" in idx.columns for idx in self._table.list_indices())

    def maybe_create_ann_index(self, min_rows: int = ANN_INDEX_MIN_ROWS) -> None:
        """Best-effort: build an IVF index once the table is large enough.

        IVF_PQ is used when ``num_sub_vectors`` divides the embedding dimension,
        otherwise IVF_FLAT (no divisor constraint). Any failure is logged and
        leaves the table on exact search, which is always correct.
        """
        if self._table is None:
            return
        rows = self._table.count_rows()
        if rows < min_rows or self._has_vector_index():
            return
        num_partitions = max(1, rows // 4096)
        # Embedding dim from the schema's fixed-size list column.
        dim = self._table.schema.field("vector").type.list_size
        try:
            if dim % ANN_PQ_SUB_VECTORS == 0:  # pragma: no cover
                self._table.create_index(
                    metric="l2",
                    num_partitions=num_partitions,
                    num_sub_vectors=ANN_PQ_SUB_VECTORS,
                    index_type="IVF_PQ",
                )
            else:
                self._table.create_index(
                    metric="l2",
                    num_partitions=num_partitions,
                    index_type="IVF_FLAT",
                )
        except Exception as e:  # pragma: no cover - depends on data/dim
            logger.warning("Skipping ANN index creation: %s", e)

    def ensure_document_id_scalar_index(self) -> None:
        """Create a scalar index on the filter column (never on the merge key
        ``id`` — see LanceDB #3177)."""
        if self._table is None:
            return
        try:
            self._table.create_scalar_index("document_id", replace=True)
        except Exception as e:  # pragma: no cover
            logger.warning("Skipping document_id scalar index: %s", e)

    def compact(self, retention_seconds: int) -> None:
        """Compact fragments and prune old MVCC versions in one call."""
        if self._table is None:
            return
        from datetime import timedelta

        self._table.optimize(cleanup_older_than=timedelta(seconds=retention_seconds))
