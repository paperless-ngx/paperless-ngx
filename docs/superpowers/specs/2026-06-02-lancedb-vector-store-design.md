# Replace the FAISS vector store with LanceDB

**Date:** 2026-06-02
**Status:** Design — pending implementation plan
**Area:** `src/paperless_ai/` (AI / LLM index feature)

## Problem

The optional AI feature stores document embeddings in a llama-index `StorageContext`
made of three file-backed components persisted under `DATA_DIR/llm_index/`:

| Component                                | Role                                                 | Backing           |
| ---------------------------------------- | ---------------------------------------------------- | ----------------- |
| `FaissVectorStore` (`faiss.IndexFlatL2`) | the vectors                                          | binary faiss file |
| `SimpleDocumentStore`                    | node text + metadata (source of truth for retrieval) | one large JSON    |
| `SimpleIndexStore`                       | `vector_id → node_id` map                            | JSON              |

`faiss.IndexFlatL2` is append-only and has no metadata filtering, and all three
components are whole-file, load-everything-into-RAM structures. That combination —
not FAISS alone — drives the bulk of the surrounding complexity and is what fails
on large installs:

1. **Deletes are fake.** On update/remove, `remove_document_docstore_nodes`
   (`indexing.py:182`) deletes nodes from the _docstore_ only; the FAISS vectors
   physically remain forever. The only way to truly reclaim them is a full
   `rebuild=True` (re-embed every document).
2. **No metadata filtering** forces the entire custom `DocumentFilteredFaissRetriever`
   (`chat.py:78-151`) with its expanding `top_k *= 2` loop to emulate a
   `document_id IN (...)` filter.
3. **Whole-docstore Python scans.** `query_similar_documents` (`indexing.py:419`)
   iterates the full docstore in Python to translate `document_id → node_id`.
4. **Write amplification.** Every single-document add/update/remove takes a global
   `FileLock` and calls `storage_context.persist()`, which rewrites the entire
   multi-GB JSON docstore — O(N) memory and O(N) disk per document operation.
5. **Brute-force query.** `IndexFlatL2` is O(N·d) per search with no ANN.

We cannot predict or bound a user's install size, so the replacement must scale from
a handful of documents to very large corpora on a single node, with no extra service.

## Constraints (decided during brainstorming)

- **Engine-agnostic, on-disk store.** Paperless supports SQLite, PostgreSQL _and_
  MariaDB, so DB-integrated vectors (e.g. pgvector) are out — the vector store stays
  a self-contained on-disk artifact like today's `llm_index` dir, identical across DB
  backends.
- **Swap the storage layer only.** Keep llama-index as the framework. `VectorStoreIndex`,
  the retrievers, the chat query engine + response synthesizer, `SimpleNodeParser`, and
  the embedding-model abstraction are all unchanged. Only the `StorageContext` trio is
  replaced.
- **Store: LanceDB**, integrated via a **custom `BasePydanticVectorStore` adapter** we
  own (`PaperlessLanceVectorStore`) talking to `lancedb` + `pyarrow` directly — _not_ the
  official `llama-index-vector-stores-lancedb` wrapper. The wrapper was evaluated and
  rejected: it hard-requires `pandas`, hides `index_type` behind `**kwargs`, and _raises_
  on empty query results. A ~150-180 line adapter against llama-index's stable public
  interfaces avoids all three and lets us own the table schema. (See "Why a custom
  adapter".)
- **ANN: auto threshold.** Small installs use LanceDB's exact (brute-force) kNN, which
  LanceDB's own docs call sufficient for datasets up to ~100K vectors. Past a threshold
  we build an IVF index automatically, best-effort, with exact search as the
  always-valid fallback.
- **pandas is eliminated.** `llama-index-core` does not depend on pandas, and the custom
  adapter materializes LanceDB results via `pyarrow` (`.to_list()`), so pandas never
  enters the dependency tree. `pyarrow` is a direct dep but arrives transitively through
  `lancedb` regardless.

## Why LanceDB

LanceDB is the only embedded, serverless candidate architected for **disk-resident,
memory-mapped** operation — RAM does not scale with the corpus, which is the single
most important property for "tiny or very large, equally." It provides real CRUD
(predicate `delete`, `add`), filtered search, and IVF ANN, all writing to a directory on
disk. Because our adapter declares `stores_text = True`, llama-index runs off the vector
store alone — so both `SimpleDocumentStore` and `SimpleIndexStore` are deleted outright.

Verified against `lancedb 0.33.0` with functional probes:

- A `lancedb` table on disk is memory-mapped; writes are durable on call (connect = a
  directory, table = a Lance dataset). **No `persist()` and no whole-file rewrite.**
- `table.delete('doc_id = "..."')` is a real predicate delete that physically removes
  rows (probe: a 2-chunk doc dropped to 0 rows).
- `table.add(rows)` appends; `merge_insert(...).when_not_matched_by_source_delete(...)`
  provides an atomic upsert that also prunes stale chunks — the incremental update path
  (see §3). Verified: a doc going 5→3 chunks ends with exactly the 3 new chunks.
- `table.search(embedding).where('document_id IN (...)').limit(k).to_list()` returns
  plain dicts via `pyarrow` (**no pandas**), and returns `[]` cleanly on no match — **no
  raise**.

## Why a custom adapter (not `llama-index-vector-stores-lancedb`)

The custom adapter was proven end-to-end through llama-index's real
`VectorStoreIndex` → `VectorIndexRetriever` path with a `MockEmbedding`: build, update
(delete+insert with **zero orphan rows**), `MetadataFilters(IN)` forwarded through the
retriever, empty-filter → `[]`, and remove — all with **`pandas` never imported**. The
adapter is ~120 lines in the probe (≈150-180 production-ready) and uses only llama-index's
**stable public** primitives: `BasePydanticVectorStore`, `node_to_metadata_dict` /
`metadata_dict_to_node`, `VectorStoreQuery` / `VectorStoreQueryResult`.

Choosing the adapter over the wrapper converts several wrapper-specific liabilities into
non-issues:

| Wrapper liability                                                                       | With the custom adapter                                                                            |
| --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Hard-imports `pandas` (`base.py:33`), uses `.to_pandas()`                               | Eliminated — `pyarrow.to_list()`                                                                   |
| `create_index` hides `index_type`, hard-defaults `num_sub_vectors=96` (base.py:333-368) | We call `table.create_index(...)` with explicit `index_type` / partitions / sub-vectors            |
| `query()` _raises_ `Warning` on empty results (base.py:560-563)                         | Our `query()` returns an empty `VectorStoreQueryResult` natively                                   |
| `_to_lance_filter` prefixes `metadata.<key>`; fragile when `_metadata_keys is None`     | Dedicated top-level `document_id` column; filter is plain `document_id IN (...)`, scalar-indexable |
| Third-party package to pin and track for API drift                                      | No integration package; depend only on stable llama-index core interfaces                          |

The cost is ~150-180 lines we own and test (vs. a ~10-line subclass) — but we were
already subclassing to swallow the empty-result `Warning` and add the ANN threshold, so
the net additional code is modest and removes a dependency.

## Design

### 1. Storage layer

Replace `get_or_create_storage_context()` with a vector-store factory that returns a
`PaperlessLanceVectorStore` pointed at `settings.LLM_INDEX_DIR` with an **explicit,
pinned `table_name`** (e.g. `LLM_INDEX_TABLE = "documents"`) used consistently by the
factory, the existence check (§7), and the migration detection (§8). The index is built
with `VectorStoreIndex.from_vector_store(vector_store, embed_model=...)` for the
load/query path, and `VectorStoreIndex(nodes=..., storage_context=...)` (storage context
holding only the vector store) for the rebuild path. No docstore, no index store.

`meta.json` (embedding model name + dimension) is **kept** for embedding-model-change
detection that forces a rebuild — unchanged from today (`embedding.py:get_embedding_dim`).

### 2. `PaperlessLanceVectorStore(BasePydanticVectorStore)`

A custom adapter (~150-180 lines) implementing llama-index's vector-store contract
directly against `lancedb` + `pyarrow`. Class flags: `stores_text = True`,
`flat_metadata = True`.

**Table schema** (explicit `pyarrow` schema, created lazily on first `add`):

| Column         | Type                            | Purpose                                                           |
| -------------- | ------------------------------- | ----------------------------------------------------------------- |
| `id`           | `string`                        | node id (`node.node_id`)                                          |
| `doc_id`       | `string`                        | `node.ref_doc_id` (= `str(document.id)`, see §3) — the delete key |
| `document_id`  | `string`                        | top-level filter column (mirrors `metadata["document_id"]`)       |
| `vector`       | `fixed_size_list<float32>[dim]` | embedding                                                         |
| `node_content` | `string`                        | `json.dumps(node_to_metadata_dict(node, remove_text=False))`      |

A dedicated top-level `document_id` column (rather than the wrapper's nested
`metadata.<key>` struct) makes filtering a plain `document_id IN (...)` predicate and
allows an optional LanceDB **scalar index** on it for fast filtered scans.

**Methods:**

- `add(nodes)` — serialize each node via `node_to_metadata_dict(node, remove_text=False,
flat_metadata=True)` into the schema above; lazily `create_table` (with the explicit
  schema sized to the embedding dim) or `table.add(rows)` (plain append). Used by the
  **rebuild** path (bulk insert into a fresh table) and as llama-index's `add` hook.
  Returns node ids.
- `upsert_document(document_id, nodes)` — the **incremental** add/update path. A single
  `merge_insert("id").when_matched_update_all().when_not_matched_insert_all()
.when_not_matched_by_source_delete("document_id = '<id>'").execute(rows)` — atomic
  replace-with-prune for one document (see §3). All nodes passed must belong to the one
  `document_id`. Nodes are embedded before the call (the incremental path embeds with the
  configured `embed_model` rather than going through `index.insert_nodes`).
- `delete(ref_doc_id)` — `table.delete(f'doc_id = "{ref_doc_id}"')` (parameter-escaped).
  Used for document removal.
- `delete_nodes(node_ids)` — `table.delete('id IN (...)')` (for completeness).
- `get_nodes(node_ids=None, filters=None)` — `table.search().where(...).to_list()`,
  rebuild nodes via `metadata_dict_to_node(json.loads(row["node_content"]))`. Returns `[]`
  cleanly when empty — the correct primitive for the chat no-content pre-check.
- `query(VectorStoreQuery)` — `table.search(query.query_embedding).where(_build_where(
query.filters)).limit(query.similarity_top_k).to_list()`; rebuild nodes, map LanceDB L2
  `_distance` → a similarity score, and **return an empty `VectorStoreQueryResult` on no
  match (no raise)**.
- `client` property → the `lancedb` connection.

**Filter translation** — `_build_where(MetadataFilters)` handles exactly the operators we
use (`EQ`, `IN`) on the top-level `document_id` column, string-escaping values. This is
small, fully owned, and free of the wrapper's `metadata.`-prefix / `_metadata_keys`
behavior.

**Auto ANN index** — `maybe_create_ann_index()`, called after build/update writes **while
holding the global write lock** (it is itself a write path): if the table row count
exceeds `ANN_INDEX_MIN_ROWS` (~100K chunks, per LanceDB guidance) and no vector index
exists yet, best-effort `table.create_index(...)`:

- **Index type by divisibility.** IVF*PQ requires `num_sub_vectors` to \_evenly divide*
  the embedding dimension — LanceDB raises a hard `RuntimeError` otherwise (verified). The
  dimension is detected at runtime from a user-configurable model and many common dims
  (e.g. 1024) are **not** divisible by 96. So: pick a `num_sub_vectors` that divides the
  dim and build **IVF_PQ**; if none exists, build **IVF_FLAT** (`index_type="IVF_FLAT"`),
  which has no divisor constraint and still gives IVF/ANN speedup — strictly better than
  reverting to full brute-force. (Talking to `lancedb` directly, `index_type` is just a
  named argument — none of the wrapper's kwargs-smuggling.)
- `num_partitions`: LanceDB guidance is ≈ `num_rows / 4096`; clamp to a sane minimum.
- Wrapped in `try/except` — a failure logs and leaves the table on exact search, which is
  always correct.

### 3. Node identity

In `build_document_node` (`indexing.py:109`), set the `LlamaDocument` `id_` to
`str(document.id)`. `SimpleNodeParser` propagates that as each chunk node's
`ref_doc_id`, and the adapter stores it in the `doc_id` column. Result: every chunk of a
paperless document shares `ref_doc_id == str(document.id)`, so one `delete(str(doc.id))`
clears exactly that document's chunks (verified end-to-end). `document_id` also remains in
node metadata (and is mirrored to the top-level filter column) for filtering and result
mapping.

**Update = native upsert via `merge_insert` (one atomic commit).** The incremental
add/update path uses a single `merge_insert`, not delete-then-add:

```
table.merge_insert("id")
     .when_matched_update_all()
     .when_not_matched_insert_all()
     .when_not_matched_by_source_delete(f"document_id = '{document_id}'")
     .execute(new_rows)
```

The `when_not_matched_by_source_delete` clause — scoped to the document's `document_id`
— prunes stale trailing chunks (the case where an edit reduces a document's chunk count)
**atomically in the same commit**. Verified on 0.33.0: a doc going 5→3 chunks ends with
exactly the 3 new chunks, other documents untouched, and it works whether or not chunk
ids are deterministic (non-matching ids become a full replace).

This is strictly better than delete-then-add on three axes:

- **Atomicity / no transient empty state.** Queries take no lock (§6), so delete-then-add
  exposes a window between the delete commit and the add commit in which a concurrent
  reader sees the document with **zero chunks**. A single `merge_insert` commit eliminates
  that window — a reader sees either the old or the new chunk set.
- **Half the version growth.** One commit per update instead of two, directly halving the
  MVCC version accumulation that compaction (§10) must reclaim.
- **Correctness preserved** without a separate delete call.

> **Important:** `optimize()` prunes old _versions_, **not** dead _rows_ in the live
> version. A plain upsert (update+insert without the delete clause) would leave stale
> chunks as live rows that `optimize` can never remove — so the
> `when_not_matched_by_source_delete` clause is mandatory, not optional.

> **Index caveat (LanceDB #3177):** `merge_insert` can fail _silently_ after `optimize()`
> when a scalar index exists on the **match column**. We match on `id`, so a scalar index
> must **never** be created on `id`. The optional scalar index for filtering goes on
> `document_id` only (§2), which is not the match column.

### 4. The four operations collapse

| Operation    | Before                                                                                                      | After                                                                                   |
| ------------ | ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| add / update | load whole index → `remove_document_docstore_nodes` (fake delete) → `insert_nodes` → `persist` (rewrite GB) | `store.upsert_document(str(doc.id), embedded_nodes)` (one atomic `merge_insert` commit) |
| remove       | load → docstore delete → persist                                                                            | `store.delete(str(doc.id))`                                                             |
| similar      | load whole docstore, Python scan for node ids, custom retriever                                             | `VectorIndexRetriever(index, similarity_top_k=k, filters=document_id IN allowed)`       |
| chat         | custom `DocumentFilteredFaissRetriever` (74 lines)                                                          | stock `VectorIndexRetriever(filters=document_id IN doc_ids)`                            |

Deleted entirely: `remove_document_docstore_nodes`, the whole-docstore scan in
`query_similar_documents`, and `_get_document_filtered_retriever` /
`DocumentFilteredFaissRetriever` in `chat.py`. `chat.py`'s direct reaches into
`index.docstore.docs`, `index.vector_store._faiss_index`, and
`index.index_struct.nodes_dict` all disappear. The "no content" pre-check in
`_stream_chat_with_documents` becomes a `store.get_nodes(filters=...)` existence check —
the adapter's `get_nodes` returns `[]` cleanly on no match, so it is the correct
primitive for an existence test. References are still derived from returned nodes'
`metadata["document_id"]` / `metadata["title"]`, so `_get_document_references` is
unchanged.

Because the adapter's `query()` returns an empty result on no match (it never raises),
both similar-docs and chat — which retrieve through `VectorIndexRetriever` /
`RetrieverQueryEngine` calling `vector_store.query()` internally — get a clean empty
result set instead of an exception. This was the wrapper's most disruptive wart and is
designed out, not worked around.

### 5. Filtering

Both similar-document and chat retrieval pass a `MetadataFilters` with a single
`MetadataFilter(key="document_id", operator=FilterOperator.IN, value=[...])` (omitted
when unconstrained). The adapter's `_build_where` translates this to the plain predicate
`document_id IN ("...","...")` against the top-level `document_id` column — no struct
path, no `_metadata_keys` dependence, so filtering is unconditionally correct on a freshly
opened table and across process restarts (proven by the fresh-process probe).

This replaces today's `query_similar_documents` mechanism, which pre-scans the docstore
for node ids and passes `doc_ids=` to `VectorIndexRetriever` (`indexing.py:416-434`) — a
_different_ retriever mechanism. The new path relies on
`VectorIndexRetriever(filters=MetadataFilters(...))` forwarding `query.filters` into
`vector_store.query()` — **verified end-to-end in the probe** (a retriever with an `IN`
filter returned only the matching document). Still covered by a regression test (see
Testing) since it is load-bearing for both similar-docs and chat.

### 6. Concurrency

Keep the existing `FileLock(_index_lock_path())` around **writes** only. Each write is now
a small delta append/upsert instead of a multi-GB rewrite, so the lock is held briefly.
Queries take no lock (LanceDB reads are MVCC snapshot-consistent). The lock-free read path
is safe for updates specifically because the incremental update is a single atomic
`merge_insert` commit (§3) — a reader never observes a document mid-update. The lock still
serializes _writers_ across Celery processes to avoid `CommitConflictError`.

**Why the global lock is load-bearing.** LanceDB's MVCC tolerates concurrent _appends_,
but concurrent _delete/update_ operations frequently conflict and fail with
`CommitConflictError` after exhausting retries (LanceDB issues #1597, #3086). Paperless's
add/update path is exactly delete-then-insert and runs from **separate Celery worker
processes**. The design is safe only because `_index_lock_path()` is a single shared lock
file under `LLM_INDEX_DIR` that serializes _all_ writers. This lock must:

- remain a single global lock (do **not** relax to per-document granularity), and
- cover every write path — add, update, remove, **and** `maybe_create_ann_index()`.

### 7. Index existence / rebuild trigger

Replace `vector_store_file_exists()` with a check for the LanceDB table's existence
(`LLM_INDEX_DIR` present and the pinned `LLM_INDEX_TABLE` in `connection.table_names()`).
The existing `queue_llm_index_update_if_needed` / `load_or_build_index` rebuild-on-missing
logic is otherwise unchanged.

**Dimension-mismatch guard.** The Lance table's vector column dimension is fixed at the
first `add()`. Beyond the `meta.json` model-change detection (which forces a rebuild when
the _model name_ changes), guard against a dimension mismatch directly: if the current
embedding dim differs from the existing table's vector dim, force a rebuild rather than
letting `add()` fail with a hard dimension error. This covers the gaps `meta.json` can't —
a missing/corrupt `meta.json`, or two models sharing a name but differing in dim.

### 8. Migration

The index is fully derived data, rebuildable from `Document` rows. On first run of the
new code, detect the stale FAISS format (presence of `default__vector_store.json` /
faiss files with no LanceDB table), wipe `LLM_INDEX_DIR`, and trigger a rebuild through
the existing `queue_llm_index_update_if_needed(rebuild=...)` path. No data migration and
no user action beyond the automatic background rebuild.

### 9. Dependencies (`pyproject.toml`)

- **Remove:** `faiss-cpu`, `llama-index-vector-stores-faiss`.
- **Add:** `lancedb` (pulls in `pyarrow`, `numpy`, `pydantic`, `tqdm`) and `pyarrow`
  (declared directly since the adapter imports it, even though `lancedb` pulls it
  transitively). **No `llama-index-vector-stores-lancedb`, no `pandas`** — `llama-index-core`
  does not require pandas (verified) and the adapter uses `pyarrow.to_list()`.
- Confirm multi-arch wheels (linux x86_64 + aarch64, the paperless Docker targets) for
  `lancedb`/`pyarrow` resolve in the lockfile. (`lancedb 0.33.0` ships manylinux x86_64 +
  aarch64 wheels, matching the paperless Docker build matrix.)

### 10. Maintenance / compaction — **required, not optional**

MVCC has a real disk cost that this design must actively manage. LanceDB writes a **new
fragment + version on every `add`/`delete`** and retains the superseded files until
cleanup. Paperless adds/updates documents **one at a time**, so the store bloats
continuously without maintenance. Measured on 2000 × 768-dim vectors (raw float32 =
6000 KiB):

| Scenario                                                | On disk                | Versions |
| ------------------------------------------------------- | ---------------------- | -------- |
| One bulk insert (= a rebuild)                           | 6016 KiB               | 1        |
| 2000 single-row adds (= per-document writes)            | **172,848 KiB (~28×)** | 2001     |
| After `table.optimize(cleanup_older_than=timedelta(0))` | **6344 KiB**           | 1        |

Implications:

- **Full rebuilds are naturally compact** (bulk insert ≈ raw vector bytes), so a rebuild
  resets accumulated bloat.
- **The atomic upsert (§3) halves _update_ version growth** (one commit instead of
  delete-then-add's two), but every new-document insert is still its own version, so
  versions accumulate over time regardless — compaction remains required.
- **Per-document writes must be compacted periodically.** Run
  `table.optimize(cleanup_older_than=<retention>)` — a **single call** that compacts
  fragments _and_ drops old versions — folded into the existing scheduled LLM-index
  maintenance task, under the global write lock. Use a small but non-zero retention in
  production (e.g. minutes–hours) so an in-flight reader on an old version isn't pulled
  out from under; `timedelta(0)` is for tests/rebuild-time only.
- **Do not use the older `cleanup_old_versions()`** API: it requires the separate
  `pylance` package (not pulled by `lancedb` core) and is superseded by
  `optimize(cleanup_older_than=...)`.

**On the "larger on disk than FAISS" observation:** at small scale LanceDB stores vectors
as **raw `float32`** (identical per-vector bytes to FAISS `IndexFlatL2`); vector
_compression_ only comes from the IVF*PQ index, which only exists past the ANN threshold
(§2). So a small dataset is expected to be \_comparable, not smaller*, than FAISS — and any
large discrepancy is version accumulation, fixed by the compaction above.

> **Windows note:** the probe hit an `Access is denied` error writing a version-hint file
> during cleanup on Windows (temp-dir file locking). Paperless production is Linux
> containers, so this does not affect the deployment target, but bare-metal Windows dev
> installs may need attention.

## Testing

Per project conventions (pytest-style, classes with `@pytest.mark.django_db`,
pytest-mock, factory-boy, type-annotated fixtures/tests, default config). LanceDB writes
to a real directory, so tests point `settings.LLM_INDEX_DIR` at `tmp_path` and exercise a
**real** (tiny) LanceDB table with a stub embedding model returning deterministic vectors
— no mocking of store internals.

- **add → query** returns the document.
- **update** via `upsert_document` leaves no orphan rows — re-index a document whose chunk
  count _shrinks_ (e.g. 5→3) and assert exactly the new chunks remain and other documents
  are untouched (this is the regression the old fake delete could not provide, and proves
  `when_not_matched_by_source_delete` prunes stale chunks).
- **update is one commit** — assert the table version advances by exactly 1 per
  `upsert_document` (guards the atomicity / version-growth property).
- **remove** drops all of a document's chunks.
- **filtered query** scopes results to the given `document_id`s and excludes others.
- **empty query** returns `[]` (the adapter's `query()` never raises).
- **node round-trip**: a node serialized via `node_to_metadata_dict` and reconstructed via
  `metadata_dict_to_node` preserves text + metadata (`document_id`, `title`).
- **embedding-model change** → `meta.json` mismatch forces rebuild (existing behavior).
- **dimension-mismatch guard** → a current embedding dim differing from the stored table
  dim forces a rebuild rather than a hard `add()` failure.
- **ANN threshold** trigger logic with a low test threshold: `maybe_create_ann_index`
  attempts an index past the threshold and is a no-op below it; a `create_index` failure
  is non-fatal and leaves exact search working.
- **ANN fallback on a non-divisible dim**: with an embedding dim not divisible by the PQ
  `num_sub_vectors` (e.g. 1024), `maybe_create_ann_index` builds IVF_FLAT (or the
  try/except fallback fires) and leaves the table queryable, not broken/unindexed.
- **Fresh-process filtering**: construct a brand-new `PaperlessLanceVectorStore` against an
  existing on-disk table and assert an `IN` filter still returns the right rows — the
  cross-restart path.
- **Retriever forwards filters**: assert `VectorIndexRetriever(filters=MetadataFilters(...))`
  built on `VectorStoreIndex.from_vector_store(...)` actually scopes results — the
  load-bearing integration seam for similar-docs and chat.
- **Compaction reclaims versions**: after several single-document writes, the maintenance
  `optimize(cleanup_older_than=...)` call reduces the table to a single version and
  results stay queryable afterward.
- **Upsert after optimize** (LanceDB #3177 guard): with a scalar index on `document_id`
  (and none on `id`), an `upsert_document` performed _after_ `optimize()` still prunes and
  replaces correctly — verified, but pinned with a test so a future index-placement change
  or LanceDB regression is caught.
- Parametrize the add/update/remove variations rather than duplicating bodies.

## Out of scope

- Replacing llama-index for chunking, embeddings, or the chat query engine.
- Any DB-integrated (pgvector-style) path.
- Hybrid / full-text / reranked search modes offered by LanceDB (vector search only,
  matching current behavior).
- Tuning embedding models or chunking parameters.

## Open risks

- **pyarrow/lancedb footprint.** `lancedb` + `pyarrow` (native wheels) enlarge the optional
  AI feature's dependency tree; verify image-size impact when updating the lockfile. (Still
  lighter than the wrapper path, which added `pandas` on top of these.)
- **ANN index parameters.** The IVF_PQ-vs-IVF_FLAT-by-divisibility logic (§2) plus the
  best-effort/exact fallback contains the correctness risk, but the row threshold and
  `num_partitions` heuristic should be validated on a large fixture for actual query
  latency.
- **We own the adapter.** We depend on llama-index's `BasePydanticVectorStore` interface
  and the `node_to_metadata_dict` / `metadata_dict_to_node` helpers. These are stable core
  APIs (far more stable than the integration package), but a major llama-index bump should
  re-run the end-to-end retriever test. Pin a known-good `lancedb` and `llama-index-core`.
- **`merge_insert` + scalar index on the match column (LanceDB #3177).** `merge_insert` can
  fail _silently_ after `optimize()` if a scalar index exists on the match column. We match
  on `id` and only index `document_id`, so we are clear — but this is an invariant to
  enforce (never index `id`) and to cover with a test that exercises
  upsert-after-optimize.
