# sqlite-vec Vector Store Transition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the LanceDB-backed AI vector store with a sqlite-vec-backed one, fixing #12970 (SIGILL on non-AVX2 CPUs) by removing the lancedb dependency entirely.

**Architecture:** `PaperlessSqliteVecVectorStore` keeps the exact `BasePydanticVectorStore` surface of today's `PaperlessLanceVectorStore`, backed by one SQLite file (`LLM_INDEX_DIR/llmindex.db`) holding a vec0 virtual table plus a small `index_meta` key/value table. Writers stay serialized by the existing FileLock; readers run concurrently via WAL. Beta policy: upgrading users re-embed (a leftover Lance directory triggers a forced rebuild and is deleted).

**Tech Stack:** Python/Django, `sqlite-vec==0.1.9` (pinned, see Risk register), stdlib `sqlite3` + `struct`, llama-index `BasePydanticVectorStore`, pytest.

**Spec:** `docs/superpowers/specs/2026-06-10-sqlite-vec-vector-store-design.md` — read it first; every schema and semantics decision below was empirically verified there.

**Included here (user decision):** the `embedding.py:115` TODO (move Filename / Storage Path / Archive Serial Number from embedded body text into `node.metadata`) is Task 5. It changes every document's embedded text, which would normally require a re-embed migration, but this transition forces a full rebuild anyway, so it rides along for free (one user-visible re-embed instead of two).

**Deferred to a second spec (do NOT implement here):** schema-migration machinery (`docs/superpowers/specs/2026-06-10-llmindex-schema-migrations-design.md`, the PR #12968 idea rebuilt for sqlite-vec). It lands after this branch, with an empty migration registry.

---

## Context for an implementer with zero history

**Why sqlite-vec:** issue #12970: lancedb wheels are compiled for `target-cpu=haswell` and SIGILL at import on pre-AVX2 CPUs; upstream will not fix the published wheel. sqlite-vec 0.1.9's wheel contains no baked SIMD (verified under qemu `-cpu Westmere`). Research: `2026-06-10-vector-store-alternatives-research.md`.

**Critical version constraint:** `sqlite-vec==0.1.9` exactly. The 0.1.10-alpha wheels bake `-mavx` (no runtime dispatch) and would reintroduce the crash class. Any future bump requires re-checking wheel build flags (`SELECT vec_debug()`) and ideally re-running the qemu check. An upstream issue about runtime dispatch is being raised separately; do not bump as part of this work.

**Verified vec0 semantics this plan relies on** (all tested against the real 0.1.9 wheel; see spec):

- `document_id` must be a plain metadata column, NOT `PARTITION KEY` (partition keys make `k` apply per partition with `IN` filters; metadata columns give a correct global top-k).
- KNN queries need `WHERE embedding MATCH ? AND k = ?`; `LIMIT` cannot be combined with `k`; results arrive distance-sorted ascending.
- `INSERT OR REPLACE` is broken on vec0 (upstream #259): always DELETE + INSERT inside one transaction.
- Metadata columns reject NULL (upstream #141): every value goes through `str(... or "")`.
- Vectors must be bound as packed float32 BLOBs, never JSON text (locale bug upstream #241).
- Aux column `+node_content` stores the JSON payload; it cannot appear in KNN WHERE clauses (we never do) but is selectable everywhere.
- DELETE never reclaims file space (upstream #54/#220); `compact()` is implemented as a rebuild (create temp table, copy, drop, rename, VACUUM).
- `DROP TABLE` on the vtab drops all its shadow tables.
- Full scans (`SELECT ... FROM vtab` without MATCH) work.
- The cumulative-vs-live bloat ratio is observable as `count(*)` of the `<table>_rowids` shadow table vs the vtab itself.

**Key existing files:**

- `src/paperless_ai/vector_store.py` — the Lance store being replaced (334 lines). Read it fully before Task 2; the new class mirrors its docstrings and surface.
- `src/paperless_ai/indexing.py` — the only construction sites: `get_vector_store()` (read path) and `write_store()` (FileLock-serialized write path). `update_llm_index()` calls `store.ensure_document_id_scalar_index()`, `store.maybe_create_ann_index()`, `store.compact(retention_seconds=...)` — the first two disappear, the third changes signature.
- `src/paperless/settings/__init__.py:99-100` — `LLM_INDEX_DIR = DATA_DIR / "llm_index"`, `LLM_INDEX_LOCK` inside it. Unchanged.
- `src/paperless_ai/tests/conftest.py` — `temp_llm_index_dir` fixture (points `LLM_INDEX_DIR`/`LLM_INDEX_LOCK` at `tmp_path`) and `FakeEmbedding` (dim 384). Reuse both.
- `src/documents/management/commands/document_llmindex.py` — `rebuild|update|compact` subcommands; `compact` calls `paperless_ai.indexing.llm_index_compact()`.

**Project conventions (from CLAUDE.md and memory):**

- All Python through `uv run`; single test file: `cd src && uv run pytest <path> --override-ini="addopts="`.
- pytest style only (no Django TestCase); new tests in dedicated files per subject; no trivial existence tests.
- `rg`/`fd`, not grep/find. Conventional commits, Co-Authored-By trailer for Claude commits.
- Current branch line for this feature is `beta`; branch from it.

---

### Task 1: Branch and dependency swap groundwork

**Files:**

- Modify: `pyproject.toml`, `uv.lock` (via uv only, never by hand)

- [ ] **Step 1: Branch**

```bash
cd /tank/users/trenton/projects/paperless/paperless-ngx
git checkout beta && git pull
git checkout -b feature-sqlitevec-vector-store
```

- [ ] **Step 2: Add sqlite-vec (keep lancedb for now; it goes away in Task 7 after everything is ported)**

```bash
uv add "sqlite-vec==0.1.9"
```

- [ ] **Step 3: Sanity-check the wheel loads and report its build flags**

```bash
cd src && uv run python -c "
import sqlite3, sqlite_vec
db = sqlite3.connect(':memory:')
db.enable_load_extension(True)
sqlite_vec.load(db)
print(db.execute('select vec_version()').fetchone()[0])
print(db.execute('select vec_debug()').fetchone()[0])
"
```

Expected: `v0.1.9` and a `Build flags:` line that does NOT contain `avx`. If it contains `avx`, STOP: the wheel is not the ISA-safe build this whole transition depends on.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Chore(beta): add sqlite-vec 0.1.9 dependency

Pinned exactly: the 0.1.9 wheels carry no baked SIMD flags (safe on
pre-AVX2 CPUs, the point of this migration); the 0.1.10 alphas bake
-mavx and would reintroduce the #12970 crash class.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Rewrite the vector store tests for the new backend

**Files:**

- Rewrite: `src/paperless_ai/tests/test_vector_store.py`

The existing file (417 lines) tests the Lance store. Port its surface to the new class and add the sqlite-vec-specific behaviors. Read the old file first; the helpers below intentionally mirror its node-building helpers so test intent stays comparable in review.

- [ ] **Step 1: Replace the file content**

```python
import json
import sqlite3
from pathlib import Path

import pytest
from llama_index.core.schema import TextNode

from paperless_ai.vector_store import DB_FILENAME
from paperless_ai.vector_store import PaperlessSqliteVecVectorStore

DIM = 16


def make_node(
    node_id: str,
    document_id: str,
    *,
    modified: str = "2026-06-10T00:00:00",
    seed: float = 0.0,
    text: str = "some text",
) -> TextNode:
    node = TextNode(
        id_=node_id,
        text=text,
        metadata={"document_id": document_id, "modified": modified},
    )
    node.relationships = {}
    # ref_doc_id source: llama-index derives it from relationships; for unit
    # tests, setting metadata document_id is what our _row() consumes.
    node.embedding = [seed + i / 100 for i in range(DIM)]
    return node


@pytest.fixture
def store(tmp_path: Path) -> PaperlessSqliteVecVectorStore:
    return PaperlessSqliteVecVectorStore(uri=str(tmp_path))


def _query(store: PaperlessSqliteVecVectorStore, embedding: list[float], top_k: int = 5, filters=None):
    from llama_index.core.vector_stores.types import VectorStoreQuery

    return store.query(
        VectorStoreQuery(
            query_embedding=embedding,
            similarity_top_k=top_k,
            filters=filters,
        ),
    )


def _in_filter(document_ids: list[str]):
    from llama_index.core.vector_stores.types import (
        FilterOperator,
        MetadataFilter,
        MetadataFilters,
    )

    return MetadataFilters(
        filters=[
            MetadataFilter(
                key="document_id", operator=FilterOperator.IN, value=document_ids
            )
        ],
    )


class TestCrud:
    def test_add_then_query_returns_node(self, store) -> None:
        node = make_node("n1", "1")
        assert store.add([node]) == ["n1"]
        result = _query(store, node.embedding, top_k=1)
        assert result.ids == ["n1"]
        assert result.nodes[0].metadata["document_id"] == "1"
        # cosine distance of the identical vector is 0 -> similarity 1
        assert result.similarities[0] == pytest.approx(1.0)

    def test_query_empty_store_returns_empty_no_raise(self, store) -> None:
        result = _query(store, [0.0] * DIM)
        assert result.ids == [] and result.nodes == [] and result.similarities == []

    def test_add_empty_list_is_noop(self, store) -> None:
        assert store.add([]) == []
        assert not store.table_exists()

    def test_delete_removes_all_chunks_of_document(self, store) -> None:
        store.add([make_node("a1", "1"), make_node("a2", "1"), make_node("b1", "2")])
        store.delete("1")
        result = _query(store, [0.0] * DIM, top_k=10)
        assert result.ids == ["b1"]

    def test_query_with_in_filter_scopes_results(self, store) -> None:
        store.add(
            [
                make_node("a1", "1", seed=0.0),
                make_node("b1", "2", seed=1.0),
                make_node("c1", "3", seed=2.0),
            ],
        )
        result = _query(store, [0.0] * DIM, top_k=10, filters=_in_filter(["2", "3"]))
        assert sorted(result.ids) == ["b1", "c1"]

    def test_query_respects_top_k_with_filter(self, store) -> None:
        # k semantics: global top-k even with IN filters (document_id is a
        # metadata column, not a partition key — see design doc).
        store.add(
            [make_node(f"n{i}", str(i % 4), seed=float(i)) for i in range(12)],
        )
        result = _query(
            store, [0.0] * DIM, top_k=3, filters=_in_filter(["0", "1", "2", "3"])
        )
        assert len(result.ids) == 3
        assert result.similarities == sorted(result.similarities, reverse=True)

    def test_get_nodes_filter_and_empty_paths(self, store) -> None:
        assert store.get_nodes(filters=_in_filter(["1"])) == []  # no table yet
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        nodes = store.get_nodes(filters=_in_filter(["1"]))
        assert [n.node_id for n in nodes] == ["a1"]
        assert nodes[0].embedding is not None
        assert store.get_nodes(filters=_in_filter(["999"])) == []

    def test_get_nodes_node_ids_not_implemented(self, store) -> None:
        with pytest.raises(NotImplementedError):
            store.get_nodes(node_ids=["x"])

    def test_fresh_instance_sees_existing_table(self, store, tmp_path: Path) -> None:
        store.add([make_node("a1", "1")])
        reopened = PaperlessSqliteVecVectorStore(uri=str(tmp_path))
        assert reopened.table_exists()
        assert reopened.vector_dim() == DIM
        assert _query(reopened, [0.0] * DIM, top_k=1).ids == ["a1"]

    def test_table_exists_and_drop(self, store) -> None:
        assert not store.table_exists()
        store.add([make_node("a1", "1")])
        assert store.table_exists()
        store.drop_table()
        assert not store.table_exists()
        assert store.vector_dim() is None


class TestUpsert:
    def test_upsert_replaces_and_prunes_stale_chunks(self, store) -> None:
        store.add(
            [make_node("d1c1", "1"), make_node("d1c2", "1"), make_node("d2c1", "2")],
        )
        store.upsert_document("1", [make_node("d1new", "1")])
        result = _query(store, [0.0] * DIM, top_k=10)
        assert sorted(result.ids) == ["d1new", "d2c1"]

    def test_upsert_creates_table_when_missing(self, store) -> None:
        store.upsert_document("1", [make_node("a1", "1")])
        assert _query(store, [0.0] * DIM, top_k=1).ids == ["a1"]

    def test_upsert_empty_nodes_removes_document(self, store) -> None:
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        store.upsert_document("1", [])
        assert _query(store, [0.0] * DIM, top_k=10).ids == ["b1"]

    def test_upsert_is_atomic_for_concurrent_readers(self, store, tmp_path: Path) -> None:
        """A second connection must never observe document 1 half-replaced."""
        store.add([make_node("a1", "1"), make_node("a2", "1")])
        reader = PaperlessSqliteVecVectorStore(uri=str(tmp_path))
        store.upsert_document("1", [make_node("a3", "1")])
        ids = [n.node_id for n in reader.get_nodes(filters=_in_filter(["1"]))]
        assert ids == ["a3"]


class TestMetadataCoercion:
    def test_none_metadata_values_become_empty_strings(self, store) -> None:
        node = make_node("a1", "1")
        node.metadata["modified"] = None
        store.add([node])  # must not raise (vec0 rejects NULL metadata)
        assert store.get_modified_times() == {"1": ""}


class TestModelNameTracking:
    def test_stored_model_name_none_without_table(self, tmp_path: Path) -> None:
        store = PaperlessSqliteVecVectorStore(
            uri=str(tmp_path), embed_model_name="model-a"
        )
        assert store.stored_model_name() is None

    def test_model_name_stored_after_add_and_persists(self, tmp_path: Path) -> None:
        store = PaperlessSqliteVecVectorStore(
            uri=str(tmp_path), embed_model_name="model-a"
        )
        store.add([make_node("a1", "1")])
        assert store.stored_model_name() == "model-a"
        reopened = PaperlessSqliteVecVectorStore(uri=str(tmp_path))
        assert reopened.stored_model_name() == "model-a"

    def test_config_mismatch_semantics(self, tmp_path: Path) -> None:
        store = PaperlessSqliteVecVectorStore(
            uri=str(tmp_path), embed_model_name="model-a"
        )
        assert not store.config_mismatch("anything")  # no table yet
        store.add([make_node("a1", "1")])
        assert not store.config_mismatch("model-a")
        assert store.config_mismatch("model-b")

    def test_config_mismatch_false_when_table_predates_tracking(
        self, tmp_path: Path
    ) -> None:
        store = PaperlessSqliteVecVectorStore(uri=str(tmp_path))  # no model name
        store.add([make_node("a1", "1")])
        assert not store.config_mismatch("model-a")


class TestGetModifiedTimes:
    def test_empty_store_returns_empty_dict(self, store) -> None:
        assert store.get_modified_times() == {}

    def test_returns_one_entry_per_document(self, store) -> None:
        store.add(
            [
                make_node("a1", "1", modified="2026-01-01T00:00:00"),
                make_node("a2", "1", modified="2026-01-01T00:00:00"),
                make_node("b1", "2", modified="2026-02-02T00:00:00"),
            ],
        )
        assert store.get_modified_times() == {
            "1": "2026-01-01T00:00:00",
            "2": "2026-02-02T00:00:00",
        }


class TestCompact:
    def _bloat_ratio(self, store) -> float:
        live = store.client.execute(
            f"SELECT count(*) FROM {store._table_name}"  # noqa: SLF001
        ).fetchone()[0]
        total = store.client.execute(
            f"SELECT count(*) FROM {store._table_name}_rowids"  # noqa: SLF001
        ).fetchone()[0]
        return total / max(live, 1)

    def _churn(self, store, cycles: int) -> None:
        for i in range(cycles):
            store.upsert_document(
                "1", [make_node(f"gen{i}-{j}", "1", seed=float(j)) for j in range(20)]
            )

    def test_compact_noop_below_threshold(self, store) -> None:
        store.add([make_node("a1", "1")])
        store.compact()
        assert _query(store, [0.0] * DIM, top_k=1).ids == ["a1"]

    def test_force_compact_preserves_rows_and_metadata(self, store) -> None:
        store.add([make_node("a1", "1"), make_node("b1", "2", seed=3.0)])
        self._churn(store, 5)
        before = {
            n.node_id: n.metadata for n in store.get_nodes(filters=_in_filter(["1", "2"]))
        }
        store.compact(force=True)
        after = {
            n.node_id: n.metadata for n in store.get_nodes(filters=_in_filter(["1", "2"]))
        }
        assert after == before
        assert self._bloat_ratio(store) == pytest.approx(1.0)
        # store remains fully usable after the rebuild
        store.upsert_document("3", [make_node("c1", "3", seed=9.0)])
        assert "c1" in _query(store, [9.0] * DIM, top_k=1).ids

    def test_auto_compact_triggers_on_churn(self, store) -> None:
        store.add([make_node(f"s{j}", "1", seed=float(j)) for j in range(20)])
        self._churn(store, 5)
        assert self._bloat_ratio(store) > 2
        store.compact()
        assert self._bloat_ratio(store) == pytest.approx(1.0)

    def test_compact_on_missing_table_is_noop(self, store) -> None:
        store.compact()
        store.compact(force=True)


class TestDbFile:
    def test_single_db_file_in_index_dir(self, store, tmp_path: Path) -> None:
        store.add([make_node("a1", "1")])
        assert (tmp_path / DB_FILENAME).exists()

    def test_wal_mode_enabled(self, store) -> None:
        assert (
            store.client.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        )
```

- [ ] **Step 2: Run to verify the import fails (class does not exist yet)**

```bash
cd src && uv run pytest paperless_ai/tests/test_vector_store.py --override-ini="addopts=" 2>&1 | tail -3
```

Expected: collection error, `ImportError: cannot import name 'PaperlessSqliteVecVectorStore'`.

- [ ] **Step 3: Commit**

```bash
git add src/paperless_ai/tests/test_vector_store.py
git commit -m "Test(beta): port vector store tests to sqlite-vec backend

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Implement PaperlessSqliteVecVectorStore

**Files:**

- Modify: `src/paperless_ai/vector_store.py`
- Create: `src/bench_vector_store.py`

---

#### Phase A: Benchmark coexistence

Add `PaperlessSqliteVecVectorStore` alongside the existing Lance class so both can be benchmarked head-to-head before the Lance class is removed. No commit is made in Phase A; the final commit (Phase B Step 6) captures the clean state.

- [ ] **Step 1: Add `PaperlessSqliteVecVectorStore` alongside the existing Lance class**

Add these imports to the top of `src/paperless_ai/vector_store.py` (insert after the existing `from llama_index...` block, before `logger = ...`):

```python
import sqlite3
import struct
from collections.abc import Iterator
from contextlib import contextmanager

import sqlite_vec
```

Then append the content from Phase B Step 4 -- everything from `DB_FILENAME = "llmindex.db"` through the end of `PaperlessSqliteVecVectorStore` -- to the **bottom** of the existing file. When appending, make one change: rename the appended `_build_where` to `_build_sqlite_where` and update its two call sites inside `PaperlessSqliteVecVectorStore` (`get_nodes` and `query` methods). This avoids shadowing the existing Lance `_build_where`. All other names (`DB_FILENAME`, `COMPACT_BLOAT_RATIO`, `_FILTER_COLUMNS`, `_pack`, `_unpack`) are safe to append verbatim.

Verify:

```bash
rg -n "^class Paperless" src/paperless_ai/vector_store.py
# Expected: PaperlessLanceVectorStore on one line, PaperlessSqliteVecVectorStore on another
```

- [ ] **Step 2: Write `src/bench_vector_store.py`**

```python
#!/usr/bin/env python3
"""Head-to-head benchmark: PaperlessLanceVectorStore vs PaperlessSqliteVecVectorStore.

Run from src/ with:
    uv run python bench_vector_store.py [OPTIONS]

Phase 1 (skipped if bench_data.pkl already exists): generate fake documents with
Faker and embed chunks via Ollama; save to disk for reuse.
Phase 2: benchmark both stores against identical data and print a comparison table.

Requires both classes to coexist in paperless_ai.vector_store (Task 3 Phase A).
After Phase B replaces the file, the Lance import fails gracefully and only the
sqlite-vec half runs.
"""
from __future__ import annotations

import argparse
import pickle
import statistics
import tempfile
import time
import uuid
from pathlib import Path

import httpx
from faker import Faker
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
    VectorStoreQuery,
)

try:
    from paperless_ai.vector_store import PaperlessLanceVectorStore

    _LANCE_OK = True
except ImportError:
    _LANCE_OK = False

from paperless_ai.vector_store import PaperlessSqliteVecVectorStore

DEFAULT_OLLAMA_URL = "http://192.168.1.87:11434"
DEFAULT_EMBED_MODEL = "qwen3-embedding:4b"
DEFAULT_DATA_FILE = "bench_data.pkl"
DEFAULT_N_DOCS = 2000
DEFAULT_CHUNKS_PER_DOC = 3
DEFAULT_QUERY_ITERS = 50
_BATCH = 32


def _embed(texts: list[str], url: str, model: str) -> list[list[float]]:
    r = httpx.post(
        f"{url}/api/embed",
        json={"model": model, "input": texts},
        timeout=120.0,
    )
    r.raise_for_status()
    return r.json()["embeddings"]


def warm_up(url: str, model: str) -> int:
    """Fire one embed call to load the model into GPU; return embedding dim."""
    print(f"Warming up {model}...", end=" ", flush=True)
    dim = len(_embed(["warm"], url, model)[0])
    print(f"dim={dim}")
    return dim


def generate_and_save(
    n_docs: int,
    chunks_per_doc: int,
    url: str,
    model: str,
    out: str,
) -> list[dict]:
    fake = Faker()
    Faker.seed(42)
    print(f"Generating {n_docs} docs ({chunks_per_doc} chunks each)...")
    docs = []
    for i in range(n_docs):
        body = "\n\n".join(fake.paragraph(nb_sentences=8) for _ in range(3))
        clen = max(1, len(body) // chunks_per_doc)
        chunks = []
        for j in range(chunks_per_doc):
            s = j * clen
            e = s + clen if j < chunks_per_doc - 1 else len(body)
            chunks.append({"node_id": str(uuid.uuid4()), "text": body[s:e], "embedding": None})
        docs.append({
            "doc_id": str(i + 1),
            "title": fake.catch_phrase(),
            "modified": fake.date_time_this_decade().isoformat(),
            "chunks": chunks,
        })

    all_texts = [c["text"] for d in docs for c in d["chunks"]]
    print(f"Embedding {len(all_texts)} chunks in batches of {_BATCH}...")
    embeddings: list[list[float]] = []
    for i in range(0, len(all_texts), _BATCH):
        embeddings.extend(_embed(all_texts[i : i + _BATCH], url, model))
        print(f"  {min(i + _BATCH, len(all_texts))}/{len(all_texts)}", end="\r", flush=True)
    print()

    idx = 0
    for d in docs:
        for c in d["chunks"]:
            c["embedding"] = embeddings[idx]
            idx += 1

    with open(out, "wb") as f:
        pickle.dump(docs, f)
    print(f"Saved to {out}")
    return docs


def _build_nodes(docs: list[dict]) -> list[TextNode]:
    nodes = []
    for d in docs:
        for c in d["chunks"]:
            n = TextNode(
                id_=c["node_id"],
                text=c["text"],
                metadata={"document_id": d["doc_id"], "modified": d["modified"]},
            )
            n.relationships = {}
            n.embedding = c["embedding"]
            nodes.append(n)
    return nodes


def _in_filter(ids: list[str]) -> MetadataFilters:
    return MetadataFilters(
        filters=[MetadataFilter(key="document_id", operator=FilterOperator.IN, value=ids)]
    )


def _dir_bytes(path: str) -> int:
    return sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())


def _sqlite_bytes(uri: str) -> int:
    p = Path(uri) / "llmindex.db"
    return p.stat().st_size if p.exists() else 0


def run_bench(
    store,
    nodes: list[TextNode],
    docs: list[dict],
    q_iters: int,
    is_lance: bool,
) -> dict:
    doc_ids = [d["doc_id"] for d in docs]
    filter_ids = doc_ids[: max(1, len(doc_ids) // 5)]
    q_vecs = [nodes[i * 10 % len(nodes)].embedding for i in range(q_iters)]
    by_doc: dict[str, list[TextNode]] = {}
    for n in nodes:
        by_doc.setdefault(n.metadata["document_id"], []).append(n)
    uri = store._uri

    # insert
    t0 = time.perf_counter()
    store.add(list(nodes))
    r: dict = {"insert": time.perf_counter() - t0}

    # query plain
    times = []
    for emb in q_vecs:
        t0 = time.perf_counter()
        store.query(VectorStoreQuery(query_embedding=emb, similarity_top_k=10))
        times.append(time.perf_counter() - t0)
    r["qp50"] = statistics.median(times)
    r["qp95"] = sorted(times)[int(len(times) * 0.95)]

    # query filtered
    times = []
    flt = _in_filter(filter_ids)
    for emb in q_vecs:
        t0 = time.perf_counter()
        store.query(VectorStoreQuery(query_embedding=emb, similarity_top_k=10, filters=flt))
        times.append(time.perf_counter() - t0)
    r["qfp50"] = statistics.median(times)
    r["qfp95"] = sorted(times)[int(len(times) * 0.95)]

    # get_modified_times
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        store.get_modified_times()
        times.append(time.perf_counter() - t0)
    r["gmt_p50"] = statistics.median(times)

    # upsert (fresh node IDs, same embeddings)
    times = []
    for doc in docs[:q_iters]:
        orig = by_doc.get(doc["doc_id"], [])
        if not orig:
            continue
        fresh = []
        for o in orig:
            fn = TextNode(
                id_=str(uuid.uuid4()),
                text=o.text,
                metadata=o.metadata.copy(),
            )
            fn.relationships = {}
            fn.embedding = o.embedding
            fresh.append(fn)
        t0 = time.perf_counter()
        store.upsert_document(doc["doc_id"], fresh)
        times.append(time.perf_counter() - t0)
    r["up50"] = statistics.median(times) if times else 0.0
    r["up95"] = sorted(times)[int(len(times) * 0.95)] if times else 0.0

    r["size_pre"] = _dir_bytes(uri) if is_lance else _sqlite_bytes(uri)

    # compact
    t0 = time.perf_counter()
    if is_lance:
        store.compact(retention_seconds=0)
    else:
        store.compact(force=True)
    r["compact"] = time.perf_counter() - t0

    r["size_post"] = _dir_bytes(uri) if is_lance else _sqlite_bytes(uri)
    return r


def _pct(lv: float | None, sv: float) -> str:
    if lv is None or lv == 0:
        return "N/A"
    p = (sv - lv) / lv * 100
    return f"{'+' if p > 0 else ''}{p:.0f}%"


def print_results(nodes: list[TextNode], q_iters: int, lance: dict | None, sq: dict) -> None:
    W = 30
    n, dim = len(nodes), len(nodes[0].embedding)
    print(f"\n=== Vector Store Benchmark ===")
    print(f"Nodes: {n} | Dim: {dim} | Query iters: {q_iters}\n")
    lh = "LanceDB" if lance else "LanceDB (N/A)"
    print(f"{'Operation':<{W}} {lh:<22} {'sqlite-vec':<22} {'Delta'}")
    print("-" * (W + 66))

    def _s(v: float) -> str:
        return f"{v:.3f}s"

    def _ms(v: float) -> str:
        return f"{v * 1000:.1f}ms"

    def _mb(v: float) -> str:
        return f"{v / 1e6:.1f} MB"

    def row(label: str, lv: float | None, sv: float, fmt) -> None:
        ls = fmt(lv) if lv is not None else "N/A"
        print(f"{label:<{W}} {ls:<22} {fmt(sv):<22} {_pct(lv, sv)}")

    def row2(label: str, lv1: float | None, lv2: float | None, sv1: float, sv2: float) -> None:
        def ms_pair(a: float, b: float) -> str:
            return f"{_ms(a)} / {_ms(b)}"
        ls = ms_pair(lv1, lv2) if lv1 is not None else "N/A"
        print(f"{label:<{W}} {ls:<22} {ms_pair(sv1, sv2):<22} {_pct(lv1, sv1)}")

    L = lance
    row(f"insert ({n} nodes)", L["insert"] if L else None, sq["insert"], _s)
    row2("query plain p50/p95",
         L["qp50"] if L else None, L["qp95"] if L else None, sq["qp50"], sq["qp95"])
    row2("query filtered p50/p95",
         L["qfp50"] if L else None, L["qfp95"] if L else None, sq["qfp50"], sq["qfp95"])
    row("get_modified_times p50", L["gmt_p50"] if L else None, sq["gmt_p50"], _ms)
    row2("upsert p50/p95",
         L["up50"] if L else None, L["up95"] if L else None, sq["up50"], sq["up95"])
    row("compact", L["compact"] if L else None, sq["compact"], _s)
    row("file size pre-compact", L["size_pre"] if L else None, sq["size_pre"], _mb)
    row("file size post-compact", L["size_post"] if L else None, sq["size_post"], _mb)


def main() -> None:
    ap = argparse.ArgumentParser(description="Vector store head-to-head benchmark")
    ap.add_argument("--n-docs", type=int, default=DEFAULT_N_DOCS)
    ap.add_argument("--chunks-per-doc", type=int, default=DEFAULT_CHUNKS_PER_DOC)
    ap.add_argument("--data-file", default=DEFAULT_DATA_FILE)
    ap.add_argument("--regenerate", action="store_true")
    ap.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    ap.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL)
    ap.add_argument("--query-iters", type=int, default=DEFAULT_QUERY_ITERS)
    args = ap.parse_args()

    warm_up(args.ollama_url, args.embed_model)

    data_path = Path(args.data_file)
    if args.regenerate or not data_path.exists():
        docs = generate_and_save(
            args.n_docs, args.chunks_per_doc, args.ollama_url, args.embed_model, args.data_file
        )
    else:
        print(f"Loading {args.data_file}...")
        with open(data_path, "rb") as f:
            docs = pickle.load(f)
        print(f"Loaded {len(docs)} docs ({sum(len(d['chunks']) for d in docs)} nodes)")

    all_nodes = _build_nodes(docs)

    lance_r = None
    if _LANCE_OK:
        print("\nBenchmarking LanceDB...")
        with tempfile.TemporaryDirectory() as d:
            store = PaperlessLanceVectorStore(uri=d)
            lance_r = run_bench(store, all_nodes, docs, args.query_iters, is_lance=True)
    else:
        print("Skipping LanceDB (PaperlessLanceVectorStore not importable).")

    print("\nBenchmarking sqlite-vec...")
    with tempfile.TemporaryDirectory() as d:
        store = PaperlessSqliteVecVectorStore(uri=d)
        sqlite_r = run_bench(store, all_nodes, docs, args.query_iters, is_lance=False)

    print_results(all_nodes, args.query_iters, lance_r, sqlite_r)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the benchmark and save output**

```bash
cd src && uv run python bench_vector_store.py 2>&1 | tee bench_results.txt
```

First run: Faker generates docs and embeds ~6000 chunks via Ollama (a few minutes). The warm-up call fires first so model-load time does not skew timings. Results are written to `bench_results.txt`.

Expected: both stores complete all operations without error; a comparison table is printed. A regression is any sqlite-vec operation significantly (>2x) slower than LanceDB. Note that `compact` differs in character (Lance uses MVCC cleanup vs. sqlite-vec full table rebuild) and is not a direct apples-to-apples comparison.

---

#### Phase B: Final implementation

- [ ] **Step 4: Replace the file content**

```python
import json
import logging
import sqlite3
import struct
from collections.abc import Iterator
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import sqlite_vec
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

DB_FILENAME = "llmindex.db"
DEFAULT_TABLE_NAME = "documents"

# compact(): rebuild when the cumulative rowid count exceeds this multiple of
# the live row count. DELETEs on vec0 tables never reclaim space (upstream
# asg017/sqlite-vec#54), so per-document re-index churn grows the file until
# a rebuild copies the live rows into a fresh table.
COMPACT_BLOAT_RATIO = 2.0

# Filterable vec0 metadata columns. _build_where() only ever receives filter
# keys we construct ourselves, but allowlisting keeps SQL identifiers safe by
# construction.
_FILTER_COLUMNS = frozenset({"document_id", "modified"})


def _pack(embedding: Sequence[float]) -> bytes:
    return struct.pack(f"{len(embedding)}f", *embedding)


def _unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"{len(blob) // 4}f", blob))


def _build_where(filters: MetadataFilters | None) -> tuple[str, list[str]]:
    """Translate the EQ / IN filters we use into a parameterized SQL clause
    on vec0 metadata columns. Returns ("", []) when there is nothing to filter.
    """
    if filters is None or not filters.filters:
        return "", []
    clauses: list[str] = []
    params: list[str] = []
    for f in filters.filters:
        if f.key not in _FILTER_COLUMNS:  # pragma: no cover - we build the keys
            raise NotImplementedError(f"Unsupported filter column: {f.key}")
        if f.operator == FilterOperator.IN:
            values = [str(v) for v in f.value]
            if not values:
                clauses.append("1 = 0")
                continue
            placeholders = ",".join("?" for _ in values)
            clauses.append(f"{f.key} IN ({placeholders})")
            params.extend(values)
        elif f.operator == FilterOperator.EQ:
            clauses.append(f"{f.key} = ?")
            params.append(str(f.value))
        else:  # pragma: no cover - we only ever build EQ/IN filters
            raise NotImplementedError(f"Unsupported filter operator: {f.operator}")
    joiner = " OR " if filters.condition == FilterCondition.OR else " AND "
    return "(" + joiner.join(clauses) + ")", params


class PaperlessSqliteVecVectorStore(BasePydanticVectorStore):
    """A llama-index vector store backed by a sqlite-vec vec0 table.

    Stores one row per node: the node id (TEXT primary key), its document id
    (metadata column, used for EQ/IN filtering and per-document delete), the
    document's modified timestamp, the embedding (float32, cosine metric), and
    the serialized node (text + metadata) as JSON in an auxiliary column.
    ``stores_text`` lets llama-index run off this store alone, with no
    separate docstore or index store.

    Everything lives in one SQLite database file (``DB_FILENAME``) inside the
    directory given as ``uri`` (kept as a directory for compatibility with the
    previous LanceDB layout). WAL mode allows readers in other processes to
    proceed while the (FileLock-serialized) writer holds a transaction.

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
    _embed_model_name: str | None = PrivateAttr()
    _conn: Any = PrivateAttr()

    def __init__(
        self,
        uri: str,
        table_name: str = DEFAULT_TABLE_NAME,
        embed_model_name: str | None = None,
    ) -> None:
        super().__init__(stores_text=True, flat_metadata=False)
        self._uri = uri
        self._table_name = table_name
        self._embed_model_name = embed_model_name
        self._conn = sqlite3.connect(
            str(Path(uri) / DB_FILENAME),
            timeout=30,
            isolation_level=None,  # autocommit; explicit transactions below
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.enable_load_extension(True)
        sqlite_vec.load(self._conn)
        self._conn.enable_load_extension(False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT)",
        )

    @property
    def client(self) -> Any:
        return self._conn

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    def _meta_get(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM index_meta WHERE key = ?",
            (key,),
        ).fetchone()
        return row["value"] if row else None

    def _meta_set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO index_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def table_exists(self) -> bool:
        return (
            self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (self._table_name,),
            ).fetchone()
            is not None
        )

    def vector_dim(self) -> int | None:
        if not self.table_exists():
            return None
        value = self._meta_get("dim")
        return int(value) if value else None

    def drop_table(self) -> None:
        self._conn.execute(f"DROP TABLE IF EXISTS {self._table_name}")
        self._conn.execute("DELETE FROM index_meta")

    def stored_model_name(self) -> str | None:
        """Return the embedding model name recorded at table creation, or None."""
        if not self.table_exists():
            return None
        return self._meta_get("embed_model")

    def config_mismatch(self, model_name: str) -> bool:
        """True when the stored model name differs from ``model_name``.

        Returns False when no table exists or when the table predates
        model-name tracking — conservative default avoids spurious rebuilds.
        """
        stored = self.stored_model_name()
        if stored is None:
            return False
        return stored != model_name

    def _create_table(self, dim: int) -> None:
        # document_id is deliberately a metadata column, NOT a partition key:
        # partition keys change KNN `k` to per-partition semantics under IN
        # filters (asg017/sqlite-vec#142); metadata columns give a correct
        # global top-k.
        self._conn.execute(
            f"""CREATE VIRTUAL TABLE {self._table_name} USING vec0(
                id TEXT PRIMARY KEY,
                document_id TEXT,
                modified TEXT,
                +node_content TEXT,
                embedding float[{dim}] distance_metric=cosine
            )""",
        )
        self._meta_set("dim", str(dim))
        if self._embed_model_name:
            self._meta_set("embed_model", self._embed_model_name)

    def _ensure_table(self, dim: int) -> None:
        if not self.table_exists():
            self._create_table(dim)

    def _row(self, node: BaseNode) -> tuple[str, str, str, str, bytes]:
        meta = node_to_metadata_dict(
            node,
            remove_text=False,
            flat_metadata=self.flat_metadata,
        )
        # vec0 metadata columns reject NULL (asg017/sqlite-vec#141): coerce
        # every value to a string, with "" as the absent sentinel.
        document_id = node.ref_doc_id or node.metadata.get("document_id")
        return (
            node.node_id,
            str(document_id or ""),
            str(node.metadata.get("modified") or ""),
            json.dumps(meta),
            _pack(node.get_embedding()),
        )

    _INSERT = "INSERT INTO {t} (id, document_id, modified, node_content, embedding) VALUES (?, ?, ?, ?, ?)"

    def add(self, nodes: Sequence[BaseNode], **add_kwargs: Any) -> list[str]:
        if not nodes:
            return []
        rows = [self._row(node) for node in nodes]
        with self._transaction():
            self._ensure_table(len(nodes[0].get_embedding()))
            self._conn.executemany(self._INSERT.format(t=self._table_name), rows)
        return [node.node_id for node in nodes]

    def upsert_document(self, document_id: str, nodes: list[BaseNode]) -> list[str]:
        """Atomically replace all stored chunks of ``document_id`` with ``nodes``.

        One transaction deletes the document's existing rows and inserts the
        new set (vec0's INSERT OR REPLACE is broken upstream, #259, so
        delete+insert it is). WAL readers in other processes see either the
        old or the new chunk set, never a partial state.
        """
        rows = [self._row(node) for node in nodes]
        with self._transaction():
            if nodes:
                self._ensure_table(len(nodes[0].get_embedding()))
            if self.table_exists():
                self._conn.execute(
                    f"DELETE FROM {self._table_name} WHERE document_id = ?",
                    (str(document_id),),
                )
            if rows:
                self._conn.executemany(self._INSERT.format(t=self._table_name), rows)
        return [node.node_id for node in nodes]

    def delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        if self.table_exists():
            with self._transaction():
                self._conn.execute(
                    f"DELETE FROM {self._table_name} WHERE document_id = ?",
                    (str(ref_doc_id),),
                )

    def _rows_to_nodes(self, rows: list[sqlite3.Row]) -> list[BaseNode]:
        nodes: list[BaseNode] = []
        for row in rows:
            node = metadata_dict_to_node(json.loads(row["node_content"]))
            node.embedding = _unpack(row["embedding"])
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
                "PaperlessSqliteVecVectorStore does not support node_ids lookup",
            )
        if not self.table_exists():
            return []
        where, params = _build_where(filters)
        sql = f"SELECT node_content, embedding FROM {self._table_name}"
        if where:
            sql += f" WHERE {where}"
        return self._rows_to_nodes(self._conn.execute(sql, params).fetchall())

    def query(
        self,
        query: VectorStoreQuery,
        **kwargs: Any,
    ) -> VectorStoreQueryResult:
        if not self.table_exists():
            return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])
        top_k = query.similarity_top_k if query.similarity_top_k is not None else 10
        where, params = _build_where(query.filters)
        sql = (
            f"SELECT id, node_content, embedding, distance FROM {self._table_name} "
            "WHERE embedding MATCH ? AND k = ?"
        )
        if where:
            sql += f" AND {where}"
        rows = self._conn.execute(
            sql,
            [_pack(query.query_embedding), top_k, *params],
        ).fetchall()
        # vec0 returns rows distance-sorted ascending; slice defensively in
        # case future schema changes alter k semantics (e.g. partition keys
        # return k rows per partition).
        rows = rows[:top_k]
        nodes = self._rows_to_nodes(rows)
        # Cosine distance in [0, 2]; map to a descending similarity.
        sims = [1.0 - float(row["distance"]) for row in rows]
        ids = [row["id"] for row in rows]
        return VectorStoreQueryResult(nodes=nodes, similarities=sims, ids=ids)

    def get_modified_times(self) -> dict[str, str]:
        """Return {document_id: stored_modified_isoformat} for all indexed documents.

        All chunks of a document share the same ``modified`` value, so the
        first row seen per document is sufficient.
        """
        if not self.table_exists():
            return {}
        result: dict[str, str] = {}
        for row in self._conn.execute(
            f"SELECT document_id, modified FROM {self._table_name}",
        ):
            doc_id = str(row["document_id"])
            if doc_id not in result:
                result[doc_id] = str(row["modified"] or "")
        return result

    def compact(self, *, force: bool = False) -> None:
        """Rebuild the table to reclaim space left behind by DELETEs.

        vec0 DELETE only invalidates rows; the vector data stays in the file
        forever (asg017/sqlite-vec#54), and per-document re-indexing is a
        delete+insert. When the cumulative rowid count exceeds
        ``COMPACT_BLOAT_RATIO`` x the live row count (or when forced), copy
        the live rows into a fresh table, swap it in, and VACUUM.
        """
        if not self.table_exists():
            return
        live = self._conn.execute(
            f"SELECT count(*) FROM {self._table_name}",
        ).fetchone()[0]
        total = self._conn.execute(
            f"SELECT count(*) FROM {self._table_name}_rowids",
        ).fetchone()[0]
        if not force and total <= max(live, 1) * COMPACT_BLOAT_RATIO:
            return
        dim = self.vector_dim()
        if dim is None:  # pragma: no cover - dim is written at creation
            logger.warning("Skipping compact: no stored vector dimension")
            return
        logger.info(
            "Compacting LLM index (%d live rows, %d cumulative)",
            live,
            total,
        )
        original, tmp = self._table_name, f"{self._table_name}_compact"
        with self._transaction():
            self._conn.execute(f"DROP TABLE IF EXISTS {tmp}")
            self._table_name = tmp
            try:
                self._create_table(dim)
            finally:
                self._table_name = original
            self._conn.execute(
                f"INSERT INTO {tmp} (id, document_id, modified, node_content, embedding) "
                f"SELECT id, document_id, modified, node_content, embedding FROM {original}",
            )
            self._conn.execute(f"DROP TABLE {original}")
            self._conn.execute(f"ALTER TABLE {tmp} RENAME TO {original}")
        self._conn.execute("VACUUM")
```

- [ ] **Step 5: Run the vector store tests**

```bash
cd src && uv run pytest paperless_ai/tests/test_vector_store.py --override-ini="addopts=" 2>&1 | tail -5
```

Expected: all PASS. Debugging notes for likely failures:

- `OperationalError: no such module: vec0` -> the extension did not load; check `sqlite_vec.load` ordering against `enable_load_extension`.
- `UNIQUE constraint failed on t primary key` in upsert tests -> the DELETE did not run inside the same transaction before the INSERT.
- A failure in `test_force_compact_preserves_rows_and_metadata` around `ALTER TABLE ... RENAME` would mean vec0 0.1.9's rename path misbehaves for this schema (the 0.1.10 alphas fixed rename bugs for non-FLAT tables; FLAT tables are expected to work). Fallback design if that happens: rebuild into a brand-new database file (`llmindex.db.compact`), checkpoint, `os.replace` onto `llmindex.db`, then reconnect; implement that instead and keep the same tests.

- [ ] **Step 6: Commit**

```bash
git add src/paperless_ai/vector_store.py src/bench_vector_store.py
git commit -m "Enhancement(beta): switch AI vector store from LanceDB to sqlite-vec

Fixes the non-AVX2 SIGILL class (#12970) at the root: lancedb is no
longer imported. sqlite-vec 0.1.9 wheels carry no baked SIMD, vec0
metadata columns give parameterized EQ/IN filtering, WAL preserves the
lock-free-reader model, and compact() rebuilds the table because vec0
DELETEs never reclaim space.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Switch indexing.py to the new store

**Files:**

- Modify: `src/paperless_ai/indexing.py`

- [ ] **Step 1: Update imports/type hints and construction sites**

In `src/paperless_ai/indexing.py`, replace every `PaperlessLanceVectorStore` with `PaperlessSqliteVecVectorStore` (TYPE_CHECKING import at ~line 23, `get_vector_store()` body and return annotation at ~lines 65-72, `write_store()` body at ~lines 86-94). The `uri=str(settings.LLM_INDEX_DIR)` argument and `LLM_INDEX_TABLE = "documents"` stay as they are.

- [ ] **Step 2: Add the legacy-Lance cleanup helper**

Add `import shutil` to the imports, then below `get_vector_store()`:

```python
def _cleanup_legacy_lance_index() -> bool:
    """Delete a LanceDB index left by a pre-sqlite-vec version, if present.

    Beta transition policy: no cross-store conversion; the caller forces a
    full rebuild (re-embed) instead. Returns True when leftovers were found.
    """
    legacy_table = settings.LLM_INDEX_DIR / f"{LLM_INDEX_TABLE}.lance"
    found = legacy_table.exists()
    if found:
        shutil.rmtree(legacy_table, ignore_errors=True)
    # faiss-era metadata file, removed on the same occasion
    (settings.LLM_INDEX_DIR / "meta.json").unlink(missing_ok=True)
    return found
```

- [ ] **Step 3: Wire it into update_llm_index and drop the Lance-only maintenance calls**

In `update_llm_index()`:

1. At the very top of the function body (before the `documents = ...` line), add:

```python
    if _cleanup_legacy_lance_index():
        logger.warning(
            "Found a LanceDB index from a previous version; forcing a full rebuild.",
        )
        rebuild = True
```

2. In the rebuild branch, delete the now-redundant line `(settings.LLM_INDEX_DIR / "meta.json").unlink(missing_ok=True)` (the helper handles it).

3. At the end of the `with write_store(...)` block, replace:

```python
        store.ensure_document_id_scalar_index()
        store.maybe_create_ann_index()
        store.compact(retention_seconds=60 * 60)  # 1 hour: safe for in-flight readers
```

with:

```python
        store.compact()
```

(`compact()` is now threshold-gated and rebuild-based; WAL snapshot isolation protects in-flight readers, so no retention window is needed.)

- [ ] **Step 4: Update the other two call sites**

In `llm_index_add_or_update_document()`, delete the `store.ensure_document_id_scalar_index()` line. In `llm_index_compact()`, change `store.compact(retention_seconds=0)` to `store.compact(force=True)` and update its docstring to: `"""Compact the index immediately, rebuilding the table to reclaim space."""`

- [ ] **Step 5: Run the indexing tests, expect failures only in Lance-specific assertions**

```bash
cd src && uv run pytest paperless_ai/tests/test_ai_indexing.py --override-ini="addopts=" 2>&1 | tail -15
```

Expected: most tests pass; failures concentrated where tests reach into Lance internals (`isinstance` check ~line 690, direct-table row counts ~lines 482-508). Those are fixed next.

- [ ] **Step 6: Port the Lance-specific test assertions**

In `src/paperless_ai/tests/test_ai_indexing.py`:

1. Rename `class TestLanceDbIndexing` to `class TestVectorStoreIndexing` and change its isinstance assertion (~lines 687-690) to:

```python
        from paperless_ai.vector_store import PaperlessSqliteVecVectorStore

        store = indexing.get_vector_store()
        assert isinstance(store, PaperlessSqliteVecVectorStore)
```

2. Find the direct-row-count assertions (`rg -n "to_list|count_rows|open_table" src/paperless_ai/tests/test_ai_indexing.py`). Replace each direct Lance table read with the store's own connection, e.g. a zero-rows assertion becomes:

```python
        store = indexing.get_vector_store()
        assert not store.table_exists() or (
            store.client.execute("SELECT count(*) FROM documents").fetchone()[0] == 0
        )
```

and a "table exists with N rows" precondition becomes:

```python
        store = indexing.get_vector_store()
        assert store.table_exists()
        assert store.client.execute("SELECT count(*) FROM documents").fetchone()[0] > 0
```

3. Update the docstring/comment mentions of "LanceDB" in this file (`rg -n "Lance" ...`) to "the vector store" or "sqlite-vec" as reads naturally; do not change test logic beyond the direct-access ports.

- [ ] **Step 7: Run indexing + chat tests**

```bash
cd src && uv run pytest paperless_ai/tests/test_ai_indexing.py paperless_ai/tests/test_chat.py --override-ini="addopts=" 2>&1 | tail -5
```

Expected: all PASS (`chat.py` only consumes `load_or_build_index()`, no direct store APIs; verify with `rg -n "vector_store|lancedb" src/paperless_ai/chat.py` -> no hits).

- [ ] **Step 8: Commit**

```bash
git add src/paperless_ai/indexing.py src/paperless_ai/tests/test_ai_indexing.py
git commit -m "Enhancement(beta): wire indexing pipeline to the sqlite-vec store

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Move Filename / Storage Path / ASN from embedded text to node metadata

**Files:**

- Modify: `src/paperless_ai/embedding.py` (`build_llm_index_text`, ~lines 114-128)
- Modify: `src/paperless_ai/indexing.py` (`build_document_node` metadata dict, ~lines 106-119)
- Modify: `src/paperless_ai/tests/test_embedding.py`, `src/paperless_ai/tests/test_ai_indexing.py`

Resolves the `embedding.py:115` TODO. These three short structured values get the same treatment title/tags/correspondent/document_type received in PR #12944: excluded from the embedded text (they add noise, not semantic signal) but visible to the LLM via llama-index's metadata prepend. Notes and Custom Fields deliberately stay in the body (long free text / dynamic count). This changes every document's embedded text, which is exactly why it ships inside this rebuild-everything transition instead of later.

- [ ] **Step 1: Update the embedding-text test expectations**

In `src/paperless_ai/tests/test_embedding.py`, find the test asserting body-text content (~lines 227-238, the blocks commented "Structured fields live in node.metadata..." / "Fields without a metadata equivalent stay in body text"). Move the three fields to the excluded group:

```python
        # Structured fields live in node.metadata for LLM context — not body text
        assert "Title: Test Title" not in result
        assert "Created: 2023-01-01" not in result
        assert "Tags: Tag1, Tag2" not in result
        assert "Document Type: Invoice" not in result
        assert "Correspondent: Test Correspondent" not in result
        assert "Filename:" not in result
        assert "Storage Path:" not in result
        assert "Archive Serial Number:" not in result

        # Fields without a metadata equivalent stay in body text
        assert "Notes: Note1,Note2" in result
        assert "Content:\n\nThis is the document content." in result
        assert "Custom Field - Field1: Value1\nCustom Field - Field2: Value2" in result
```

- [ ] **Step 2: Add node-metadata expectations**

In `src/paperless_ai/tests/test_ai_indexing.py`, find the `build_document_node` test asserting `nodes[0].metadata["document_id"]` (~line 35) and extend it:

```python
    assert nodes[0].metadata["filename"] == real_document.filename
    assert nodes[0].metadata["storage_path"] == (
        real_document.storage_path.name if real_document.storage_path else None
    )
    assert (
        nodes[0].metadata["archive_serial_number"]
        == real_document.archive_serial_number
    )
    assert "filename" in nodes[0].excluded_embed_metadata_keys
    assert "filename" not in nodes[0].excluded_llm_metadata_keys
```

(Check the `real_document` fixture's actual attribute values first and mirror them; if it sets none of these, the assertions above still hold with `None` values, which is the point: absent values are `None` in node metadata, consistent with the existing `correspondent`/`document_type` convention.)

- [ ] **Step 3: Run both test files to verify the new assertions fail**

```bash
cd src && uv run pytest paperless_ai/tests/test_embedding.py paperless_ai/tests/test_ai_indexing.py --override-ini="addopts=" 2>&1 | tail -5
```

Expected: FAIL on the new assertions only ("Filename:" still in result; KeyError "filename" in metadata).

- [ ] **Step 4: Implement**

In `src/paperless_ai/embedding.py` `build_llm_index_text()`, delete these three lines from the `lines` list:

```python
        f"Filename: {doc.filename}",
        f"Storage Path: {doc.storage_path.name if doc.storage_path else ''}",
        f"Archive Serial Number: {doc.archive_serial_number or ''}",
```

and replace the TODO comment above the list with:

```python
    # Short structured fields (filename, storage path, ASN, title, tags, ...) live
    # in node.metadata: excluded from embeddings, shown to the LLM via metadata
    # prepend. Notes and Custom Fields stay in the body: Notes can be long free
    # text, Custom Fields are dynamic in count and best kept in the embedding.
```

In `src/paperless_ai/indexing.py` `build_document_node()`, extend the metadata dict (after the `"document_type"` entry):

```python
        "filename": document.filename,
        "storage_path": document.storage_path.name if document.storage_path else None,
        "archive_serial_number": document.archive_serial_number,
```

(`None`/int values are fine here: this dict is serialized into the node-content JSON, not into vec0 metadata columns; only `document_id` and `modified` are columns with the NULL restriction. `excluded_embed_metadata_keys=list(metadata.keys())` already covers the new keys; `excluded_llm_metadata_keys` stays `["document_id"]`.)

- [ ] **Step 5: Run the tests again**

```bash
cd src && uv run pytest paperless_ai/tests/test_embedding.py paperless_ai/tests/test_ai_indexing.py --override-ini="addopts=" 2>&1 | tail -5
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/paperless_ai/embedding.py src/paperless_ai/indexing.py src/paperless_ai/tests/test_embedding.py src/paperless_ai/tests/test_ai_indexing.py
git commit -m "Enhancement(beta): move filename/storage path/ASN to node metadata

Same treatment as title/tags/correspondent in #12944: excluded from
the embedded text, visible to the LLM via metadata prepend. Changes
embedded text for every document, so it ships inside the sqlite-vec
transition, whose forced rebuild re-embeds everything anyway.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Legacy Lance index transition tests

**Files:**

- Create: `src/paperless_ai/tests/test_legacy_lance_cleanup.py`

Per project convention, the transition behavior gets its own dedicated test file.

- [ ] **Step 1: Write the tests**

```python
from pathlib import Path

import pytest

from documents.models import Document
from paperless_ai import indexing


@pytest.fixture
def legacy_lance_dir(temp_llm_index_dir: Path) -> Path:
    """Simulate leftovers of a pre-sqlite-vec LanceDB index."""
    lance_table = temp_llm_index_dir / "documents.lance"
    (lance_table / "data").mkdir(parents=True)
    (lance_table / "data" / "0000.lance").write_bytes(b"not a real lance file")
    (temp_llm_index_dir / "meta.json").write_text("{}")
    return lance_table


@pytest.mark.django_db
class TestLegacyLanceCleanup:
    def test_update_removes_legacy_dir_and_forces_rebuild(
        self,
        legacy_lance_dir: Path,
        temp_llm_index_dir: Path,
        mock_embed_model,
        document_factory,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        document_factory(title="doc a", content="first document")
        indexing.update_llm_index(rebuild=False)
        assert not legacy_lance_dir.exists()
        assert not (temp_llm_index_dir / "meta.json").exists()
        assert "forcing a full rebuild" in caplog.text
        store = indexing.get_vector_store()
        assert store.table_exists()

    def test_update_without_legacy_dir_does_not_force_rebuild(
        self,
        temp_llm_index_dir: Path,
        mock_embed_model,
        document_factory,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        document_factory(title="doc a", content="first document")
        indexing.update_llm_index(rebuild=False)
        caplog.clear()
        indexing.update_llm_index(rebuild=False)
        assert "forcing a full rebuild" not in caplog.text

    def test_cleanup_helper_reports_absence(self, temp_llm_index_dir: Path) -> None:
        assert indexing._cleanup_legacy_lance_index() is False  # noqa: SLF001
```

Note: check `src/paperless_ai/tests/conftest.py` and `src/documents/tests/conftest.py` for the existing document-creation fixture name before running — `rg -n "document_factory|def make_document" src/paperless_ai/tests/ src/documents/tests/conftest.py`. If the AI tests build documents differently (e.g. direct `Document.objects.create(...)` with `checksum`/`title`), mirror that exact pattern here instead of `document_factory`; `test_ai_indexing.py` is the reference for how this app's tests create documents and invoke `update_llm_index`.

- [ ] **Step 2: Run them**

```bash
cd src && uv run pytest paperless_ai/tests/test_legacy_lance_cleanup.py --override-ini="addopts=" 2>&1 | tail -5
```

Expected: all PASS (the implementation landed in Task 4; this task is the dedicated coverage for it).

- [ ] **Step 3: Commit**

```bash
git add src/paperless_ai/tests/test_legacy_lance_cleanup.py
git commit -m "Test(beta): cover legacy LanceDB index cleanup and forced rebuild

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Remove lancedb (and check pyarrow), update lazy-import guard

**Files:**

- Modify: `pyproject.toml`, `uv.lock`, `src/paperless_ai/tests/test_lazy_imports.py`

- [ ] **Step 1: Confirm nothing references lancedb anymore**

```bash
rg -ln "lancedb" src/ --iglob '!**/test_lazy_imports.py'
```

Expected: no hits. If any remain, fix them before proceeding.

- [ ] **Step 2: Remove the dependency**

```bash
uv remove lancedb
```

- [ ] **Step 3: Check whether pyarrow is still needed**

```bash
rg -n "pyarrow" pyproject.toml src/ --iglob '!uv.lock'
uv pip list 2>/dev/null | rg -i pyarrow
```

If `pyproject.toml` lists pyarrow as a direct dependency and the only `src/` references are the lazy-import test string, run `uv remove pyarrow`. If pyarrow remains in `uv.lock` as a transitive dependency of something else, leave it; the lazy-import test still guards against it leaking into the light path.

- [ ] **Step 4: Update the lazy-import leak list**

In `src/paperless_ai/tests/test_lazy_imports.py`, change the leak list line to:

```python
            "leaked = [m for m in ('lancedb', 'pyarrow', 'llama_index', 'sqlite_vec') "
```

(Keeping `lancedb`/`pyarrow` in the list is free: absent packages can never appear in `sys.modules`, and the guard survives any accidental reintroduction.)

- [ ] **Step 5: Run the lazy import test and the full AI app suite**

```bash
cd src && uv run pytest paperless_ai/tests/test_lazy_imports.py --override-ini="addopts=" 2>&1 | tail -3
cd src && uv run pytest paperless_ai/ --override-ini="addopts=" 2>&1 | tail -5
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/paperless_ai/tests/test_lazy_imports.py
git commit -m "Chore(beta): drop lancedb dependency

Fixes #12970: the package whose wheels SIGILL on non-AVX2 CPUs is no
longer installed at all.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Full verification sweep

**Files:** none (verification only)

- [ ] **Step 1: Management command tests and the wider documents suite**

```bash
cd src && uv run pytest documents/tests/management/test_management_document_llmindex.py --override-ini="addopts=" 2>&1 | tail -5
cd src && uv run pytest documents/ paperless_ai/ -n auto 2>&1 | tail -5
```

Expected: all PASS. The llmindex command tests exercise `rebuild|update|compact` through `indexing.py`; if a compact test asserted Lance-version behavior, port the assertion to the new semantics (file shrinks / table intact), keeping the test's intent.

- [ ] **Step 2: Lint**

```bash
prek run --files $(git diff --name-only beta...HEAD | tr '\n' ' ')
```

Expected: clean (or auto-fixed; re-add and amend if prek rewrites files).

- [ ] **Step 3: The point of it all — ISA verification**

If qemu-user is available (`which qemu-x86_64`), run the smoke check that the AI path no longer imports anything AVX2-baked:

```bash
cd src && uv run python -c "import sys; print(sys.executable)"
# then, using that interpreter path:
qemu-x86_64 -cpu Westmere <interpreter-path> -c "
import sqlite3, sqlite_vec, struct
db = sqlite3.connect(':memory:')
db.enable_load_extension(True)
sqlite_vec.load(db)
db.execute('create virtual table v using vec0(embedding float[384])')
db.execute('insert into v(rowid, embedding) values (1, ?)', (struct.pack('384f', *([0.5]*384)),))
print(db.execute('select rowid from v where embedding match ? and k = 1', (struct.pack('384f', *([0.4]*384)),)).fetchone())
print('OK: sqlite-vec works on a pre-AVX2 CPU')
"
```

Expected: `(1,)` then the OK line, exit 0.

- [ ] **Step 4: Update project memory**

Append to the memory file `project_vector_store_alternatives.md`: transition implemented on branch `feature-sqlitevec-vector-store`, lancedb removed, and any gotchas discovered during implementation (especially if the compact rename fallback from Task 3 Step 2 was needed).

- [ ] **Step 5: Final commit if anything moved, then summarize the branch**

```bash
git log --oneline beta..HEAD
git diff --stat beta...HEAD
```

Hand the branch to the user for PR creation (PRs are the user's call; do not push or open one unprompted).

---

## Self-review checklist (already applied)

- Spec coverage: every section of the design doc maps to a task (pin+canary -> Task 1; schema/store -> Tasks 2-3; indexing wiring + compact semantics -> Task 4; metadata restructure -> Task 5; migration-from-Lance -> Tasks 4 and 6; dependency changes -> Task 7; test plan + ISA check -> Tasks 2, 6, 8). Deliberately out of scope per the user: schema-migration machinery (second spec, lands after this branch with an empty registry).
- The `_INSERT` class attribute is defined in Task 3 before both uses; `DB_FILENAME` is exported and imported by the Task 2 tests; `compact(force=...)` keyword matches between store (Task 3) and indexing (Task 4); `_cleanup_legacy_lance_index` is defined in Task 4 and referenced by Task 5 tests.
- Known soft spots called out inline rather than hidden: the `document_factory` fixture name (Task 5 Step 1 note), possible llmindex-command test assertions (Task 7 Step 1), and the vec0 ALTER RENAME fallback (Task 3 Step 2).
- `query()` slices to `top_k` defensively even though metadata-column `k` is already global, and `_build_where` allowlists filter columns, so user data never reaches SQL identifiers; values always travel as bound parameters.
