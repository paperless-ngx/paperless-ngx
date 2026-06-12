# sqlite-vec Vector Store Design (replaces PaperlessLanceVectorStore)

Date: 2026-06-10

Context: LanceDB wheels SIGILL on non-AVX2 CPUs (#12970); research in `2026-06-10-vector-store-alternatives-research.md` selected sqlite-vec. This is a beta feature, so a one-time re-embed on upgrade is acceptable. Every claim marked [VERIFIED] below was empirically tested against the actual PyPI wheel (0.1.9, and 0.1.10a4 where noted), either in this repo's scratch harness (`/tmp/vstore-avx-test/explore_sqlitevec*.py`) or by the issues-audit agent.

## Version pin: `sqlite-vec==0.1.9`, and why it is load-bearing

- The 0.1.9 linux x86_64 wheel is built with **no SIMD flags at all** (`vec_debug()` shows empty build flags) and passed our qemu Westmere (SSE4.2, no AVX) and SandyBridge (AVX, no AVX2) emulation tests [VERIFIED]. This is the entire point of the migration.
- The **0.1.10-alpha.4 wheel regresses this**: built with `-mavx -DSQLITE_VEC_ENABLE_AVX` file-wide, no runtime CPU dispatch. It can SIGILL on AVX-less CPUs, including Goldmont Atom/Celeron NAS boxes, exactly the #12970 user base [VERIFIED via vec_debug on the wheel].
- Guardrails: pin `==0.1.9` exactly; log `SELECT vec_version(), vec_debug()` at store init as an AVX canary; before ever bumping to 0.1.10+, re-check the wheel flags (and consider raising the runtime-dispatch issue upstream first).
- arm64: 0.1.9 manylinux aarch64 wheel is a proper ELF64 binary, no NEON flags baked [VERIFIED]. (The broken 32-bit "aarch64" wheel era was 0.1.6, fixed since.)
- No sdist on PyPI (asg017/sqlite-vec#211, open) and no musl wheels; fine for our Debian-based image, blocks Alpine bare-metal installs.

## Schema

One dedicated SQLite database file in `LLM_INDEX_DIR` (e.g. `llmindex.db`), never the Django DB. Connections set `PRAGMA journal_mode=WAL`, `busy_timeout`, `synchronous=NORMAL`.

```sql
CREATE VIRTUAL TABLE nodes USING vec0(
    id TEXT PRIMARY KEY,             -- node_id (uuid)
    document_id TEXT,                -- METADATA column, deliberately NOT a partition key
    modified TEXT,                   -- ISO timestamp; never NULL (sentinel "")
    +node_content TEXT,              -- auxiliary column: JSON payload, any size
    embedding float[{dim}] distance_metric=cosine
);

CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT);
-- rows: embed_model, dim, schema_version, created_by_vec_version
```

Design decisions, each verified on 0.1.9:

- **`document_id` is a metadata column, not a partition key.** With a partition key, `k` applies per partition: `k=5 AND document_id IN (3 docs)` returns 15 rows (asg017/sqlite-vec#142, open) [VERIFIED]. As a metadata column the same query returns a correct global top-k of exactly 5 [VERIFIED]. `query_similar_documents()` passes permission-scoped `IN` lists, so per-partition semantics would over-fetch k x N(docs). At our scale the partition-pruning speedup is not needed (filtered KNN at 20K x 1024 was _faster_ than unfiltered: 39 ms vs 74 ms).
- **One document column, not two.** The Lance store carried both `doc_id` (ref_doc_id) and `document_id`; in our usage they are always the same value (`str(document.id)`), so the new schema keeps only `document_id`.
- **TEXT primary key works** (insert, UPDATE, DELETE, duplicate rejection) [VERIFIED]. There is no usable rowid mapping with a TEXT pk, which we do not need.
- **Aux column for the payload.** `+node_content` holds the multi-KB JSON; aux columns cannot appear in KNN WHERE clauses (loud error, not silent) [VERIFIED], which we never do, and are selectable in scans and KNN results [VERIFIED].
- **Metadata columns reject NULL** (asg017/sqlite-vec#141, open) [VERIFIED]. `_row()` must keep coercing everything through `str(... or "")` as it already does today.
- **`distance_metric=cosine`**: similarity maps as `1 - distance` (identical vector gives distance 0.0 [VERIFIED]). For unit-norm embeddings the ranking equals today's L2 ranking; for non-normalized models cosine is the safer default, and the beta re-embed makes the behavior change free. (L2 + `1/(1+d)` remains available if exact parity is ever wanted.)
- **Vectors are always bound as float32 BLOBs** (`struct.pack`/`np.tobytes`), never JSON text: bypasses the locale-dependent `strtod` parsing bug (asg017/sqlite-vec#241, open) entirely.
- Limits, all comfortable: dims <= 8192, k <= 4096, chunk_size default 1024 [VERIFIED]. TEXT metadata has no length cap; values > 12 bytes go to a shadow text table with a prefix fast-path, and the one historical bug at that boundary (long-metadata DELETE, #274) is fixed in 0.1.9.

## Method mapping (PaperlessLanceVectorStore -> PaperlessSqliteVecVectorStore)

| Current method                                | sqlite-vec implementation                                                                                                              | Notes                                                                                                                                                                                                                   |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `__init__(uri, table_name, embed_model_name)` | `sqlite3.connect(path)` + `enable_load_extension` + `sqlite_vec.load()` + PRAGMAs                                                      | Same lazy "table may not exist yet" stance                                                                                                                                                                              |
| `client` property                             | the `sqlite3.Connection`                                                                                                               |                                                                                                                                                                                                                         |
| `table_exists()`                              | `SELECT 1 FROM sqlite_master WHERE name='nodes'`                                                                                       |                                                                                                                                                                                                                         |
| `vector_dim()`                                | `index_meta['dim']`                                                                                                                    | Written at table creation; wrong-dim inserts are rejected by vec0 anyway [VERIFIED]                                                                                                                                     |
| `drop_table()`                                | `DROP TABLE nodes`                                                                                                                     | Drops all 7 shadow tables with it [VERIFIED]; also clear `index_meta`                                                                                                                                                   |
| `stored_model_name()` / `config_mismatch()`   | `index_meta['embed_model']`                                                                                                            | Same conservative None handling                                                                                                                                                                                         |
| `_schema(dim, model)`                         | the CREATE statements above                                                                                                            | dim from first batch, as today (`_ensure_table`)                                                                                                                                                                        |
| `_row(node)`                                  | same dict, vector packed to bytes                                                                                                      | keep `str(... or "")` coercion (NULL rejection)                                                                                                                                                                         |
| `add(nodes)`                                  | `executemany(INSERT ...)` inside one transaction                                                                                       | ~3,300 rows/s at 1024 dims measured; batching via transactions                                                                                                                                                          |
| `upsert_document(document_id, nodes)`         | `BEGIN; DELETE FROM nodes WHERE document_id = ?; executemany(INSERT); COMMIT`                                                          | **Not** `INSERT OR REPLACE`: broken on vec0 (asg017/sqlite-vec#259, open). Transaction gives the same no-transient-empty-state guarantee as merge_insert; rollback verified [VERIFIED]                                  |
| `delete(ref_doc_id)`                          | `DELETE FROM nodes WHERE document_id = ?`                                                                                              |                                                                                                                                                                                                                         |
| `get_nodes(filters)`                          | `SELECT id, document_id, node_content, embedding FROM nodes [WHERE ...]`                                                               | full scans on vec0 work [VERIFIED]; 45 ms / 20K rows                                                                                                                                                                    |
| `query(VectorStoreQuery)`                     | `SELECT id, node_content, embedding, distance FROM nodes WHERE embedding MATCH ? AND k = ? [AND filters]` then Python-slice to `top_k` | `k = ?` is mandatory; `LIMIT` cannot be combined with `k` [VERIFIED]; results arrive distance-sorted [VERIFIED]; similarities = `1 - distance`                                                                          |
| `_build_where(filters)`                       | same EQ/IN translation, but emitting `?` placeholders + params list                                                                    | **Upgrade**: bound parameters replace today's manual `_escape()` string interpolation                                                                                                                                   |
| `get_modified_times()`                        | `SELECT document_id, modified FROM nodes` + first-seen dedupe in Python                                                                | identical logic                                                                                                                                                                                                         |
| `ensure_document_id_scalar_index()`           | no-op (delete if nothing else needs it)                                                                                                | metadata filters are evaluated in the chunk scan; nothing to create                                                                                                                                                     |
| `maybe_create_ann_index()`                    | no-op on 0.1.9                                                                                                                         | ANN (rescore/diskann) is 0.1.10-alpha territory; adopting an ANN index makes the file unreadable by 0.1.9 (one-way door), while flat tables round-trip 0.1.9 <-> 0.1.10a4 cleanly [VERIFIED]. Revisit post-0.1.10-final |
| `compact(retention_seconds)`                  | **rebuild-based compaction**, see below                                                                                                | replaces Lance MVCC cleanup                                                                                                                                                                                             |

Filter constraint surface (loud errors otherwise, [VERIFIED]): only `=, !=, <, <=, >, >=, IN` on metadata columns in KNN queries. We use only EQ/IN. Never use `NOT IN` (the vtab cannot see it; SQLite post-filters and silently under-delivers below k, asg017/sqlite-vec#116).

## Compaction: the one real behavioral difference

vec0 DELETE only flips a validity bit; space is never reclaimed, and VACUUM recovers only about half (asg017/sqlite-vec#54, #220, open; fix PRs #243/#210 unmerged). Measured: 5 delete+reinsert cycles on 2K rows grew the file 3.32 MB -> 6.56 MB; VACUUM got back to 4.94 MB. Paperless's per-document churn (every document edit is a delete+reinsert) hits this directly.

So `compact()` becomes the maintainer-endorsed rebuild (asg017/sqlite-vec#205):

```sql
CREATE VIRTUAL TABLE nodes_new USING vec0(...);
INSERT INTO nodes_new SELECT id, document_id, modified, node_content, embedding FROM nodes;
DROP TABLE nodes;
ALTER TABLE nodes_new RENAME TO nodes;  -- then VACUUM
```

This copies vectors without re-embedding, runs under the existing write FileLock, and slots into the existing `document_llmindex compact` command and the scheduled maintenance task. A cheap trigger heuristic: rebuild when `count(*) in nodes_rowids shadow` (cumulative) exceeds ~2x live rows, or just keep the existing scheduled cadence.

## Concurrency

vec0 is a plain vtab over ordinary shadow tables, so standard SQLite WAL semantics apply, and the existing architecture is already the textbook arrangement: writers serialized by `settings.LLM_INDEX_LOCK` FileLock, readers concurrent via WAL. Verified across processes: a reader during another process's open write transaction does not block and sees a consistent pre-transaction snapshot; post-commit it sees the new rows [VERIFIED]. No sqlite-vec-specific multi-process corruption, locking, or segfault reports exist in the tracker. The 0.1.10a4 cached-statement fix (#295) is a Firefox/mozStorage `sqlite3_close()` issue; CPython's `sqlite3` is unaffected, no Python-side reports.

Same caveat as the main SQLite DB: `LLM_INDEX_DIR` should not be on NFS.

## Performance expectations (measured on the 0.1.9 no-SIMD wheel)

- KNN 20K rows x 1024 dims: ~74 ms plain, ~39 ms with a metadata EQ filter.
- 100K x 768: 185 ms/query (vs 497 ms for LanceDB exact search on identical data).
- Extrapolated 500K x 1024-1536: ~0.9-1.8 s/query; 384 dims roughly 4x faster. Acceptable for suggestions/chat at the extreme tail; typical installs (low tens of thousands of chunks) are tens of ms.
- Insert: ~3,300 rows/s at 1024 dims in a single transaction.
- File size: ~raw vector size (~4.3 KB/row at 1024 dims), no compression; plus the bloat behavior above.

## Migration from the Lance store

Beta policy: re-embed. On startup/first index task: if `LLM_INDEX_DIR` contains a Lance table but no `llmindex.db`, log and queue a full rebuild, then remove the Lance directory. No cross-store vector copy, no lancedb import anywhere in the path (which is what un-breaks #12970 hosts: they currently crash at import, have no usable index, and get a fresh build).

PR #12968's migration machinery maps onto `index_meta['schema_version']`: structural migrations = create-new-table + `INSERT ... SELECT` + rename (vectors copied, no re-embed; same shape as the compaction rebuild); re-embed migrations = drop + full rebuild, jumping straight to the current version.

## Dependency changes

- Add: `sqlite-vec==0.1.9` (one ~100 KB platform wheel, zero Python deps).
- Remove: `lancedb~=0.33.0` (and its pylance/lancedb wheels, ~40 MB). `pyarrow` leaves this module; check whether anything else in the AI stack still needs it before dropping from pyproject.

## Test plan notes

- pytest-style per project convention; the store tests can run against a tmp_path DB file (or `:memory:` for pure-logic tests; extension loading works on uv-managed CPython [VERIFIED]).
- Port the existing `test_vector_store.py` surface; add dedicated tests for: upsert transactionality (no transient empty state mid-upsert from a second connection), NULL-coercion in `_row()`, k-slice behavior, EQ/IN filter correctness, compaction rebuild preserving rows byte-for-byte, vec_debug canary logging.
- The qemu matrix (`/tmp/vstore-avx-test/`) can be re-run against any future sqlite-vec bump: `qemu-x86_64 -cpu Westmere venv/bin/python candidate_test.py sqlite_vec <dir>`.

## Benchmark harness

`src/bench_vector_store.py` -- standalone head-to-head comparison run during the migration window when both `PaperlessLanceVectorStore` and `PaperlessSqliteVecVectorStore` coexist (Task 3 Phase A of the implementation plan). After Phase B replaces `vector_store.py`, the Lance import fails gracefully and only the sqlite-vec half runs (useful for post-migration baseline checks).

```bash
cd src
uv run python bench_vector_store.py            # auto-generates bench_data.pkl on first run
uv run python bench_vector_store.py --regenerate  # force re-embed
```

**Phase 1 (data generation, skipped if `bench_data.pkl` exists):** Faker generates `--n-docs` (default 2000) fake documents -- title, body, correspondent, ISO timestamp. Each body is split into `--chunks-per-doc` (default 3) equal-length chunks (~6000 total nodes). A warm-up embed call fires before generation to ensure the model is resident in GPU. All chunk texts are embedded via Ollama `/api/embed` in batches of 32 and saved to `bench_data.pkl`. Faker seed 42 for reproducibility.

**Phase 2 (benchmark):** Each store runs in an isolated `tempfile.TemporaryDirectory()`. Query vectors are drawn reproducibly from the corpus (every 10th node, wrapping).

| Operation                                 | Reps | Metric                |
| ----------------------------------------- | ---- | --------------------- |
| `add()` bulk insert                       | 1    | total time            |
| `query()` plain                           | 50   | p50 / p95             |
| `query()` filtered (IN on 20% of doc IDs) | 50   | p50 / p95             |
| `get_modified_times()`                    | 20   | p50                   |
| `upsert_document()`                       | 50   | p50 / p95             |
| `compact()`                               | 1    | total time            |
| File size                                 | --   | pre- and post-compact |

**CLI flags:** `--n-docs` (2000), `--chunks-per-doc` (3), `--data-file` (`bench_data.pkl`), `--regenerate`, `--ollama-url` (`http://192.168.1.87:11434`), `--embed-model` (`qwen3-embedding:4b`), `--query-iters` (50).

**Dependencies:** `faker` and `httpx` must be available (`uv add --dev faker httpx` if not already installed).

## Risk register (from the 2026-06-10 issues audit)

| Risk                                        | Ref                                     | State          | Disposition                                                                                                                                       |
| ------------------------------------------- | --------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0.1.10+ wheels bake AVX, no dispatch        | release CI change, verified on 0.1.10a4 | current        | Pin 0.1.9; vec_debug canary; upstream ask before any bump                                                                                         |
| DELETE never reclaims space; VACUUM ~50%    | #54, #220                               | open           | Rebuild-based `compact()` above                                                                                                                   |
| INSERT OR REPLACE broken on vec0            | #259                                    | open           | Use DELETE+INSERT in txn (design already does)                                                                                                    |
| NULL metadata rejected                      | #141                                    | open           | Sentinel `""` coercion (already current behavior)                                                                                                 |
| Partition-key IN returns k per partition    | #142                                    | open           | Avoided: document_id is a metadata column                                                                                                         |
| NOT IN silently under-delivers              | #116                                    | open           | Never emit NOT IN                                                                                                                                 |
| Locale strtod breaks JSON vector parsing    | #241                                    | open           | Always BLOB-bind vectors                                                                                                                          |
| Single weekend maintainer; fix PRs languish | #226                                    | open           | Mitigated by Mozilla sponsorship + Firefox vendoring (release-train consumer); pin + vendor-from-source remains the escape hatch (no sdist: #211) |
| ANN index = one-way file format             | 0.1.10 alphas                           | —              | Do not adopt ANN until 0.1.10 final + flag audit                                                                                                  |
| Long-TEXT metadata DELETE bug               | #274                                    | fixed in 0.1.9 | Floor requirement `>=0.1.9` already implied by pin                                                                                                |
