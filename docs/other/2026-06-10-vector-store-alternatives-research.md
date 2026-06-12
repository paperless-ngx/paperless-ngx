# Vector Store Alternatives to LanceDB (issue #12970 research)

Date: 2026-06-10
Trigger: [paperless-ngx#12970](https://github.com/paperless-ngx/paperless-ngx/issues/12970), LanceDB wheels SIGILL at import on non-AVX2 x86_64 CPUs.
Method: deep-research web sweep (22 sources, 25 claims adversarially verified, 21 confirmed / 4 refuted) plus local empirical testing of every candidate wheel under qemu-user CPU emulation, plus a brute-force latency benchmark.

## TL;DR

1. **Waiting on upstream is not a plan.** The AVX2 baseline in LanceDB wheels is a deliberate, maintainer-defended build choice. The compat tracking issue (lance#2195) was closed as Stale / not_planned on 2026-01-22, the runtime-dispatch PR (lance#6630) is unmerged, and `lancedb-compat` on PyPI is a 404.
2. **faiss is no longer a safe fallback either.** The new Meta-published faiss-cpu 1.14.2 wheel ships a single AVX2 binary and SIGILLs on pre-Haswell CPUs (verified empirically). Only the archived community 1.13.2 wheel still carries the generic fallback.
3. **sqlite-vec is the best structural replacement.** Pure C, zero dependencies, plain SQLite file, metadata columns with SQL filtering, passes the pre-AVX2 emulation test, and brute-force search at 100K x 768 dims is ~185 ms/query, faster than LanceDB exact search on the same data.
4. **Recommendation:** short-term, ship a pre-flight CPUID check that disables AI cleanly instead of crashing. Real fix, port `PaperlessLanceVectorStore` to a sqlite-vec backend (the method surface maps almost 1:1 onto SQL); decide then whether sqlite-vec replaces LanceDB outright or serves as the non-AVX2 fallback.

## Constraints a replacement must satisfy

From PR #12944 (the FAISS -> LanceDB switch) and the current `PaperlessLanceVectorStore` surface:

- Embedded / file-based under `LLM_INDEX_DIR`, no extra service container.
- Published wheels must run on pre-Haswell x86_64 (no baked-in AVX2) and on arm64.
- Multi-process: Celery workers + granian web workers; writers already serialized via FileLock, readers must not be blocked.
- Per-document upsert/delete; metadata filtering (EQ / IN on `document_id`).
- Real deletes (not tombstone-forever), not loading the whole index into memory.
- Scale target ~1K-500K chunks of f32 embeddings (384-1536 dims); exact search acceptable below ~100K rows.
- Wrappable behind the existing llama-index `BasePydanticVectorStore` subclass shape.

## Empirical SIGILL matrix (qemu-user 8.2.2)

Each candidate ran a real insert + top-k search workload (50 vectors, 384 dims) natively and under two emulated CPUs. Host: Xeon E5-2683 v4 (Broadwell, AVX2), Python 3.12, manylinux x86_64 wheels as published on PyPI 2026-06-10.

- `Westmere` = SSE4.2, no AVX. Same ISA class as the Atom C3758 from issue #12970.
- `SandyBridge` = AVX, no AVX2. The Sandy/Ivy Bridge users in the upstream reports.

| Package                     | Version | Native | Westmere              | SandyBridge           |
| --------------------------- | ------- | ------ | --------------------- | --------------------- |
| lancedb                     | 0.33.0  | PASS   | **SIGILL**            | **SIGILL**            |
| sqlite-vec                  | 0.1.9   | PASS   | PASS                  | PASS                  |
| faiss-cpu (Meta wheel)      | 1.14.2  | PASS   | **SIGILL**            | **SIGILL**            |
| faiss-cpu (community wheel) | 1.13.2  | PASS   | PASS                  | PASS                  |
| usearch                     | 2.25.3  | PASS   | PASS                  | PASS                  |
| duckdb                      | 1.5.3   | PASS   | PASS                  | PASS                  |
| chromadb                    | 1.5.9   | PASS   | PASS                  | PASS                  |
| qdrant-client (local mode)  | 1.18.0  | PASS   | PASS                  | PASS                  |
| voyager                     | 2.1.0   | PASS   | PASS                  | PASS                  |
| milvus-lite                 | 3.0     | PASS   | **SIGILL** (via deps) | **SIGILL** (via deps) |
| numpy brute force           | 2.4.6   | PASS   | PASS                  | PASS                  |

The lancedb crash reproduces issue #12970 exactly (SIGILL during import), which validates the harness.

Dependency-level isolation of the failures:

- **pyarrow 24.0.0 passes on both emulated CPUs.** Its runtime dispatch is sound; the lancedb crash is entirely the lance Rust core.
- **pandas 3.0.3 requires AVX**: SIGILL at import on Westmere, passes on SandyBridge. (numpy 2.4.6 alone passes everywhere.)
- **milvus-lite 3.0 itself is pure Python** (the v3.0.0 release, 2026-05-13, is an explicit pure-Python rewrite; the wheel contains no native code). The SIGILLs come from its mandatory dependency stack: pandas kills it at import on Westmere, and on SandyBridge something in the pymilvus client init path (69 loaded C extensions, pandas/pyarrow/grpcio/protobuf) still executes an illegal instruction.

### faiss-cpu wheel forensics

The portability regression is visible in the wheel contents:

- 1.13.2 (community faiss-wheels, now archived): `_swigfaiss.abi3.so` + `_swigfaiss_avx2.abi3.so` + `_swigfaiss_avx512.abi3.so`, with a runtime loader that picks by CPUID. Passes on all emulated CPUs.
- 1.14.2 (first Meta-published wheel): a single `_swigfaiss.abi3.so` (6.1 MB) + `libfaiss.so` (14 MB). No generic variant exists, so the loader has nothing to fall back to. SIGILL on both pre-AVX2 CPUs.

Pinning to 1.13.2 means pinning to an archived repo, a dead end. Worth reporting upstream to facebookresearch/faiss as a packaging regression, but do not build paperless's plan on it.

## Brute-force latency (native, 100K vectors x 768 dims, top-10)

| Store                                     | Insert 100K | Query      |
| ----------------------------------------- | ----------- | ---------- |
| sqlite-vec 0.1.9 (file)                   | 18.0 s      | **185 ms** |
| lancedb 0.33.0 exact, no ANN index (file) | 9.1 s       | 497 ms     |
| numpy in-memory                           | n/a         | 262 ms     |

100K x 768 is already a large paperless install (the PR #12944 author's own index was ~40-53 MB, roughly 15-20K chunks). Scaling linearly, 500K rows lands near ~1 s/query for sqlite-vec, slow but usable for suggestions/chat; below 100K it is comfortably interactive. Exact search also means no recall loss, no ANN index builds, and no compaction cycle.

## Per-candidate assessment

### sqlite-vec 0.1.9 — recommended

- **ISA:** pure C with no SIMD baseline assumptions; passed Westmere and SandyBridge. No SIGILL reports found upstream.
- **Fit:** the `vec0` virtual table gives metadata columns (since v0.1.6) and partition keys, so `document_id` EQ/IN filtering is a SQL WHERE clause, the same shape as the current `_build_where()`. Persistence is one SQLite file; the existing FileLock writer serialization plus WAL mode covers Celery + granian (WAL readers do not block on the writer).
- **Method mapping:** `merge_insert` -> DELETE + INSERT in one transaction; `compact()` -> no-op or `PRAGMA incremental_vacuum`; stored model name -> a one-row meta table; `get_modified_times()` -> `SELECT document_id, modified`; `vector_dim()` -> declared column type. Real deletes work (`DELETE FROM t WHERE ...`).
- **Project health (verified 2026-06-10):** commit concentration is real, asg017 has 441 commits and the next contributor 5, and the version is still pre-1.0 (v0.1.9 stable, v0.1.10-alpha.4 of 2026-05-18 current). But the institutional backing is substantial: sqlite-vec is a Mozilla Builders project (Mozilla is the main sponsor, announced June 2024, plus Fly.io / Turso / SQLite Cloud / Shinkai), and **Firefox vendors and ships it**: `third_party/sqlite3/ext/sqlite-vec` in mozilla-central is pinned to v0.1.10-alpha.4 (vendored within days of release), gated by `MOZ_SQLITE_VEC0_EXT` for browser builds, with its own Bugzilla component (Core :: SQLite and Embedded Database Bindings) and vendoring automation. A project on the Firefox release train is unlikely to silently die; Mozilla has both the motive and the means to maintain it.
- **ANN is no longer "never":** the vendored tree and the v0.1.10 alpha commits show IVF (+ k-means, DiskANN, rescore) actively in development (`sqlite-vec-ivf.c`, `sqlite-vec-diskann.c`, "Rename all IVF shadow tables" etc.). The original report claim that ANN never shipped (issue #25) is true for stable releases but stale as a trajectory: the >100K-row story is being built right now, likely Mozilla-driven.
- **Risks:** brute-force only in stable releases today; effectively one code author; pre-1.0 versioning. The vec0 KNN operator support for `IN` on metadata vs partition-key columns should be verified during implementation.
- **Version pin warning (2026-06-10 follow-up audit):** the 0.1.9 wheel is built with no SIMD flags (verified via `vec_debug()` and qemu), but the **0.1.10-alpha.4 wheel bakes in `-mavx` with no runtime dispatch** and can SIGILL on AVX-less CPUs, the same failure mode as LanceDB. Pin `==0.1.9` and audit wheel flags before any bump. Full mapping + risk register: `docs/superpowers/specs/2026-06-10-sqlite-vec-vector-store-design.md`.
- **Deps:** zero. Removes lancedb + pylance (and their ~40 MB of wheels) if it replaces rather than supplements.

### faiss-cpu — was the pre-LanceDB store; now disqualified by packaging

Runtime dispatch worked in the community wheels, but paperless moved off FAISS in PR #12944 for good reasons (no metadata filtering, no real deletes, full in-memory docstore), and the 1.14.2 Meta wheels reintroduce the exact SIGILL this research is trying to escape. Going back is strictly worse than LanceDB today.

### usearch 2.25.3 / voyager 2.1.0 — ISA-safe but structurally poor fits

Both pass emulation (usearch via SimSIMD's compile-everything-dispatch-at-runtime design). Neither stores metadata or payloads: filtering is predicate callbacks (usearch) or absent (voyager), persistence is whole-index save/load files, and node content would need a SQLite sidecar maintained by the wrapper. That is the same integration work as FAISS with less ecosystem support. Only attractive if ANN performance at >500K rows ever becomes the binding constraint.

### ChromaDB 1.5.9 — ISA-safe (new data), blocked on multi-process

Passed both emulated CPUs (the web sweep had no surviving verified claims on Chroma; this is new evidence). But embedded `PersistentClient` does not support concurrent access from multiple processes (Chroma's documented system constraint), which Celery + granian violate immediately; the supported concurrent mode is the Chroma server, i.e. an extra container. Also the heaviest dependency tree of the candidates. Disqualified.

### DuckDB 1.5.3 — ISA-safe, blocked on file locking

Passed both emulated CPUs; `array_distance` over a FLOAT[n] column works fine for exact search and SQL filtering. But a DuckDB file allows either one read-write process or many read-only processes, not both at once, so granian readers would be locked out during Celery writes (today's LanceDB readers are lock-free, and SQLite WAL readers are too). The VSS/HNSW extension's persistence is still marked experimental. Disqualified for this use.

### qdrant-client local mode — ISA-safe, hard multi-process lock

Local mode is numpy-based and passed emulation, but it takes an exclusive portalocker lock on the storage dir; a second process gets `RuntimeError` directing you to the Qdrant server. Maintainer-confirmed as out of scope (qdrant-client#765). Disqualified.

### milvus-lite 3.0 — pure Python now, still disqualified

v3.0.0 (2026-05-13) rewrote Milvus Lite in pure Python (custom LSM-style engine: memtable/WAL/segments/manifest, no native code in the wheel), and the v2-era exclusive-lock behavior is gone: a second process can open the same DB concurrently (verified locally, no lock files created). Two corrections to the web-research-era assessment, in its favor. It still fails for paperless: the mandatory pymilvus dependency stack (pandas 3.x, pyarrow, grpcio, protobuf) SIGILLs on both pre-AVX2 test CPUs, so the portability problem is merely relocated, and the dependency weight is the largest of any candidate. Its concurrent-writer safety through the custom storage engine is also unproven (no documented multi-process write story for the rewrite).

### numpy / llama-index SimpleVectorStore — portable but regressive

Always works, but it is the load-everything-into-RAM model that PR #12944 deliberately left behind. Acceptable only as a last-resort fallback tier.

### SQLite team's Vec1 (evaluated 2026-06-10, post-report; promising later, not now)

The SQLite project's own vector extension (https://sqlite.org/vec1, single `vec1.c`, IVFADC+OPQ ANN plus exact NN/flat modes, L2+cosine, metadata columns with in-index filter pushdown, streaming filtered queries). Why it loses today despite the gold-standard maintainership:

1. **Pre-release**: the project page says "No further features are required before first release. But: Testing is insufficient" and "almost all paths require optimization". No first release has happened.
2. **The same SIGILL trap, documented as the build model**: recommended build is `-mavx2 -mfma`, and the docs state binaries built that way "will not work on systems that lack them". A multi-arch Makefile target exists, but compile-time SIMD selection is the design; shipping it safely for #12970-class CPUs is on the packager.
3. **No distribution**: no PyPI wheels, no package at all; paperless would vendor and compile it for Docker AND ask bare-metal users to do the same.
4. **Filter pushdown has no `IN`**: in-index filtering supports `<, >, =, >=, <=, IS` only. The store's primary query is `document_id IN (...)`; with vec1 that means streaming queries + JOIN post-filtering, with the manual's own documented silently-reduced-K pitfall.
5. Rowid-keyed only (no TEXT pk; node UUIDs need a mapping table) and metadata columns are "optimized for small values (say 8 bytes)", so the node-content JSON needs a sidecar table anyway. ANN mode requires offline `vec1_train()` model training, retraining as data evolves, and rerank discipline; the untrained exact modes are usable but then vec1's distinctive ANN advantage is unused.

Worth re-evaluating after its first release if it grows a packaging story; the store-behind-`BasePydanticVectorStore` design and the migration machinery make a later vec1 backend the same bounded port as this one.

### Vectorlite (dark horse, not tested)

SQLite extension wrapping hnswlib with Google Highway runtime dispatch; v0.2.0 explicitly fixed an AVX2-wheel crash, the exact failure mode at issue. Verification of its arm64 wheels and maintenance health was inconclusive in the web sweep and it was not in the local matrix. Could be revisited if sqlite-vec's lack of ANN ever bites.

## Recommendation

**Step 1 (ship now, fixes #12970):** pre-flight CPU check before any `lancedb` import: read `/proc/cpuinfo` flags (or CPUID via py-cpuinfo) for `avx2`; on failure, disable the AI feature with a clear system-check error / log line instead of crashing celery and granian. This matches the resolution the issue itself suggests and is independent of any store decision. A SIGILL cannot be caught, so the check must gate the import.

**Step 2 (the real fix): port the store to sqlite-vec.** `PaperlessLanceVectorStore` was designed as a thin, self-contained adapter and that pays off here: every method maps directly onto SQL against a `vec0` table plus a small meta table. Two deployment shapes:

- **(a) Full replacement** (my lean): one code path, one store to test, drops the lancedb dependency entirely, plain SQLite file artifact, and the benchmark shows exact search beating LanceDB's exact path at 100K rows. Costs: no ANN above ~100K rows (about ~1 s/query at 500K), and a one-time index rebuild on upgrade (already a routine paperless operation, `document_llmindex rebuild`).
- **(b) Dual backend**: keep LanceDB on AVX2 hosts, sqlite-vec on the rest, selected by the step-1 CPU check. Preserves ANN for very large installs, but doubles the test/maintenance surface and keeps the lancedb dependency for everyone.

Given realistic paperless index sizes (tens of thousands of chunks, not hundreds of thousands) and the cost of maintaining two stores, (a) is the better trade unless telemetry/user reports say otherwise. If lance#6630 eventually merges and lancedb wheels gain runtime dispatch, that decision can be revisited with no architectural debt.

**Migration machinery (PR #12968) carries over.** The in-place LanceDB migration framework in paperless-ngx#12968 (structural migrations vs full re-embed, so users paying for embeddings only re-pay when the vectors themselves change) is needed regardless of store, and its split survives a backend swap intact:

- On sqlite-vec, "structural" migrations are SQL DDL. vec0 virtual tables do not support arbitrary `ALTER TABLE`, so the standard pattern is create-new-table + `INSERT INTO ... SELECT` + drop + rename, which copies vectors without re-embedding, the exact same cost class as LanceDB's `add_columns`/`alter_columns`. A schema version lives in the same meta table as the embedding model name.
- The framework is also the natural vehicle for the store swap itself: on AVX2 hosts, a one-time cross-store migration can read rows out of the existing Lance table and insert them into sqlite-vec with **no re-embedding** (vectors copy as-is). Only non-AVX2 hosts, which today crash outright and therefore have no usable index, need a fresh rebuild.

## Caveats and open questions

- qemu TCG faithfully reproduces CPUID-gated SIGILLs but is not a performance environment; latency numbers are native-host only.
- Westmere lacks AVX entirely, slightly stricter than the Atom C3758 (Goldmont, SSE4.2) in the issue; SandyBridge covers the AVX-but-no-AVX2 reports. Both fail lancedb, so the conclusion is insensitive to the exact tier.
- Chroma multi-process and DuckDB locking conclusions come from documentation and upstream issues, not local tests.
- sqlite-vec: verify `IN` operator support on `vec0` metadata vs partition-key columns during implementation; confirm WAL-mode behavior on the network filesystems some users put `LLM_INDEX_DIR` on (same caveat already applies to SQLite as the main DB).
- faiss-cpu 1.14.2's missing generic build should be reported to facebookresearch/faiss; if Meta restores variant bundling, faiss still would not beat sqlite-vec here (no metadata, no real deletes).

## Sources (key)

- https://github.com/paperless-ngx/paperless-ngx/issues/12970 (downstream bug)
- https://github.com/lance-format/lance/issues/2195 (closed Stale / not_planned 2026-01-22)
- https://github.com/lancedb/lancedb/issues/3324, https://github.com/lance-format/lance/pull/6630 (upstream fix attempts, unmerged)
- https://alexgarcia.xyz/blog/2024/sqlite-vec-stable-release/index.html, https://alexgarcia.xyz/blog/2024/sqlite-vec-metadata-release (sqlite-vec capabilities)
- https://github.com/asg017/sqlite-vec/issues/25 (ANN, never shipped)
- https://github.com/faiss-wheels/faiss-wheels (archived; "Starting with faiss v1.14.2, the upstream faiss repository officially supports PyPI wheel distribution")
- https://github.com/ashvardanian/SimSIMD (runtime dispatch design)
- https://github.com/qdrant/qdrant-client/issues/765, https://github.com/milvus-io/milvus-lite/issues/264 (multi-process locks; the milvus one is v2-era, superseded by the v3 pure-Python rewrite)
- https://github.com/milvus-io/milvus-lite/releases/tag/v3.0.0 (pure-Python rewrite, 2026-05-13)
- https://cookbook.chromadb.dev/core/system_constraints/ (Chroma single-process embedded constraint)
- https://hacks.mozilla.org/2024/06/sponsoring-sqlite-vec-to-enable-more-powerful-local-ai-applications/ (Mozilla Builders sponsorship)
- https://github.com/mozilla-firefox/firefox/tree/main/third_party/sqlite3/ext/sqlite-vec (Firefox vendoring, pinned v0.1.10-alpha.4, `MOZ_SQLITE_VEC0_EXT` in storage/moz.build)
- https://github.com/paperless-ngx/paperless-ngx/pull/12968 (in-place index migration machinery, store-agnostic in design)
- Local artifacts: `/tmp/vstore-avx-test/` (candidate_test.py, run_matrix.sh, bench_sqlitevec.py)
