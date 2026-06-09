# AI Suggestions: Inject existing taxonomy as candidates

**Status:** Design (v3 — RAG-sourced, node metadata)
**Date:** 2026-05-20
**Updated:** 2026-06-09 (v3: switch from frequency DB queries to node metadata from RAG retrieval)
**Related:** [Discussion #12787](https://github.com/paperless-ngx/paperless-ngx/discussions/12787)
**Branch target:** `dev`
**Depends on:** `2026-06-09-node-metadata-enrichment.md` (adds `storage_path`, `filename`, `asn` to node metadata; must land first)

## Problem

AI Suggestions currently asks the LLM for free-form tag/document-type/correspondent/storage-path names, then reconciles via `difflib` fuzzy matching (cutoff 0.8) in `paperless_ai/matching.py`. This works for typos but not for semantic equivalents:

- `blood test` does not fuzzy-match `Bloodwork`
- `IRS` does not fuzzy-match `Taxes`
- `doctor visit` does not fuzzy-match `Medical`

Result: the LLM invents new metadata names that duplicate existing taxonomy entries.

## Goal

Tell the LLM what already exists, so it can prefer existing names verbatim. Fuzzy matching becomes the fallback for typos and for legitimately novel suggestions, not the primary semantic-equivalence mechanism.

Non-goals: changing the LLM client, embedding model selection, or RAG retrieval. Replacing fuzzy matching entirely. Custom-field option values. Frequency-based DB queries (superseded by RAG-sourced approach).

## Approach

Hints are sourced from the LanceDB node metadata of the similar documents already retrieved for RAG context — no separate DB queries, no new user-facing configuration. The feature is **gated on `llm_embedding_backend`**: when no embedding backend is configured, no hints are built and today's behavior is unchanged.

LanceDB nodes already store `tags`, `correspondent`, `document_type`, `title`, and date fields per document (see `indexing.py:build_document_node`). `storage_path` is not currently stored; this feature adds it via a structural schema migration (no re-embed required).

For each suggestion request (when embedding backend is on):

1. Run the ANN retrieval once → get raw `NodeWithScore` results.
2. Extract taxonomy from the node metadata: `tags` (list), `document_type`, `correspondent`, `storage_path`.
3. Inject the unique names into the LLM prompt as "Available <category>" blocks.
4. Pass the same name sets to `matching.py` as `hinted_names` so an exact normalized match short-circuits past fuzzy.

When embedding backend is off → `hints = None` → prompt and matching are identical to today.

## Components

### `paperless_ai/indexing.py` (modify — `retrieve_similar_nodes`)

Extract the shared retriever logic from `query_similar_documents` into a new lower-level function:

```python
def retrieve_similar_nodes(
    document: Document,
    document_ids: Iterable[int | str] | None = None,
    top_k: int = 5,
) -> list["NodeWithScore"]:
    """Run ANN retrieval and return raw NodeWithScore results."""
    ...
```

Refactor `query_similar_documents` to call `retrieve_similar_nodes` and convert to ORM objects (behavior unchanged). The taxonomy hints path calls `retrieve_similar_nodes` directly — no DB round-trip, no second ANN query.

### `paperless_ai/taxonomy.py` (new)

```python
class TaxonomyHints(TypedDict):
    tags: list[str]
    document_types: list[str]
    correspondents: list[str]
    storage_paths: list[str]

def build_taxonomy_hints_from_nodes(nodes: list["NodeWithScore"]) -> TaxonomyHints: ...
def get_taxonomy_hints_for_document(document: Document, user: User | None) -> TaxonomyHints | None: ...
def format_hints_for_prompt(hints: TaxonomyHints) -> str: ...
```

`get_taxonomy_hints_for_document`:

- Returns `None` immediately if `AIConfig().llm_embedding_backend` is falsy.
- Applies the same owner-aware document ID filter as `get_context_for_document` (`get_objects_for_user_owner_aware(user, "view_document", Document)` when `user` is not `None`; unfiltered otherwise).
- Calls `retrieve_similar_nodes(document=document, document_ids=visible_document_ids)`.
- Passes results to `build_taxonomy_hints_from_nodes`.

`build_taxonomy_hints_from_nodes(nodes)`:

- Extracts from each `node.metadata`: `tags` (list), `document_type` (str | None), `correspondent` (str | None), `storage_path` (str | None).
- Collects unique values across all nodes, sorted. Empty/`None` values skipped.
- Returns a `TaxonomyHints`. No cap — naturally bounded by `top_k=5` in retrieval.

`format_hints_for_prompt` emits one `Available <category>:` block per non-empty category. Empty categories produce no block (avoid prompting the LLM with "Available tags: (none)"). A single instruction line follows:

```
Prefer existing names from these lists verbatim. Only propose a new value
if none of the existing names fits.
```

### `paperless_ai/ai_classifier.py` (modify)

> **Note (updated 2026-06-09):** Current signatures after #12894 and #12944:
>
> - `build_prompt_without_rag(document: Document, config: AIConfig) -> str`
> - `build_prompt_with_rag(document: Document, config: AIConfig, user: User | None = None) -> str`
> - `get_ai_document_classification(document, user, output_language: str | None = None) -> dict`
>
> `build_localization_prompt` (added in #12894) runs after the LLM call and does **not** interact with taxonomy hints — hints inject into the base prompt only, before the LLM call.

Both `build_prompt_without_rag` and `build_prompt_with_rag` accept a new optional `hints: TaxonomyHints | None = None` parameter. When non-`None`, `format_hints_for_prompt(hints)` is spliced in before the "Analyze the following document" instruction. When `None` (default), the prompt is built as today.

`get_ai_document_classification(document, user, output_language: str | None = None, hints: TaxonomyHints | None = None)` accepts the same optional `hints` and forwards it to the prompt builder. Return shape **unchanged** (`dict`). Callers in tests pass `hints=None` (or omit) to preserve existing behavior.

### `paperless_ai/matching.py` (modify)

- `_match_names_to_queryset(names, queryset, attr, hinted_names: set[str] | None = None)`:
  - Normalization unchanged.
  - Exact-match-on-full-queryset behavior unchanged (always tried first).
  - When `hinted_names` is provided and the LLM-returned name (normalized) matches a hinted name (normalized) → treated as exact-only; fuzzy is skipped for that name.
  - When `hinted_names` is `None` or the name isn't in it → existing 0.8 fuzzy fallback runs.
- `match_tags_by_name(names, user, hinted_names=None)` etc. — optional kwarg, backward compatible.

### `documents/views.py` (modify)

The suggestion endpoint (around line 1498) is the single production caller of `get_ai_document_classification` and the call site for `match_*_by_name`. Update it to:

1. Build hints: `hints = get_taxonomy_hints_for_document(doc, request.user)` — returns `None` when embedding backend is off; no additional config check needed in the view.
2. Pass `hints` into the classifier: `parsed = get_ai_document_classification(doc, request.user, output_language, hints=hints)` — `output_language` is already resolved at this point (`views.py:1472`).
3. Pass `hinted_names=set(hints["tags"])` (etc., one per category, or `None` when `hints` is `None`) into each `match_*_by_name` call.

**Cache interaction:** the AI suggestion path is wrapped by `cached_llm_suggestions` / `refresh_suggestions_cache` (views.py:1488). A cached response bypasses both the LLM call and hint construction entirely. Acceptable for v1.

### No `AIConfig` / DB model / settings changes

No new configuration fields, DB columns, Django migrations, env vars, or frontend changes. The feature is automatically active for users who have an embedding backend configured and invisible to everyone else.

## Data flow

Suggestion request (embedding backend on):

1. View calls `get_taxonomy_hints_for_document(doc, user)` → `retrieve_similar_nodes` → extract metadata → `TaxonomyHints`.
2. View calls `get_ai_document_classification(doc, user, output_language, hints=hints)`.
3. Classifier builds RAG prompt via `build_prompt_with_rag` (internally calls `query_similar_documents` → `retrieve_similar_nodes` for context text) + splices hints block → LLM → parsed dict.
4. View calls `match_*_by_name(names, user, hinted_names=set(hints[<category>]))` per category.

Suggestion request (embedding backend off):

- `get_taxonomy_hints_for_document` returns `None` immediately (no retrieval runs).
- Rest of the flow identical to today.

**Note on retrieval calls:** `retrieve_similar_nodes` is called once directly (for hints) and once indirectly via `build_prompt_with_rag` → `get_context_for_document` → `query_similar_documents`. Both calls use identical parameters. Acceptable for v1; can be eliminated later by lifting `retrieve_similar_nodes` up to `get_ai_document_classification` and threading results to both callers.

## Error handling

- **Embedding backend off:** `get_taxonomy_hints_for_document` returns `None`; no hints; behavior identical to today.
- **No similar documents found:** `build_taxonomy_hints_from_nodes([])` returns all-empty `TaxonomyHints`; `format_hints_for_prompt` produces no blocks; effectively `hints = None`.
- **Node missing `storage_path` key** (index predates the metadata enrichment prerequisite): `node.metadata.get("storage_path")` returns `None`; skipped gracefully. Storage path hints absent until rebuild completes.
- **LLM returns a name not in hints but exactly matching an existing visible name:** still treated as exact match — `_match_names_to_queryset` always tries exact-on-full-queryset before fuzzy.
- **Retrieval failure:** propagates; suggestion failures already surface as 5xx.

## Testing

All tests use pytest style — grouped under classes, `@pytest.mark.django_db` on the class, `pytest-mock`'s `mocker` fixture, every fixture parameter/return/test signature type-annotated. Format with `ruff` directly (not `uv run ruff`).

### `paperless_ai/tests/test_taxonomy.py` (new)

- `class TestBuildTaxonomyHintsFromNodes:`
  - Returns a `TaxonomyHints` with all four keys.
  - Deduplicates tag names shared across multiple nodes.
  - `None` values in node metadata skipped gracefully.
  - Missing `storage_path` key in metadata handled gracefully (pre-migration nodes).
  - Empty node list → all-empty `TaxonomyHints`.
  - Sorted output is stable across calls.

- `class TestGetTaxonomyHintsForDocument:`
  - Returns `None` when `AIConfig().llm_embedding_backend` is falsy; `retrieve_similar_nodes` not called (`mocker.spy`).
  - Calls `retrieve_similar_nodes` with owner-aware document ID filter when user is provided.
  - Returns populated `TaxonomyHints` when nodes are found.
  - Returns all-empty `TaxonomyHints` (not `None`) when `retrieve_similar_nodes` returns `[]`.

- `class TestFormatHintsForPrompt:`
  - All four blocks present when all categories non-empty.
  - Empty category produces no block.
  - All-empty hints produces empty string (no stray instruction line).
  - Instruction line appears exactly once when at least one block is rendered.

### `paperless_ai/tests/test_ai_classifier.py` (extend)

- `class TestBuildPrompt:`
  - `build_prompt_without_rag(doc, config, hints=hints)` produces a prompt containing the hints block when hints are non-empty.
  - `build_prompt_with_rag(doc, config, user, hints=hints)` includes both the RAG context block (unchanged) and the hints block.
  - `hints=None`: prompt matches today's baseline (string equality against a fixture).
  - `get_ai_document_classification(doc, user, hints=...)` forwards hints into the prompt; return shape unchanged.

### `paperless_ai/tests/test_matching.py` (extend)

- `class TestHintedMatching:`
  - LLM returns `"Bloodwork"` verbatim, `hinted_names={"Bloodwork"}` → exact match returned; `difflib.get_close_matches` not called (`mocker.spy`).
  - LLM returns `"blood test"` not in `hinted_names`, no existing exact → fuzzy fallback runs; behavior unchanged from today (regression guard).
  - LLM returns `"Bloodwork "` (whitespace) with `hinted_names={"Bloodwork"}` → normalized exact match wins, fuzzy not consulted.
  - Backward compatibility: `match_tags_by_name(names, user)` without the kwarg behaves identically to today.

## Migration / rollout

No migration in this feature. The prerequisite spec (`2026-06-09-node-metadata-enrichment.md`) handles the LanceDB schema migration (v2, `requires_reembed=True`) and the resulting index rebuild. Once that lands, `storage_path` is in every node's metadata and this feature needs no additional migration steps.

No Django migration. No new config. Users with an embedding backend get taxonomy hints automatically once both specs are shipped; users without one see no change.

## Interplay with `extract_unmatched_names`

`extract_unmatched_names` surfaces LLM-returned names that didn't match any existing taxonomy entry — the UI uses these to offer "create new tag?" affordances. With hints in place, fewer names will be unmatched. No behavior change required: a hinted name the LLM returns verbatim will exact-match and not appear in the unmatched list; a name the LLM invents anyway still flows through fuzzy and, if no match, surfaces as "new" exactly as today.

## Out of scope (potential v2)

- Capping hint list length per category (currently unbounded within `top_k=5` retrieved nodes; revisit if prompt length becomes a concern).
- Eliminating the double `retrieve_similar_nodes` call by threading nodes through `get_ai_document_classification`.
- Frequency-based hints as a fallback for users without an embedding backend.
- Structured output / JSON schema enum constraints as an alternative to prompt injection.
- Tag hierarchy awareness.
- Custom field option values.
