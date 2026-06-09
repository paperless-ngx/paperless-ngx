# AI Suggestions: Inject existing taxonomy as candidates

**Status:** Design (v2 — frequency-only)
**Date:** 2026-05-20
**Related:** [Discussion #12787](https://github.com/paperless-ngx/paperless-ngx/discussions/12787)
**Branch target:** `dev`

## Problem

AI Suggestions currently asks the LLM for free-form tag/document-type/correspondent/storage-path names, then reconciles via `difflib` fuzzy matching (cutoff 0.8) in `paperless_ai/matching.py`. This works for typos but not for semantic equivalents:

- `blood test` does not fuzzy-match `Bloodwork`
- `IRS` does not fuzzy-match `Taxes`
- `doctor visit` does not fuzzy-match `Medical`

Result: the LLM invents new metadata names that duplicate existing taxonomy entries.

## Goal

Tell the LLM what already exists, so it can prefer existing names verbatim. Fuzzy matching becomes the fallback for typos and for legitimately novel suggestions, not the primary semantic-equivalence mechanism.

Non-goals: changing the LLM client, embedding model selection, or RAG retrieval. Replacing fuzzy matching entirely. Custom-field option values. Embedding-based shortlisting (deferred to a v2 if frequency proves insufficient).

## Approach

For each of Tags, DocumentTypes, Correspondents, StoragePaths:

1. Take the user-visible queryset (owner-aware, matching `matching.py`).
2. Annotate by document-usage count and take the top `X` names by frequency. `X` is configurable per category cap (single setting, applied to all four categories).
3. Inject those names into the LLM prompt as "Available <category>" blocks, with the instruction to prefer them verbatim.
4. When the LLM responds, tell `matching.py` which names were hinted so an exact normalized match short-circuits past fuzzy. Names not in the hint list keep today's fuzzy fallback.

No FAISS index, no signals, no Celery tasks, no locks. Pure DB-side queries on each suggestion request.

## Components

### `paperless_ai/taxonomy.py` (new)

```python
class TaxonomyHints(TypedDict):
    tags: list[str]
    document_types: list[str]
    correspondents: list[str]
    storage_paths: list[str]

def build_taxonomy_hints(document: Document, user: User | None) -> TaxonomyHints: ...
def format_hints_for_prompt(hints: TaxonomyHints) -> str: ...
```

Internals:

- `_visible_queryset(model_cls, perm: str, user)` — wraps `get_objects_for_user_owner_aware` exactly as `matching.py` does. If `user` is `None`, returns the unfiltered manager queryset (parity with how `matching.py` behaves today).
- `_shortlist_by_frequency(queryset, max_per_category)` — DB-side:
  ```python
  return list(
      queryset
      .annotate(usage=Count("documents"))
      .order_by("-usage", "name")
      .values_list("name", flat=True)[:max_per_category]
  )
  ```
  Confirmed reverse relation name is `documents` for all four models (`documents/models.py:164,173,184,211`). Secondary order by `name` keeps results stable when usage ties (common with 0-usage tails). `StoragePath` uses the human `name` field, not the `path` template.

`format_hints_for_prompt` emits one `Available <category>:` block per non-empty category. Empty categories produce no block (avoid prompting the LLM with "Available tags: (none)"). A single instruction line follows:

```
Prefer existing names from these lists verbatim. Only propose a new value
if none of the existing names fits.
```

### `paperless_ai/ai_classifier.py` (modify)

> **Note (updated 2026-06-09):** Since this spec was written, two commits changed this file:
>
> - `27426c04b` (#12894) added `llm_output_language` to `AIConfig`, added a new `build_localization_prompt(suggestions, output_language)` function that runs _after_ the LLM call (post-classification localization step), and added `output_language: str | None = None` to `get_ai_document_classification`.
> - `eb292baa6` (#12944) switched the vector store to LanceDB (minor changes to this file).
>
> The current signatures are:
>
> - `build_prompt_without_rag(document: Document, config: AIConfig) -> str`
> - `build_prompt_with_rag(document: Document, config: AIConfig, user: User | None = None) -> str`
> - `get_ai_document_classification(document, user, output_language: str | None = None) -> dict`
>
> `build_localization_prompt` is a separate downstream step and does **not** interact with taxonomy hints — hints inject into the base prompt only, before the LLM call.

Current signatures already take `config: AIConfig`; no `user` addition is needed in `build_prompt_without_rag` (the view owns hint construction). Both prompt builders accept a new optional `hints: TaxonomyHints | None = None` parameter. When non-`None`, `format_hints_for_prompt(hints)` is spliced in before the "Analyze the following document" instruction. When `None` (default), the prompt is built as today.

`get_ai_document_classification(document, user, output_language: str | None = None, hints: TaxonomyHints | None = None)` accepts the same optional `hints` and forwards it to the prompt builder. Return shape is **unchanged** (`dict`). The view layer owns hint construction so the same `TaxonomyHints` object can be used both for the prompt and for `hinted_names` in matching — no need to thread it back out of the classifier. Callers in tests pass `hints=None` (or omit) to preserve existing behavior.

### `paperless_ai/matching.py` (modify)

- `_match_names_to_queryset(names, queryset, attr, hinted_names: set[str] | None = None)`:
  - Normalization unchanged.
  - Exact-match-on-full-queryset behavior unchanged (always tried first).
  - When `hinted_names` is provided and the LLM-returned name (normalized) matches a hinted name (normalized) → treated as exact-only; fuzzy is skipped for that name.
  - When `hinted_names` is `None` or the name isn't in it → existing 0.8 fuzzy fallback runs.
- `match_tags_by_name(names, user, hinted_names=None)` etc. — optional kwarg, backward compatible.

### `documents/views.py` (modify)

The suggestion endpoint (around line 1482) is the single production caller of `get_ai_document_classification` and the call site for `match_*_by_name`. Update it to:

1. Build hints once: `hints = build_taxonomy_hints(document, request.user)` (when `AIConfig().taxonomy_hints_enabled` and `max_per_category > 0`; otherwise `hints = None`).
2. Pass `hints` into the classifier: `parsed = get_ai_document_classification(document, request.user, output_language, hints=hints)` — `output_language` is already resolved at this point (added in #12894, `views.py:1472`).
3. Pass `hinted_names=set(hints["tags"])` (etc., one per category, or `None` when `hints` is `None`) into each `match_*_by_name` call.

**Cache interaction:** the AI suggestion path is wrapped by `cached_llm_suggestions` / `refresh_suggestions_cache` (views.py:1477). A cached response bypasses the LLM call entirely — so changes to hints config don't take effect until the cache entry is invalidated. Acceptable for v1 (cache is short-lived). If experience shows users change the toggle and expect immediate effect, follow up by including a hash of the hint-relevant config (`taxonomy_hints_enabled`, `_max`) in the cache key.

### `paperless/config.py` (`AIConfig`) + DB model + settings

`AIConfig.__post_init__` reads values from the `ApplicationConfiguration` DB row **and** falls back to `settings.*` constants (pattern at `paperless/config.py:207` for `ai_enabled`). Both layers are needed.

Two new fields, threaded through three places:

1. **`paperless/settings/*.py`** — add module-level constants read from env:
   - `AI_TAXONOMY_HINTS: bool = __get_boolean("PAPERLESS_AI_TAXONOMY_HINTS", "yes")` (default on)
   - `AI_TAXONOMY_HINTS_MAX: int = int(os.getenv("PAPERLESS_AI_TAXONOMY_HINTS_MAX", "30"))`

2. **`paperless/models.py` (`ApplicationConfiguration`)** — add two nullable columns:
   - `taxonomy_hints_enabled = models.BooleanField(null=True)`
   - `taxonomy_hints_max_per_category = models.PositiveSmallIntegerField(null=True)` (range 0–32767; `PositiveSmallIntegerField` is sufficient)
   - One Django migration.

3. **`paperless/config.py` (`AIConfig`)** — read with **explicit None check, not `or`** (because `0` and `False` are legitimate user values that would otherwise silently fall back to the settings default):
   ```python
   self.taxonomy_hints_enabled = (
       app_config.taxonomy_hints_enabled
       if app_config.taxonomy_hints_enabled is not None
       else settings.AI_TAXONOMY_HINTS
   )
   self.taxonomy_hints_max_per_category = (
       app_config.taxonomy_hints_max_per_category
       if app_config.taxonomy_hints_max_per_category is not None
       else settings.AI_TAXONOMY_HINTS_MAX
   )
   ```
   (Other fields in this file use `or`; we deliberately diverge here to support `0` and `False`. A short comment in code records why.)

**Frontend** (`src-ui/src/app/data/paperless-config.ts`): add two entries to the `PaperlessConfigOptions` declarative list (one `Boolean`, one `Number`, `category: ConfigCategory.AI`) plus two fields on the `PaperlessConfig` interface. No component changes; the form is generated from this list.

`paperless.conf.example` and the configuration docs page get entries.

## Data flow

Suggestion request:

1. View checks `AIConfig().taxonomy_hints_enabled`; if enabled, calls `hints = build_taxonomy_hints(document, user)`; otherwise `hints = None`.
2. View calls `parsed = get_ai_document_classification(document, user, hints=hints)`.
3. Classifier splices `format_hints_for_prompt(hints)` into the prompt (when non-`None`), calls LLM, returns parsed dict.
4. View calls `match_*_by_name(names, user, hinted_names=set(hints[<category>]) if hints else None)` per category. Exact-on-hint short-circuit; fuzzy fallback unchanged for misses.

No background processing. No persisted state. Each suggestion request runs four lightweight `Count("documents")` queries (could be combined into a single query per model via `.annotate().order_by().values_list()`, no joins beyond the existing reverse relation).

## Error handling

- **Empty visible queryset for a category:** omit that category's block from the prompt.
- **`taxonomy_hints_enabled = False` or `max_per_category = 0`:** `build_taxonomy_hints` returns an empty `TaxonomyHints`; prompt is identical to today; matching is called without `hinted_names`; behavior identical to today.
- **LLM returns a name not in hints but exactly matching an existing visible name:** still treated as exact match. `_match_names_to_queryset` always tries exact-on-full-queryset before fuzzy; `hinted_names` only governs whether fuzzy is consulted for that specific name.
- **DB query failure during shortlist build:** propagate. Suggestion failures already surface as 5xx; adding silent fallbacks here would mask real problems.

## Testing

All new and modified tests use pytest style — functions/classes, no `unittest.TestCase` subclasses; `pytest-django` with per-class `@pytest.mark.django_db`; `pytest-mock`'s `mocker` fixture for patching; every fixture parameter, fixture return, and test signature type-annotated. Tests grouped under classes (`class TestBuildTaxonomyHints:`), not flat free functions. Shared fixtures live in `paperless_ai/tests/conftest.py`. Format with `ruff` directly (not `uv run ruff`).

### `paperless_ai/tests/test_taxonomy.py` (new)

- `class TestBuildTaxonomyHints:`
  - Returns a `TaxonomyHints` with all four keys.
  - Top-K limit respected (`max_per_category` honored from `AIConfig`).
  - Frequency ordering: tag used on 5 docs ranks above tag used on 2 docs.
  - Tie-break by name (alphabetical) for stable output.
  - Owner-aware: user lacking `view_tag` perm gets `tags=[]`; `view_documenttype` likewise per category.
  - Empty queryset for a category → empty list; `format_hints_for_prompt` omits the block.
  - `taxonomy_hints_enabled=False` returns zero-filled `TaxonomyHints` and runs no taxonomy DB queries (`django_assert_num_queries`).
  - `max_per_category=0` same behavior as disabled.
  - `StoragePath` shortlist uses the `name` field, not `path` template (asserted on returned values).

- `class TestFormatHintsForPrompt:`
  - All four blocks present when all categories non-empty.
  - Empty category produces no block.
  - All-empty hints produces empty string (no stray instruction line).
  - Instruction line appears exactly once when at least one block is rendered.

### `paperless_ai/tests/test_ai_classifier.py` (extend)

- `class TestBuildPrompt:`
  - `build_prompt_without_rag(doc, user)` now accepts `user`; produces a prompt containing the hints block when hints are non-empty.
  - `build_prompt_with_rag(doc, user)` includes both the RAG context block (unchanged) and the hints block.
  - `taxonomy_hints_enabled=False`: prompt matches today's baseline (string equality against a fixture).
  - `get_ai_document_classification(doc, user, hints=...)` forwards hints into the prompt; return shape unchanged (still `dict`).

### `paperless_ai/tests/test_matching.py` (extend)

- `class TestHintedMatching:`
  - LLM returns `"Bloodwork"` verbatim, `hinted_names={"Bloodwork", ...}` → exact match returned; `difflib.get_close_matches` not called (`mocker.spy` on `difflib.get_close_matches`).
  - LLM returns `"blood test"` not in `hinted_names`, no existing exact → fuzzy fallback runs; behavior unchanged from today (regression guard).
  - LLM returns `"Bloodwork "` (whitespace) with hinted_names containing `"Bloodwork"` → normalized exact match wins, fuzzy not consulted.
  - Backward compatibility: `match_tags_by_name(names, user)` without the kwarg behaves identically to today (snapshot of an existing test, parameterized).

Markers: no `live` marker needed.

## Migration / rollout

- One Django migration adding two columns to `ApplicationConfiguration` (`taxonomy_hints_enabled BooleanField`, `taxonomy_hints_max_per_category PositiveSmallIntegerField`). Both nullable with sensible defaults so existing rows aren't broken.
- Feature defaults to on for new and existing installs. Set `PAPERLESS_AI_TAXONOMY_HINTS=false` (or via the Application Configuration UI) to restore today's behavior.
- Frontend admin form updated to expose the two fields under the existing AI section.

## Open questions deferred to implementation

- `paperless_ai/tests/conftest.py` already exists — verify fixture-naming conventions match before adding new fixtures.
- Confirm `parse_ai_response` doesn't need to know about hints (it's a pure parser; hints flow alongside, not through it).
- The view layer applying `hinted_names` needs to read the same `AIConfig` instance the classifier used; pass the `TaxonomyHints` through the response tuple (chosen) rather than re-deriving in the view.

## Interplay with `extract_unmatched_names`

`extract_unmatched_names` (used downstream of matching) surfaces LLM-returned names that didn't match any existing taxonomy entry — the UI uses these to offer "create new tag?" affordances. With hints in place, fewer names will be unmatched, which is the desired outcome. No behavior change is required: a hinted name that the LLM repeats verbatim will exact-match and not appear in the unmatched list; a name the LLM invents anyway (despite the hint instruction) still flows through fuzzy and, if no match, surfaces as "new" exactly as today. Out of scope: filtering unmatched results based on what was in the hint set.

## Out of scope (potential v2)

- Embedding-based shortlisting (for users with very large taxonomies where frequency misses the right tag). Would re-introduce a FAISS-shaped subsystem with signals, debounce, and locks. Defer until evidence frequency is insufficient.
- Tag hierarchy awareness — hinting `Medical/Bloodwork` vs `Bloodwork` when tags are nested.
- Custom field option values.
- `StoragePath` template-expression hinting (vs raw `name`).
