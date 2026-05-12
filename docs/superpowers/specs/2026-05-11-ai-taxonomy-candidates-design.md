# AI Taxonomy Candidate Injection

**Date:** 2026-05-11
**Status:** Approved

## Problem

The AI suggestions flow (`ai_suggestions` endpoint) asks the LLM to freely invent
names for tags, correspondents, document types, and storage paths. Post-hoc fuzzy
matching then maps those names back to existing DB objects. When the LLM invents a
name like "blood work" and the user has a tag named "Bloodwork", the fuzzy match can
fail (threshold 0.8), causing the item to appear as a "suggest new" entry rather than
matching the existing one.

## Solution

Inject the user's existing taxonomy as candidates in the LLM prompt so it can output
exact existing names directly. Fuzzy matching is kept as-is for any remaining
free-form suggestions.

## Scope

Changes are limited to `src/paperless_ai/ai_classifier.py`. The view
(`documents/views.py`) and matching layer (`paperless_ai/matching.py`) are unchanged.

## Design

### Taxonomy fetching

A new helper `get_taxonomy_candidates(user)` in `ai_classifier.py`:

- Fetches tags, correspondents, document types, and storage paths visible to the user
  via `get_objects_for_user_owner_aware` (same permission pattern as `matching.py`)
- Annotates each queryset with `Count('documents')` and orders by `-count` so
  frequently-used items appear first
- Slices each queryset to `TAXONOMY_CANDIDATE_LIMIT = 200`
- Returns a dict: `{"tags": [...], "correspondents": [...], "document_types": [...], "storage_paths": [...]}`
- When `user` is `None`, returns `None` (no candidates available)

### Prompt injection

`build_prompt_without_rag` and `build_prompt_with_rag` gain an optional
`candidates: dict | None = None` parameter. When candidates are present, the
following section is appended to the prompt:

```
Existing metadata (use exact names where they fit; suggest new ones only if nothing matches):
Tags: bloodwork, insurance, tax, rent, ...
Correspondents: Dr. Smith, Acme Corp, ...
Document types: Invoice, Receipt, ...
Storage paths: Medical/2024, Finance/Tax, ...
```

Categories with an empty candidate list are omitted from the section.

### Entry point

`get_ai_document_classification(document, user)` is updated to:

1. Call `get_taxonomy_candidates(user)` when `user` is not `None`
2. Pass the result to `build_prompt_with_rag` / `build_prompt_without_rag`

No changes to the function signature or return value.

## Graceful degradation

- Users with no embedding backend: candidates still injected (no embedding needed)
- Users with `user=None`: prompt unchanged from today
- Users with > 200 items in a category: most-used 200 are included; less common items
  may not appear as candidates but fuzzy matching still handles them as before

## Testing

New file: `src/paperless_ai/tests/test_taxonomy_candidates.py`

1. `get_taxonomy_candidates`
   - Returns permission-filtered names only
   - Orders by document count descending
   - Caps at 200 per category
   - Returns `None` when user is `None`

2. `build_prompt_without_rag` / `build_prompt_with_rag`
   - Candidate section present when candidates provided
   - Candidate section absent when `candidates=None`
   - Empty categories omitted from candidate section

3. `get_ai_document_classification`
   - Candidates fetched and passed through when user provided
   - Prompt unmodified (no candidate section) when user is `None`

Existing tests in `test_ai_classifier.py` and `test_matching.py` are untouched.

## Out of scope

- Embedding-based semantic retrieval for very large taxonomies (future enhancement)
- Fixing normalization inconsistency in `extract_unmatched_names` (separate concern)
- Changes to caching logic or cache invalidation on taxonomy changes
