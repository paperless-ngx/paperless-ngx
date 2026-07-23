# Archive AI chat: hybrid (lexical + vector) retrieval

Date: 2026-07-23
Status: Draft, not yet implemented
Related: [GitHub issue #13234](https://github.com/paperless-ngx/paperless-ngx/issues/13234)

## Problem

The archive-wide AI chat (`ChatStreamingView` with no `document_id`, backed by
`stream_chat_with_documents()` in `src/paperless_ai/chat.py`) retrieves context
purely via dense-vector similarity search: `VectorIndexRetriever` embeds the
user's question and does cosine-similarity nearest-neighbor search over chunk
embeddings, with a hardcoded `similarity_top_k` of 5 (`CHAT_RETRIEVER_TOP_K`,
`chat.py:20`) and no similarity cutoff.

Dense embeddings are known to perform poorly on exact keyword, rare/foreign
word, and numeric-string matching (e.g. a compound German word like
"Herdwächter", or a specific invoice number). For these queries, the
correct document's chunk often does not rank in the global top-5 nearest
neighbors across the whole archive, while Paperless's existing Tantivy
full-text index (used by normal search) finds it immediately. The chat's
"use only the context above" prompt then causes the LLM to confidently deny
the document exists and cite whatever unrelated chunks it was given.

Per-document chat (`document_id` set) is scoped to one document's own chunks,
so it can only ever retrieve the wrong _chunk within_ the right document —
it can't surface an entirely wrong document — which is why the bug is far
more visible in the archive-wide case.

## Goal

Supplement vector retrieval with lexical (Tantivy) retrieval so that exact
keyword/number queries reliably surface the right document(s), matching what
normal Paperless search already finds, without a large increase in
implementation complexity.

## Non-goals

- Re-ranking models, learned fusion, or reciprocal-rank-fusion scoring.
- Changing per-document chat's existing behavior beyond making it go through
  the same retriever type (see "Scope" below) — it should not regress.
- Changing chunking, embedding model behavior, or the embedding query
  task-prefix issue noted during investigation (out of scope for this fix;
  may be worth a separate follow-up).
- Similarity cutoffs / dropping low-confidence vector hits (a related but
  separate improvement; not part of this design).

## Design

### Overview

Introduce a `HybridRetriever` that wraps the existing vector retrieval and
adds a lexical-hit path via the Tantivy backend, reusing the query embedding
already computed for vector search wherever possible.

### Flow

1. Run today's `VectorIndexRetriever.retrieve(query_str)` unchanged: up to
   `CHAT_RETRIEVER_TOP_K` (5) nodes by cosine similarity, filtered to the
   caller's permitted document IDs.
2. Call `documents.search.get_backend().search_ids(query_str, user=user,
search_mode=SearchMode.TEXT, limit=CHAT_LEXICAL_TOP_K)` — the same idiom
   already used in `views.py:3522` — to get lexical document-ID matches.
   `user` is `None` for superusers and `request.user` otherwise, matching the
   existing permission pattern (`views.py:3521`). Intersect the returned IDs
   with the caller-provided `documents` set so results never exceed what the
   caller already permission-scoped (this is what makes the retriever safe
   to use for both the archive-wide and single-document cases).
3. For lexical-hit document IDs not already represented among step 1's
   nodes, issue **one `store.query()` call per missing document** (not a
   single batched call across all of them), each with `similarity_top_k=1`
   and a metadata filter restricted to that one document ID, reusing the
   same query embedding. This is deliberate: `PaperlessSqliteVecVectorStore
.query()` runs a single global `vec0` KNN search over the WHERE-filtered
   rows (`vector_store.py:409-434`) — it does not partition top-k per
   document — so a single batched call across N lexical-hit documents with
   `top_k=N` could return several chunks from one document and none from
   another. Per-document calls are the only way to guarantee each lexical
   hit contributes its actual best-matching chunk. This means up to
   `CHAT_LEXICAL_TOP_K` extra small store queries; acceptable since they're
   local sqlite-vec lookups, not network calls.
   - **Embedding reuse mechanism:** compute the query embedding once, up
     front, into a `QueryBundle(query_str, embedding=...)`. Pass that same
     `QueryBundle` to both `VectorIndexRetriever.retrieve()` (step 1) and
     each per-document `store.query()` (step 3). `retrieve(query_str)` on
     its own re-embeds internally with no way to extract the vector
     afterward, so the retriever must be driven by an explicit
     pre-embedded `QueryBundle`, not a raw query string, for the reuse to
     be real rather than a second silent embedding call.
4. Merge the node lists from steps 1 and 3 with a **deterministic,
   priority-preserving rule**: keep all of step 1's vector nodes; append
   step 3's lexical-added nodes (in Tantivy hit order), skipping any
   duplicate node id already present from step 1. If the combined count
   exceeds `CHAT_MAX_NODES` (8), truncate from the _end of the lexical
   additions_ — vector nodes are never evicted to make room for a lexical
   one. This keeps the fix additive: a working vector-only answer can only
   gain context, never lose a hit it already had.
5. Return the merged list — vector nodes first (similarity order), then
   surviving lexical additions (Tantivy order) — as the retriever's
   `_retrieve()` result. Everything downstream — `RetrieverQueryEngine`,
   streaming synthesis, `_get_document_references` — is unchanged; it just
   consumes whatever `HybridRetriever.retrieve()` returns, exactly as it
   consumed `VectorIndexRetriever` before.

### New constants (`chat.py`)

- `CHAT_LEXICAL_TOP_K = 5` — how many Tantivy document hits to consider.
- `CHAT_MAX_NODES = 8` — cap on total merged nodes handed to the synthesizer.

### Components

- **New:** `HybridRetriever(BaseRetriever)` in a new module,
  `src/paperless_ai/retrieval.py`. Constructor takes: the underlying vector
  retriever, the open `store` (for the per-document filtered `store.query()`
  calls), the permission-scoped document ID filter, and `user` (for the
  Tantivy permission check). `_retrieve()` builds one `QueryBundle` with a
  precomputed embedding and drives both the vector retriever and the
  per-document lexical lookups from it (see flow step 3).
- **Changed:** `_stream_chat_with_documents()` constructs a `HybridRetriever`
  instead of handing `VectorIndexRetriever` directly to
  `RetrieverQueryEngine.from_args()`; the vector retriever is still built
  internally exactly as today and used as step 1 of the hybrid flow.
- **Changed:** `stream_chat_with_documents()` / `_stream_chat_with_documents()`
  gain a `user` parameter, threaded from `ChatStreamingView.post`
  (`views.py:2268`) using the same `None`-for-superuser convention already
  used elsewhere in `views.py`.

### Scope: applies to both chat modes

The hybrid retriever is used unconditionally, for both archive-wide and
single-document chat. In the single-document case the Tantivy lookup is
naturally restricted to that one document (via the intersection in step 2),
so it's a no-op if the lexical search doesn't match, and it can still help
surface the right chunk within that document for keyword-heavy questions
that vector similarity alone might miss.

### Error handling

- If the Tantivy backend raises or the index isn't available for some
  reason, the lexical step should degrade gracefully to vector-only results
  (log and continue) rather than failing the whole chat response — chat
  already wraps everything in a try/except at the `stream_chat_with_documents`
  level (`chat.py:82-87`), but the lexical addition should not, by itself,
  turn a previously-working vector-only answer into an error.

### Testing

- Unit tests for `HybridRetriever` (new `src/paperless_ai/tests/` module),
  mocking the vector retriever and the Tantivy backend, covering:
  - Lexical-only hits (not found by vector search) are included via the
    per-document `store.query()` calls, one chunk per lexical-hit document.
  - Multiple lexical-hit documents each contribute their own best chunk
    (guarding against the batched-query bug this design deliberately avoids —
    see flow step 3).
  - Dedup: a node found by both paths appears once.
  - Cap eviction order: when combined hits exceed `CHAT_MAX_NODES`, all
    vector nodes from step 1 survive and only excess lexical additions are
    trimmed.
  - Merge ordering: vector nodes precede lexical additions in the returned
    list.
  - Permission scoping: lexical hits outside the caller's permitted
    `documents` set are excluded even if Tantivy would otherwise return them.
  - Graceful degradation when the Tantivy backend errors.
- An integration-style test reproducing the bug report's shape: seed
  documents where a rare keyword/number's document scores low on pure vector
  similarity but is exactly matched lexically; verify the merged retrieval
  includes it and that per-document chat is unaffected when the lookup finds
  nothing new.

## Open questions / follow-ups (not blocking this design)

- Whether to also add a similarity cutoff for the vector path, so low-
  confidence vector-only hits are dropped rather than always filling out
  `CHAT_RETRIEVER_TOP_K` — discussed during investigation but explicitly
  scoped out of this design.
- The embeddinggemma query/document task-prefix mismatch noted during
  investigation (`indexing.py` `truncate_embedding_query`) — a separate,
  model-configuration-level issue.
