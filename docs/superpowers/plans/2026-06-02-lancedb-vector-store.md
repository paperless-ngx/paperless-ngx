# LanceDB Vector Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the AI feature's FAISS + `SimpleDocumentStore` + `SimpleIndexStore` llama-index storage with a single LanceDB table fronted by a custom `BasePydanticVectorStore` adapter, eliminating fake deletes, whole-file rewrites, the custom chat retriever, and pandas.

**Architecture:** A new `paperless_ai/vector_store.py` defines `PaperlessLanceVectorStore`, a llama-index `BasePydanticVectorStore` talking to `lancedb` + `pyarrow` directly. `indexing.py` is rewired to build the index from that store alone (`VectorStoreIndex.from_vector_store`), add/update via atomic `merge_insert` upsert, remove via predicate delete, and query/similar/chat via stock retrievers with `MetadataFilters`. Disk bloat from MVCC is reclaimed with `optimize(cleanup_older_than=...)` folded into the scheduled `update_llm_index`.

**Tech Stack:** Python 3.11+, Django, llama-index-core, lancedb 0.33.x, pyarrow, pytest + pytest-django + pytest-mock, factory-boy, uv.

**Reference spec:** `docs/superpowers/specs/2026-06-02-lancedb-vector-store-design.md`

---

## Conventions for this plan

- Backend tests are **pytest-style, grouped in classes**, with `@pytest.mark.django_db` on the class when DB access is needed. Annotate fixture params, fixture return types, and test signatures. Use the `mocker` fixture (pytest-mock), not bare `patch`. Build models with `DocumentFactory` from `documents/tests/factories.py`. (See `CLAUDE.md`.)
- Run a single test: `uv run pytest src/paperless_ai/tests/test_vector_store.py::TestClass::test_x -v`
- Lint/format with the **global** `ruff`: `ruff check src/paperless_ai` and `ruff format src/paperless_ai` (not `uv run ruff`).
- **Tests cannot be executed in the authoring session on this machine** — where a step says "Run … Expected: PASS", the implementer runs it and confirms before moving on.
- Commit messages end with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## HARD CONSTRAINT: lazy imports of AI libraries

**`llama_index`, `lancedb`, and `pyarrow` must never be imported at module-load time of any module reachable from a non-AI entry point.** A simple management command must not transitively drag in gigabytes of AI libraries. This is a known past regression and a hard requirement.

The existing code already enforces this pattern, and this plan must preserve it:

- `documents/tasks.py` imports `paperless_ai.indexing` **at module top**, and management commands import `documents.tasks` / `documents.models`. So anything `indexing.py` pulls at module-load time lands in the light path.
- Today `indexing.py` and `embedding.py` keep all `llama_index` / `faiss` imports **function-local** (e.g. `build_document_node` imports `LlamaDocument` inside the function). Importing `indexing.py` does **not** import `llama_index`.

Rules for this plan:

1. `paperless_ai/vector_store.py` (the new adapter) **may** import `lancedb` / `pyarrow` / `llama_index` at its top level — it is pure AI code.
2. **`indexing.py` must import `vector_store` only inside functions** (e.g. inside `get_vector_store()`), never at module top. Use `if TYPE_CHECKING:` for type hints.
3. **Any `llama_index` symbol used in `indexing.py` / `chat.py` (including `MetadataMode`, retrievers, filters) must be imported inside the function that uses it**, never at module top.
4. Test modules under `paperless_ai/tests/` **may** import these at the top — they are AI tests.
5. A subprocess guard test (Task 6) asserts that importing `documents.tasks` leaves `lancedb` / `pyarrow` / `llama_index` absent from `sys.modules`.

---

## File Structure

- **Create** `src/paperless_ai/vector_store.py` — `PaperlessLanceVectorStore` adapter (schema, add, upsert_document, delete, get_nodes, query, `_build_where`, `maybe_create_ann_index`, `optimize`). Single responsibility: the LanceDB ↔ llama-index storage boundary.
- **Create** `src/paperless_ai/tests/test_vector_store.py` — adapter unit/integration tests.
- **Modify** `src/paperless_ai/indexing.py` — factory + load/build/add/update/remove/similar functions rewired to the adapter; delete `get_or_create_storage_context`, `remove_document_docstore_nodes`; change `build_document_node`, `vector_store_file_exists`, `update_llm_index`, `llm_index_add_or_update_document`, `llm_index_remove_document`, `query_similar_documents`, `load_or_build_index`.
- **Modify** `src/paperless_ai/chat.py` — delete `_get_document_filtered_retriever`; use stock `VectorIndexRetriever` with filters; switch the no-content pre-check to `store.get_nodes`.
- **Modify** `src/documents/tasks.py` — call adapter compaction at the end of `update_llm_index` (via indexing helper) — no new beat task.
- **Modify** `pyproject.toml` — drop `faiss-cpu`, `llama-index-vector-stores-faiss`; add `lancedb`, `pyarrow`.
- **Modify** `src/paperless_ai/embedding.py` — add a `current_embedding_dim()` helper used by the dimension-mismatch guard (logic already mostly present in `get_embedding_dim`).
- **Modify** `src/paperless_ai/tests/test_ai_indexing.py`, `src/paperless_ai/tests/test_chat.py` — update tests that referenced FAISS/docstore internals.

---

## Task 1: Swap dependencies

**Files:**

- Modify: `pyproject.toml:45` (remove `faiss-cpu`), `pyproject.toml:60` (remove `llama-index-vector-stores-faiss`), and add `lancedb` + `pyarrow` in alphabetical position.

- [ ] **Step 1: Remove the FAISS dependencies**

In `pyproject.toml`, delete these two lines from the `dependencies` array:

```toml
  "faiss-cpu>=1.10",
```

```toml
  "llama-index-vector-stores-faiss>=0.5.2",
```

- [ ] **Step 2: Add lancedb and pyarrow**

In the same `dependencies` array, add (keep the array alphabetized — `lancedb` goes just before `langdetect`, `pyarrow` just before `python-dateutil`):

```toml
  "lancedb~=0.33.0",
```

```toml
  "pyarrow>=16",
```

- [ ] **Step 3: Resolve the lockfile**

Run: `uv sync --group dev`
Expected: resolves and installs; `faiss-cpu` and `llama-index-vector-stores-faiss` are removed, `lancedb`/`pyarrow` added. No `pandas` is added.

- [ ] **Step 4: Verify pandas is absent and lancedb imports**

Run: `uv run python -c "import importlib.util as u; import lancedb, pyarrow; print('lancedb', lancedb.__version__); print('pandas present:', u.find_spec('pandas') is not None)"`
Expected: prints the lancedb version and `pandas present: False`.

- [ ] **Step 5: Verify multi-arch wheels resolved**

Run: `uv pip show lancedb pyarrow`
Expected: both shown with versions. (Linux x86_64 + aarch64 wheels exist for lancedb 0.33.x — confirm CI Docker build later.)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: replace faiss-cpu with lancedb for the AI vector store

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: The adapter — schema, add, delete, get_nodes, query

**Files:**

- Create: `src/paperless_ai/vector_store.py`
- Test: `src/paperless_ai/tests/test_vector_store.py`

- [ ] **Step 1: Write the failing test for add → query round-trip**

Create `src/paperless_ai/tests/test_vector_store.py`:

```python
from pathlib import Path

import pytest
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
    node.relationships = {}
    node.ref_doc_id = document_id
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest src/paperless_ai/tests/test_vector_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'paperless_ai.vector_store'`.

- [ ] **Step 3: Write the adapter (add/delete/get_nodes/query/client)**

Create `src/paperless_ai/vector_store.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest src/paperless_ai/tests/test_vector_store.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Add delete / filter / get_nodes / fresh-process tests**

Append to `src/paperless_ai/tests/test_vector_store.py` inside `TestPaperlessLanceVectorStoreCrud`:

```python
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
```

- [ ] **Step 6: Run all adapter tests**

Run: `uv run pytest src/paperless_ai/tests/test_vector_store.py -v`
Expected: PASS (all 7 tests).

- [ ] **Step 7: Lint and commit**

```bash
ruff check src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
ruff format src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
git add src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
git commit -m "feat(ai): add LanceDB-backed vector store adapter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Atomic upsert (`upsert_document`)

**Files:**

- Modify: `src/paperless_ai/vector_store.py`
- Test: `src/paperless_ai/tests/test_vector_store.py`

- [ ] **Step 1: Write the failing test for shrink-on-update pruning + single commit**

Append a new class to `src/paperless_ai/tests/test_vector_store.py`:

```python
class TestPaperlessLanceVectorStoreUpsert:
    @pytest.fixture
    def store(self, tmp_path: Path) -> PaperlessLanceVectorStore:
        s = PaperlessLanceVectorStore(uri=str(tmp_path / "idx"))
        s.add(
            [
                _node("1-0", "1", "old0", 0.1),
                _node("1-1", "1", "old1", 0.2),
                _node("1-2", "1", "old2", 0.3),
                _node("2-0", "2", "keep", 0.9),
            ],
        )
        return s

    def test_upsert_prunes_stale_chunks_and_keeps_others(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.upsert_document(
            "1",
            [_node("1-0", "1", "new0", 0.1), _node("1-1", "1", "new1", 0.2)],
        )

        table = store.client.open_table("documents")
        doc1 = sorted(
            r["id"] for r in table.search().where("document_id = '1'").to_list()
        )
        assert doc1 == ["1-0", "1-1"]  # 1-2 pruned
        assert table.count_rows() == 3  # 2 new doc1 + 1 doc2

    def test_upsert_is_single_commit(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        table = store.client.open_table("documents")
        before = table.version
        store.upsert_document("1", [_node("1-0", "1", "new0", 0.1)])
        assert store.client.open_table("documents").version == before + 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest src/paperless_ai/tests/test_vector_store.py::TestPaperlessLanceVectorStoreUpsert -v`
Expected: FAIL with `AttributeError: 'PaperlessLanceVectorStore' object has no attribute 'upsert_document'`.

- [ ] **Step 3: Implement `upsert_document`**

Add to `PaperlessLanceVectorStore` in `src/paperless_ai/vector_store.py`, after `add`:

```python
    def upsert_document(self, document_id: str, nodes: list[BaseNode]) -> list[str]:
        """Atomically replace all stored chunks of ``document_id`` with ``nodes``.

        A single ``merge_insert`` commit: matching node ids are updated, new ids
        inserted, and any existing rows for this document that are not in the new
        set are deleted (``when_not_matched_by_source_delete``). This prunes stale
        trailing chunks when an edit reduces a document's chunk count, with no
        transient empty state for concurrent lock-free readers.
        """
        if not nodes:
            # No indexable content: treat as a removal.
            self.delete(document_id)
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest src/paperless_ai/tests/test_vector_store.py::TestPaperlessLanceVectorStoreUpsert -v`
Expected: PASS (both tests).

- [ ] **Step 5: Lint and commit**

```bash
ruff check src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
ruff format src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
git add src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
git commit -m "feat(ai): atomic upsert_document on the LanceDB store

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: ANN index threshold, scalar index, and compaction

**Files:**

- Modify: `src/paperless_ai/vector_store.py`
- Test: `src/paperless_ai/tests/test_vector_store.py`

- [ ] **Step 1: Write the failing tests**

Append a new class to `src/paperless_ai/tests/test_vector_store.py`:

```python
class TestPaperlessLanceVectorStoreMaintenance:
    @pytest.fixture
    def store(self, tmp_path: Path) -> PaperlessLanceVectorStore:
        return PaperlessLanceVectorStore(uri=str(tmp_path / "idx"))

    def test_maybe_create_ann_index_noop_below_threshold(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add([_node("1-0", "1", "a", 0.1)])
        # Threshold far above row count -> no index attempted, no error.
        store.maybe_create_ann_index(min_rows=1000)
        # Still queryable.
        result = store.query(
            VectorStoreQuery(query_embedding=[0.1] * DIM, similarity_top_k=1),
        )
        assert len(result.nodes) == 1

    def test_maybe_create_ann_index_non_divisible_dim_falls_back(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        # DIM=8 is not divisible by the PQ default sub-vectors; must not raise
        # and must leave the table queryable (IVF_FLAT fallback or skipped).
        for i in range(40):
            store.add([_node(f"1-{i}", "1", f"t{i}", float(i))])
        store.maybe_create_ann_index(min_rows=10)
        result = store.query(
            VectorStoreQuery(query_embedding=[1.0] * DIM, similarity_top_k=3),
        )
        assert len(result.nodes) == 3

    def test_compact_reduces_to_single_version(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        for i in range(5):
            store.add([_node(f"1-{i}", "1", f"t{i}", float(i))])
        assert len(store.client.open_table("documents").list_versions()) > 1
        store.compact(retention_seconds=0)
        assert len(store.client.open_table("documents").list_versions()) == 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest src/paperless_ai/tests/test_vector_store.py::TestPaperlessLanceVectorStoreMaintenance -v`
Expected: FAIL (`maybe_create_ann_index` / `compact` not defined).

- [ ] **Step 3: Implement maintenance methods**

Add to the top of `src/paperless_ai/vector_store.py` (module constants, after `DEFAULT_TABLE_NAME`):

```python
# Below this many chunks, LanceDB's exact (brute-force) search is sufficient and
# faster than building an ANN index (per LanceDB guidance, ~100K vectors).
ANN_INDEX_MIN_ROWS = 100_000
# IVF_PQ default; num_sub_vectors must evenly divide the embedding dimension.
ANN_PQ_SUB_VECTORS = 96
```

Add these methods to `PaperlessLanceVectorStore`:

```python
    def _has_vector_index(self) -> bool:
        try:
            return any(
                "vector" in (getattr(idx, "columns", []) or [])
                for idx in self._table.list_indices()
            )
        except Exception:  # pragma: no cover - older lancedb without list_indices
            return False

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
            if dim % ANN_PQ_SUB_VECTORS == 0:
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
```

> **Note for the implementer:** verify `list_size` is the right attribute for a `pyarrow` fixed-size list on the installed pyarrow (`pa.list_(pa.float32(), 8).list_size == 8`). If the installed pyarrow exposes it differently, adjust the accessor accordingly (this same accessor is used by `vector_dim()` in Task 2).

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest src/paperless_ai/tests/test_vector_store.py::TestPaperlessLanceVectorStoreMaintenance -v`
Expected: PASS (all three).

- [ ] **Step 5: Add the upsert-after-optimize regression test (#3177 guard)**

Append to `TestPaperlessLanceVectorStoreMaintenance`:

```python
    def test_upsert_after_optimize_with_scalar_index(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add(
            [
                _node("1-0", "1", "old0", 0.1),
                _node("1-1", "1", "old1", 0.2),
                _node("1-2", "1", "old2", 0.3),
                _node("2-0", "2", "keep", 0.9),
            ],
        )
        store.ensure_document_id_scalar_index()
        store.compact(retention_seconds=0)

        store.upsert_document("1", [_node("1-0", "1", "new0", 0.1)])

        table = store.client.open_table("documents")
        doc1 = sorted(
            r["id"] for r in table.search().where("document_id = '1'").to_list()
        )
        assert doc1 == ["1-0"]
        assert table.count_rows() == 2
```

- [ ] **Step 6: Run the full maintenance class**

Run: `uv run pytest src/paperless_ai/tests/test_vector_store.py::TestPaperlessLanceVectorStoreMaintenance -v`
Expected: PASS (all four).

- [ ] **Step 7: Lint and commit**

```bash
ruff check src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
ruff format src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
git add src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
git commit -m "feat(ai): ANN index threshold, scalar index, and compaction

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Node identity — set `LlamaDocument.id_` to the document id

**Files:**

- Modify: `src/paperless_ai/indexing.py` (the `build_document_node` function, around `indexing.py:132-149`)
- Test: `src/paperless_ai/tests/test_ai_indexing.py`

- [ ] **Step 1: Write the failing test**

Add to `src/paperless_ai/tests/test_ai_indexing.py`:

```python
@pytest.mark.django_db
def test_build_document_node_sets_ref_doc_id(real_document) -> None:
    nodes = indexing.build_document_node(real_document)
    assert nodes
    for node in nodes:
        assert node.ref_doc_id == str(real_document.id)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest src/paperless_ai/tests/test_ai_indexing.py::test_build_document_node_sets_ref_doc_id -v`
Expected: FAIL — `ref_doc_id` is a random uuid, not `str(real_document.id)`.

- [ ] **Step 3: Set the LlamaDocument id**

In `src/paperless_ai/indexing.py`, in `build_document_node`, change the `LlamaDocument(...)` construction to set `id_`:

```python
    doc = LlamaDocument(
        id_=str(document.id),
        text=text,
        metadata=metadata,
        excluded_embed_metadata_keys=list(metadata.keys()),
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest src/paperless_ai/tests/test_ai_indexing.py::test_build_document_node_sets_ref_doc_id -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/paperless_ai/indexing.py src/paperless_ai/tests/test_ai_indexing.py
git commit -m "feat(ai): tie LlamaDocument id to the paperless document id

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Vector-store factory + load/build in `indexing.py`

**Files:**

- Modify: `src/paperless_ai/indexing.py` — replace `get_or_create_storage_context` and `load_or_build_index`; add `get_vector_store` and `LLM_INDEX_TABLE`.
- Test: `src/paperless_ai/tests/test_ai_indexing.py`

- [ ] **Step 1: Write the failing test**

Add to `src/paperless_ai/tests/test_ai_indexing.py`:

```python
@pytest.mark.django_db
def test_get_vector_store_roundtrip(
    temp_llm_index_dir,
    mock_embed_model,
) -> None:
    from llama_index.core.vector_stores.types import VectorStoreQuery

    from paperless_ai.vector_store import PaperlessLanceVectorStore

    store = indexing.get_vector_store()
    assert isinstance(store, PaperlessLanceVectorStore)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest src/paperless_ai/tests/test_ai_indexing.py::test_get_vector_store_roundtrip -v`
Expected: FAIL — `indexing.get_vector_store` not defined.

- [ ] **Step 3: Add the factory and rewrite the index builder**

In `src/paperless_ai/indexing.py`:

1. Add near the top (after `logger = ...`). **Do not** add a top-level `import` of `vector_store` — only a constant and a `TYPE_CHECKING`-only hint (see the lazy-import constraint):

```python
LLM_INDEX_TABLE = "documents"
```

There is already a `from typing import TYPE_CHECKING` block at the top of `indexing.py`; add the adapter to it for type hints only:

```python
if TYPE_CHECKING:
    from paperless_ai.vector_store import PaperlessLanceVectorStore
```

2. Replace the entire `get_or_create_storage_context(...)` function with (note the **function-local** import of `vector_store` and the string type hint):

```python
def get_vector_store() -> "PaperlessLanceVectorStore":
    """Open (or lazily create) the LanceDB-backed vector store.

    Imports ``vector_store`` lazily so that importing ``indexing`` (which
    ``documents.tasks`` does at module top) never drags in lancedb/llama_index.
    """
    from paperless_ai.vector_store import PaperlessLanceVectorStore

    settings.LLM_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return PaperlessLanceVectorStore(
        uri=str(settings.LLM_INDEX_DIR),
        table_name=LLM_INDEX_TABLE,
    )
```

3. Replace `load_or_build_index(...)` with:

```python
def load_or_build_index(nodes=None):
    """Load the VectorStoreIndex backed by the LanceDB store.

    With ``stores_text=True`` the index runs off the vector store alone — no
    docstore or index store. ``nodes`` is accepted for signature compatibility
    but unused; the store is the source of truth.
    """
    import llama_index.core.settings as llama_settings
    from llama_index.core import VectorStoreIndex

    embed_model = get_embedding_model()
    llama_settings.Settings.embed_model = embed_model
    vector_store = get_vector_store()
    return VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
    )
```

4. Replace `vector_store_file_exists()` (it must use the store before Task 7 relies on it):

```python
def vector_store_file_exists() -> bool:
    """True when the LanceDB table exists."""
    return get_vector_store().table_exists()
```

5. Remove the now-unused imports for `StorageContext`, `SimpleDocumentStore`, `SimpleIndexStore`, and `faiss`. **Keep `shutil`** — it is used by Task 9's migration cleanup.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest src/paperless_ai/tests/test_ai_indexing.py::test_get_vector_store_roundtrip -v`
Expected: PASS.

- [ ] **Step 5: Write the lazy-import guard test**

This guards the hard constraint: importing `documents.tasks` (the light path that management commands traverse) must not pull in any AI library. It runs in a **subprocess** because the pytest process has already imported these libs via other tests.

Create `src/paperless_ai/tests/test_lazy_imports.py`:

```python
import subprocess
import sys


class TestLazyAiImports:
    def test_importing_tasks_does_not_load_ai_libraries(self) -> None:
        code = (
            "import os, django, sys\n"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')\n"
            "django.setup()\n"
            "import documents.tasks  # noqa: F401\n"
            "leaked = [m for m in ('lancedb', 'pyarrow', 'llama_index') "
            "if m in sys.modules]\n"
            "assert not leaked, f'AI libraries leaked into the light path: {leaked}'\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd="src",
        )
        assert result.returncode == 0, result.stdout + result.stderr
```

- [ ] **Step 6: Run the guard test**

Run: `uv run pytest src/paperless_ai/tests/test_lazy_imports.py -v`
Expected: PASS. If it FAILS, find the offending top-level import (`git grep -n "^from llama_index\|^import lancedb\|^import pyarrow\|^from paperless_ai.vector_store" src/paperless_ai src/documents`) and make it function-local.

- [ ] **Step 7: Commit**

```bash
git add src/paperless_ai/indexing.py src/paperless_ai/tests/test_ai_indexing.py src/paperless_ai/tests/test_lazy_imports.py
git commit -m "refactor(ai): build the index from the LanceDB store alone (lazy import)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Rewire add / update / remove / rebuild

**Files:**

- Modify: `src/paperless_ai/indexing.py` — `llm_index_add_or_update_document`, `llm_index_remove_document`, `update_llm_index`; delete `remove_document_docstore_nodes`.
- Test: `src/paperless_ai/tests/test_ai_indexing.py`

- [ ] **Step 1: Write the failing tests (CRUD against the real store)**

Add to `src/paperless_ai/tests/test_ai_indexing.py`:

```python
@pytest.mark.django_db
def test_add_then_remove_document(
    temp_llm_index_dir,
    mock_embed_model,
    real_document,
) -> None:
    indexing.llm_index_add_or_update_document(real_document)
    store = indexing.get_vector_store()
    table = store.client.open_table(indexing.LLM_INDEX_TABLE)
    assert table.count_rows() >= 1

    indexing.llm_index_remove_document(real_document)
    assert store.client.open_table(indexing.LLM_INDEX_TABLE).count_rows() == 0


@pytest.mark.django_db
def test_update_shrinks_chunks_without_orphans(
    temp_llm_index_dir,
    mock_embed_model,
    real_document,
) -> None:
    real_document.content = "word " * 4000  # many chunks
    real_document.save()
    indexing.llm_index_add_or_update_document(real_document)
    store = indexing.get_vector_store()
    big = store.client.open_table(indexing.LLM_INDEX_TABLE).count_rows()

    real_document.content = "short"  # one chunk
    real_document.save()
    indexing.llm_index_add_or_update_document(real_document)

    rows = store.client.open_table(indexing.LLM_INDEX_TABLE).count_rows()
    assert rows < big
    assert rows >= 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest src/paperless_ai/tests/test_ai_indexing.py -k "add_then_remove or shrinks" -v`
Expected: FAIL (current implementation still uses the docstore path).

- [ ] **Step 3: Rewrite the functions**

In `src/paperless_ai/indexing.py` (per the lazy-import constraint, **do not** add a top-level `llama_index` import — `MetadataMode` is imported inside each function that uses it):

1. **Delete** the `remove_document_docstore_nodes(...)` function entirely.

2. Replace `llm_index_add_or_update_document`:

```python
def llm_index_add_or_update_document(document: Document):
    """Add or atomically replace a document's chunks in the LLM index."""
    from llama_index.core.schema import MetadataMode

    new_nodes = build_document_node(document, chunk_size=get_rag_chunk_size())

    embed_model = get_embedding_model()
    for node in new_nodes:
        node.embedding = embed_model.get_text_embedding(
            node.get_content(metadata_mode=MetadataMode.EMBED),
        )

    with FileLock(_index_lock_path()):
        store = get_vector_store()
        store.upsert_document(str(document.id), new_nodes)
        store.ensure_document_id_scalar_index()
```

> Note: `upsert_document` with an empty `new_nodes` list deletes the document (handles the "no indexable content" case the old code logged-and-skipped).

3. Replace `llm_index_remove_document`:

```python
def llm_index_remove_document(document: Document):
    """Remove a document's chunks from the LLM index."""
    with FileLock(_index_lock_path()):
        store = get_vector_store()
        store.delete(str(document.id))
```

4. Rewrite `update_llm_index` — both the rebuild and incremental branches. The rebuild path drops/recreates the table and bulk-inserts; the incremental path upserts changed documents (compare `modified`). Replace the function body with:

```python
def update_llm_index(
    *,
    iter_wrapper: IterWrapper[Document] = identity,
    rebuild=False,
) -> str:
    """Rebuild or incrementally update the LLM index."""
    from llama_index.core.schema import MetadataMode

    documents = Document.objects.all()
    if not documents.exists():
        logger.warning("No documents found to index.")
        if not rebuild and not vector_store_file_exists():
            return "No documents found to index."

    chunk_size = AIConfig().llm_embedding_chunk_size
    embed_model = get_embedding_model()

    with FileLock(_index_lock_path()):
        if rebuild or not vector_store_file_exists():
            (settings.LLM_INDEX_DIR / "meta.json").unlink(missing_ok=True)
            logger.info("Rebuilding LLM index.")
            store = get_vector_store()
            store.drop_table()  # defined in Task 2; bulk-insert into a fresh table
            for document in iter_wrapper(documents):
                nodes = build_document_node(document, chunk_size=chunk_size)
                for node in nodes:
                    node.embedding = embed_model.get_text_embedding(
                        node.get_content(metadata_mode=MetadataMode.EMBED),
                    )
                store.add(nodes)
            msg = "LLM index rebuilt successfully."
        else:
            store = get_vector_store()
            existing = {
                str(row["document_id"]): json.loads(row["node_content"])
                for row in _iter_existing_modified(store)
            }
            changed = 0
            for document in iter_wrapper(documents):
                doc_id = str(document.id)
                node_meta = existing.get(doc_id)
                if node_meta is not None:
                    stored_modified = node_meta.get("modified")
                    if stored_modified == document.modified.isoformat():
                        continue
                nodes = build_document_node(document, chunk_size=chunk_size)
                for node in nodes:
                    node.embedding = embed_model.get_text_embedding(
                        node.get_content(metadata_mode=MetadataMode.EMBED),
                    )
                store.upsert_document(doc_id, nodes)
                changed += 1
            msg = (
                "LLM index updated successfully."
                if changed
                else "No changes detected in LLM index."
            )

        store.ensure_document_id_scalar_index()
        store.maybe_create_ann_index()
        store.compact(retention_seconds=get_llm_index_compaction_retention())
    return msg
```

5. Add the helpers used above near the other small helpers in `indexing.py`:

```python
def _iter_existing_modified(store) -> list[dict]:
    """One representative row per document_id, for modified-time comparison."""
    table_name = LLM_INDEX_TABLE
    if table_name not in store.client.table_names():
        return []
    seen: dict[str, dict] = {}
    for row in store.client.open_table(table_name).search().to_list():
        seen.setdefault(str(row["document_id"]), row)
    return list(seen.values())


def get_llm_index_compaction_retention() -> int:
    """Seconds of MVCC version history to keep during compaction."""
    return 60 * 60  # 1 hour: safe for in-flight readers, reclaims daily
```

6. Ensure `import json` is present at the top of `indexing.py` (it is used by `_iter_existing_modified`).

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest src/paperless_ai/tests/test_ai_indexing.py -k "add_then_remove or shrinks" -v`
Expected: PASS.

- [ ] **Step 5: Run the full indexing test module**

Run: `uv run pytest src/paperless_ai/tests/test_ai_indexing.py -v`
Expected: PASS, except tests that asserted on the old docstore internals — fix or delete those in Task 11.

- [ ] **Step 6: Commit**

```bash
git add src/paperless_ai/indexing.py src/paperless_ai/tests/test_ai_indexing.py
git commit -m "refactor(ai): add/update/remove/rebuild via LanceDB upsert + delete

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: `query_similar_documents` via metadata filter

**Files:**

- Modify: `src/paperless_ai/indexing.py` — `query_similar_documents` (around `indexing.py:394-463`)
- Test: `src/paperless_ai/tests/test_ai_indexing.py`

- [ ] **Step 1: Write the failing test**

Add to `src/paperless_ai/tests/test_ai_indexing.py`:

```python
@pytest.mark.django_db
def test_query_similar_documents_respects_allowed_ids(
    temp_llm_index_dir,
    mock_embed_model,
) -> None:
    from documents.tests.factories import DocumentFactory

    a = DocumentFactory.create(content="alpha shared content here")
    b = DocumentFactory.create(content="beta shared content here")
    c = DocumentFactory.create(content="gamma shared content here")
    for doc in (a, b, c):
        indexing.llm_index_add_or_update_document(doc)

    results = indexing.query_similar_documents(a, document_ids=[b.id])

    assert all(doc.id == b.id for doc in results)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest src/paperless_ai/tests/test_ai_indexing.py::test_query_similar_documents_respects_allowed_ids -v`
Expected: FAIL (current implementation scans the docstore via `index.docstore.docs`, which no longer exists).

- [ ] **Step 3: Rewrite `query_similar_documents`**

Replace the function body in `src/paperless_ai/indexing.py`:

```python
def query_similar_documents(
    document: Document,
    top_k: int = 5,
    document_ids: Iterable[int | str] | None = None,
) -> list[Document]:
    """Return up to ``top_k`` Documents most similar to ``document``."""
    allowed_document_ids = normalize_document_ids(document_ids)
    if allowed_document_ids is not None and not allowed_document_ids:
        return []

    if not vector_store_file_exists():
        queue_llm_index_update_if_needed(
            rebuild=False,
            reason="LLM index not found for similarity query.",
        )
        return []

    from llama_index.core.retrievers import VectorIndexRetriever
    from llama_index.core.vector_stores.types import FilterOperator
    from llama_index.core.vector_stores.types import MetadataFilter
    from llama_index.core.vector_stores.types import MetadataFilters

    index = load_or_build_index()

    filters = None
    if allowed_document_ids is not None:
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="document_id",
                    operator=FilterOperator.IN,
                    value=sorted(allowed_document_ids),
                ),
            ],
        )

    retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=top_k,
        filters=filters,
    )

    config = AIConfig()
    query_text = truncate_content(
        (document.title or "") + "\n" + (document.content or ""),
        chunk_size=config.llm_embedding_chunk_size,
        context_size=config.llm_context_size,
    )
    results = retriever.retrieve(query_text)

    retrieved_document_ids: list[int] = []
    for node in results:
        document_id = node.metadata.get("document_id")
        if document_id is None:
            continue
        normalized = str(document_id)
        if allowed_document_ids is not None and normalized not in allowed_document_ids:
            continue
        try:
            retrieved_document_ids.append(int(normalized))
        except ValueError:
            logger.warning(
                "Skipping LLM index result with invalid document_id %r.",
                document_id,
            )

    return list(Document.objects.filter(pk__in=retrieved_document_ids))
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest src/paperless_ai/tests/test_ai_indexing.py::test_query_similar_documents_respects_allowed_ids -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/paperless_ai/indexing.py src/paperless_ai/tests/test_ai_indexing.py
git commit -m "refactor(ai): query_similar_documents via metadata filter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Dimension guard, migration cleanup, and embedding helper

> Note: the store primitives `table_exists` / `vector_dim` / `drop_table` were added in Task 2, and `vector_store_file_exists()` was rewritten in Task 6. This task adds only the indexing-level migration and dimension-mismatch guard plus the embedding helper they need.

**Files:**

- Modify: `src/paperless_ai/indexing.py` — add migration cleanup + dimension-mismatch guard; wire them into `update_llm_index`.
- Modify: `src/paperless_ai/embedding.py` — add `current_embedding_dim`.
- Test: `src/paperless_ai/tests/test_ai_indexing.py`

- [ ] **Step 1: Write the failing test**

Add to `test_ai_indexing.py`:

```python
@pytest.mark.django_db
def test_migration_wipes_stale_faiss_files(temp_llm_index_dir) -> None:
    stale = temp_llm_index_dir / "default__vector_store.json"
    stale.write_text("{}")
    indexing.migrate_stale_faiss_index()
    assert not stale.exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest src/paperless_ai/tests/test_ai_indexing.py::test_migration_wipes_stale_faiss_files -v`
Expected: FAIL (`indexing.migrate_stale_faiss_index` not defined).

- [ ] **Step 3: Add the embedding helper**

In `src/paperless_ai/embedding.py`, add:

```python
def current_embedding_dim() -> int:
    """Embedding dimension for the configured model (probes if not cached)."""
    return get_embedding_dim()
```

- [ ] **Step 4: Add migration cleanup + dimension guard**

In `src/paperless_ai/indexing.py` (note: `vector_store_file_exists` was already rewritten in Task 6 — do not redefine it):

```python
def migrate_stale_faiss_index() -> None:
    """Remove a pre-LanceDB FAISS index directory so it is rebuilt fresh."""
    stale_marker = settings.LLM_INDEX_DIR / "default__vector_store.json"
    if stale_marker.exists():
        logger.info("Removing stale FAISS LLM index; it will be rebuilt.")
        shutil.rmtree(settings.LLM_INDEX_DIR, ignore_errors=True)
        settings.LLM_INDEX_DIR.mkdir(parents=True, exist_ok=True)


def embedding_dim_mismatch() -> bool:
    """True when the stored table's vector dim differs from the current model."""
    store = get_vector_store()
    stored = store.vector_dim()
    if stored is None:
        return False
    from paperless_ai.embedding import current_embedding_dim

    return stored != current_embedding_dim()
```

Then wire them into `update_llm_index` — add this at the very top of the function body, **before** the `with FileLock(...)` block (the `migrate_stale_faiss_index` call from Task 7's `update_llm_index` rewrite, if already present, should match this; otherwise add it now):

```python
    migrate_stale_faiss_index()
    if not rebuild and vector_store_file_exists() and embedding_dim_mismatch():
        logger.warning("Embedding dimension changed; forcing LLM index rebuild.")
        rebuild = True
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest src/paperless_ai/tests/test_ai_indexing.py::test_migration_wipes_stale_faiss_files -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/paperless_ai/indexing.py src/paperless_ai/embedding.py src/paperless_ai/tests/test_ai_indexing.py
git commit -m "feat(ai): dimension guard and FAISS index migration

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Chat — stock retriever with filters

**Files:**

- Modify: `src/paperless_ai/chat.py` — delete `_get_document_filtered_retriever`; rewrite `_stream_chat_with_documents`.
- Test: `src/paperless_ai/tests/test_chat.py`

- [ ] **Step 1: Read the existing chat tests**

Run: `uv run pytest src/paperless_ai/tests/test_chat.py -v`
Expected: baseline of current passes (note which tests reference `_get_document_filtered_retriever` or FAISS internals; those will be updated).

- [ ] **Step 2: Write/adjust the failing test**

Add to `src/paperless_ai/tests/test_chat.py` (a class-grouped, mocker-based test):

```python
import pytest

from paperless_ai import chat


@pytest.mark.django_db
class TestStreamChatRetrieval:
    def test_no_nodes_yields_no_content_message(
        self,
        temp_llm_index_dir,
        mock_embed_model,
        mocker,
    ) -> None:
        from documents.tests.factories import DocumentFactory

        doc = DocumentFactory.create(content="hello world")
        # Nothing indexed for this document yet.
        out = list(chat.stream_chat_with_documents("question?", [doc]))
        assert chat.CHAT_NO_CONTENT_MESSAGE in out
```

(`mock_embed_model` is the fixture in `test_ai_indexing.py`; move it into `conftest.py` in Step 4 so both modules can use it.)

- [ ] **Step 3: Run to verify it fails or errors on the docstore reach-in**

Run: `uv run pytest src/paperless_ai/tests/test_chat.py::TestStreamChatRetrieval -v`
Expected: FAIL/ERROR — current `_stream_chat_with_documents` reads `index.docstore.docs`, which no longer exists.

- [ ] **Step 4: Move `mock_embed_model` + `FakeEmbedding` to conftest**

Cut the `FakeEmbedding` class and `mock_embed_model` fixture from `test_ai_indexing.py` and paste them into `src/paperless_ai/tests/conftest.py` (so both test modules share them). Leave `temp_llm_index_dir` as-is.

- [ ] **Step 5: Rewrite chat**

In `src/paperless_ai/chat.py`:

1. **Delete** `_get_document_filtered_retriever(...)` entirely.

2. Rewrite `_stream_chat_with_documents`:

```python
def _stream_chat_with_documents(query_str: str, documents: list[Document]):
    from llama_index.core.prompts import PromptTemplate
    from llama_index.core.query_engine import RetrieverQueryEngine
    from llama_index.core.response_synthesizers import get_response_synthesizer
    from llama_index.core.retrievers import VectorIndexRetriever
    from llama_index.core.vector_stores.types import FilterOperator
    from llama_index.core.vector_stores.types import MetadataFilter
    from llama_index.core.vector_stores.types import MetadataFilters

    client = AIClient()
    index = load_or_build_index()

    doc_ids = [str(doc.pk) for doc in documents]
    filters = MetadataFilters(
        filters=[
            MetadataFilter(
                key="document_id",
                operator=FilterOperator.IN,
                value=doc_ids,
            ),
        ],
    )

    # No indexed content for these documents -> bail early.
    if not index.vector_store.get_nodes(filters=filters):
        logger.warning("No nodes found for the given documents.")
        yield CHAT_NO_CONTENT_MESSAGE
        return

    retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=CHAT_RETRIEVER_TOP_K,
        filters=filters,
    )

    top_nodes = retriever.retrieve(query_str)
    if len(top_nodes) == 0:
        logger.warning("Retriever returned no nodes for the given documents.")
        yield CHAT_NO_CONTENT_MESSAGE
        return

    references = _get_document_references(documents, top_nodes)

    prompt_template = PromptTemplate(template=CHAT_PROMPT_TMPL)
    response_synthesizer = get_response_synthesizer(
        llm=client.llm,
        prompt_helper=get_rag_prompt_helper(),
        text_qa_template=prompt_template,
        streaming=True,
    )
    query_engine = RetrieverQueryEngine.from_args(
        retriever=retriever,
        llm=client.llm,
        response_synthesizer=response_synthesizer,
        streaming=True,
    )

    logger.debug("Document chat query: %s", query_str)
    response_stream = query_engine.query(query_str)
    for chunk in response_stream.response_gen:
        yield chunk
        sys.stdout.flush()

    if references:
        yield _format_chat_metadata_trailer(references)
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest src/paperless_ai/tests/test_chat.py -v`
Expected: PASS (update or remove any remaining test that asserted on `DocumentFilteredFaissRetriever` / FAISS internals).

- [ ] **Step 7: Lint and commit**

```bash
ruff check src/paperless_ai/chat.py
ruff format src/paperless_ai/chat.py
git add src/paperless_ai/chat.py src/paperless_ai/tests/test_chat.py src/paperless_ai/tests/conftest.py src/paperless_ai/tests/test_ai_indexing.py
git commit -m "refactor(ai): chat uses a stock filtered retriever

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Sweep remaining FAISS references and fix stale tests

**Files:**

- Modify: `src/paperless_ai/tests/test_ai_indexing.py`, `src/paperless_ai/tests/test_chat.py` (delete/adjust FAISS-internal assertions)
- Modify: any remaining references in `src/paperless_ai/` to `FaissVectorStore`, `SimpleDocumentStore`, `SimpleIndexStore`, `get_or_create_storage_context`, `remove_document_docstore_nodes`.

- [ ] **Step 1: Find remaining references**

Run: `git grep -n "Faiss\|FaissVectorStore\|SimpleDocumentStore\|SimpleIndexStore\|get_or_create_storage_context\|remove_document_docstore_nodes\|_faiss_index\|index_struct.nodes_dict\|docstore.docs" src/`
Expected: matches only in tests to be updated, or none.

- [ ] **Step 2: Update or delete each stale reference**

For each match in a test, replace the docstore/FAISS-internal assertion with the equivalent store-level assertion (`store.client.open_table(...).count_rows()`, `store.query(...)`, `store.get_nodes(...)`). Delete tests that only validated old internals (e.g. a test asserting `remove_document_docstore_nodes` left FAISS vectors behind).

- [ ] **Step 3: Run the whole AI suite**

Run: `uv run pytest src/paperless_ai/ -v`
Expected: PASS, no references to removed symbols.

- [ ] **Step 4: Run the documents task tests that touch the LLM index**

Run: `uv run pytest src/documents/tests/test_tasks.py -k "llm or index" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/paperless_ai/tests/
git commit -m "test(ai): drop FAISS-internal assertions

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Full-suite verification and config docs

**Files:**

- Modify: `paperless.conf.example` (document the unchanged `PAPERLESS_LLM_INDEX_TASK_CRON`; no new vars required — ANN threshold and compaction retention are internal constants).

- [ ] **Step 1: Confirm no new env vars needed**

The ANN threshold (`ANN_INDEX_MIN_ROWS`) and compaction retention (`get_llm_index_compaction_retention`) are internal constants per the spec. No `paperless.conf.example` change is required unless a maintainer wants them tunable. Skip unless requested.

- [ ] **Step 2: Run the full backend AI + tasks suite**

Run: `uv run pytest src/paperless_ai/ src/documents/tests/test_tasks.py -v`
Expected: PASS.

- [ ] **Step 3: Run the app-config API test (it referenced the index status)**

Run: `uv run pytest src/documents/tests/test_api_app_config.py -v`
Expected: PASS.

- [ ] **Step 4: Lint the whole AI package**

Run: `ruff check src/paperless_ai && ruff format --check src/paperless_ai`
Expected: clean.

- [ ] **Step 5: Verify the consume → index path manually (smoke)**

Run a quick smoke per the spec: with `PAPERLESS_LLM_INDEX_ENABLED` on, consume a document and confirm `llm_index_add_or_update_document` writes a row (the test in Task 7 covers this in CI; this is an optional manual smoke).

- [ ] **Step 6: Final commit / branch is ready for PR**

```bash
git add -A
git commit -m "chore(ai): finalize LanceDB vector store migration

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review notes (for the implementer)

- **Lazy imports are a hard requirement** (see the constraint section). After Tasks 6, 7, and 10, the guard test (`test_lazy_imports.py`) must stay green: importing `documents.tasks` must not load `lancedb` / `pyarrow` / `llama_index`. Every `llama_index` symbol in `indexing.py`/`chat.py` (retrievers, filters, `MetadataMode`) and the `vector_store` import itself must be function-local; only `vector_store.py` and test modules import these at top level.

- **`MetadataMode.EMBED`** is passed to `get_content` when embedding in the add/incremental/rebuild paths. Because `build_document_node` sets `excluded_embed_metadata_keys` to every metadata key, `EMBED` yields just the chunk text — exactly what llama-index's own embedding pipeline would feed the model, preserving current behavior. The import `from llama_index.core.schema import MetadataMode` is added in Task 7.
- **`list_size`** is the pyarrow attribute for a fixed-size list's length, used by `vector_dim()` (Task 2) and `maybe_create_ann_index()` (Task 4). Confirm on the installed pyarrow (`pa.list_(pa.float32(), 8).list_size`); adjust the accessor in both places if the version differs.
- **`merge_insert` match key `id` must never get a scalar index** (LanceDB #3177). The only scalar index is on `document_id` (`ensure_document_id_scalar_index`). Task 4's `test_upsert_after_optimize_with_scalar_index` guards this.
- **`embed_model.get_text_embedding`** is called per node in the rebuild/incremental/add paths because we bypass `index.insert_nodes` and write to the store directly. This matches the proven probe. For large rebuilds, consider batching with `get_text_embedding_batch` as a later optimization (YAGNI for now).
- **Compaction retention** defaults to 1 hour (`get_llm_index_compaction_retention`); tests call `compact(retention_seconds=0)` directly to force a single version.
