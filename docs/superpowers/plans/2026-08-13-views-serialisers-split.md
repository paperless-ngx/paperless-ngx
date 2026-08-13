# Split views.py and serialisers.py Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `src/documents/views.py` (5,395 lines) and `src/documents/serialisers.py` (3,532 lines) into domain-based module packages, with zero behavior change.

**Architecture:** Both files become packages (`documents/views/`, `documents/serialisers/`), one module per domain area. Serialisers split first (views depend on serialisers, never the reverse), then views, then the three external call sites (`paperless/urls.py`, `paperless_mail/views.py`, `paperless_mail/serialisers.py`) are pointed at the new submodules. No `__init__.py` re-exports in either package — every internal and external consumer imports the exact submodule.

**Tech Stack:** Django REST Framework (viewsets/serializers), ruff (lint/format), pytest via the project's VM test runner.

**Spec:** `docs/superpowers/specs/2026-08-13-views-serialisers-split-design.md`

## Global Constraints

- No behavior change: class/function bodies, names, and public API responses are unchanged — pure move/reorganize. (spec: Non-goals)
- Domain module names are identical across both packages (`bulk_edit.py` exists in both, etc.). (spec: Import direction)
- Import direction is one-way: `documents/views/*` may import from `documents/serialisers/*`; `documents/serialisers/*` must never import from `documents/views/*`. (spec: Import direction)
- Neither package's `__init__.py` re-exports submodule contents — every consumer, internal or external, imports the specific submodule (e.g. `from documents.views.workflows import WorkflowViewSet`). (spec: Architecture)
- `src/documents/tests/test_views.py` and `src/documents/tests/test_api_documents.py` are not modified — they must pass unchanged, proving the move didn't alter behavior. (spec: Non-goals, Testing)
- This branch targets `dev` and is separate from `feature-ai-taxonomy-hints-v2`. (spec: Non-goals)
- Backend tests run on the Linux VM via the helper script, never locally: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "<pytest targets>"`. `ruff check` / `ruff format` run locally (global binary, not `uv run ruff`).

---

## Reference: symbol-to-module maps

These tables (from the spec) are the authoritative source for which class/function goes to which new file. Copy them exactly — do not improvise groupings.

### `documents/serialisers/` map

| Module           | Symbols                                                                                                                                                                                                                                                                                                                                                                                            |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `base.py`        | `DynamicFieldsModelSerializer`, `DocumentUpdateFieldsModelSerializer`, `MatchingModelSerializer`, `SetPermissionsMixin`, `SerializerWithPerms`, `SetPermissionsSerializer`, `OwnedObjectSerializer`, `OwnedObjectListSerializer`, `ReadWriteSerializerMethodField`, `DocumentListSerializer`, `DocumentSelectionSerializer`, `SourceModeValidationMixin`, `BasicUserSerializer`, `NotesSerializer` |
| `metadata.py`    | `CorrespondentSerializer`, `DocumentTypeSerializer`, `DeprecatedColors`, `ColorField`, `TagSerializer`, `CorrespondentField`, `TagsField`, `DocumentTypeField`, `StoragePathField`, `StoragePathSerializer`, `StoragePathTestSerializer`, `CustomFieldSerializer`, `CustomFieldInstanceSerializer`, `validate_documentlink_targets`                                                                |
| `documents.py`   | `DocumentSerializer`, `SearchResultListSerializer`, `SearchResultSerializer`, `DuplicateDocumentSummarySerializer`, `_DocumentVersionInfo`, `DocumentVersionInfoSerializer`, `DocumentVersionSerializer`, `DocumentVersionLabelSerializer`, `_get_viewable_duplicates`                                                                                                                             |
| `upload.py`      | `PostDocumentSerializer`                                                                                                                                                                                                                                                                                                                                                                           |
| `saved_views.py` | `SavedViewFilterRuleSerializer`, `SavedViewSerializer`                                                                                                                                                                                                                                                                                                                                             |
| `bulk_edit.py`   | `RotateDocumentsSerializer`, `MergeDocumentsSerializer`, `EditPdfDocumentsSerializer`, `RemovePasswordDocumentsSerializer`, `DeleteDocumentsSerializer`, `ReprocessDocumentsSerializer`, `BulkEditSerializer`, `BulkDownloadSerializer`, `BulkEditObjectsSerializer`                                                                                                                               |
| `sharing.py`     | `EmailSerializer`, `ShareLinkSerializer`, `ShareLinkBundleSerializer`                                                                                                                                                                                                                                                                                                                              |
| `tasks.py`       | `TaskSerializerV10`, `TaskSerializerV9`, `TaskSummarySerializer`, `RunTaskSerializer`, `AcknowledgeTasksViewSerializer`                                                                                                                                                                                                                                                                            |
| `workflows.py`   | `WorkflowTriggerSerializer`, `WorkflowActionEmailSerializer`, `WorkflowActionWebhookSerializer`, `WorkflowActionSerializer`, `WorkflowSerializer`                                                                                                                                                                                                                                                  |
| `system.py`      | `UiSettingsViewSerializer`, `TrashSerializer`                                                                                                                                                                                                                                                                                                                                                      |

Extraction order matters (later modules reference earlier ones): `base` → `metadata` → `documents` → `upload` → `saved_views` → `bulk_edit` → `sharing` → `tasks` → `workflows` → `system`.

### `documents/views/` map

| Module           | Symbols                                                                                                                                                                                                                                                                 |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `base.py`        | `PassUserMixin`, `BulkPermissionMixin`, `PermissionsAwareDocumentCountMixin`, `DocumentSelectionMixin`, `DocumentOperationPermissionMixin`, `SearchParams`, `SearchResultPage`, `ResolvedRequestDocs`, `_get_tantivy_query_and_mode`, `_get_more_like_id`, `serve_file` |
| `index.py`       | `IndexView`, `serve_logo`                                                                                                                                                                                                                                               |
| `metadata.py`    | `CorrespondentViewSet`, `TagViewSet`, `DocumentTypeViewSet`, `StoragePathViewSet`, `CustomFieldViewSet`, `_get_llm_output_language`                                                                                                                                     |
| `documents.py`   | `EmailDocumentDetailSchema`, `DocumentViewSet`, `UnifiedSearchViewSet`                                                                                                                                                                                                  |
| `upload.py`      | `PostDocumentView`                                                                                                                                                                                                                                                      |
| `chat.py`        | `ChatStreamingSerializer`, `ChatStreamingView`                                                                                                                                                                                                                          |
| `search.py`      | `SearchAutoCompleteView`, `GlobalSearchView`, `SelectionDataView`, `StatisticsView`                                                                                                                                                                                     |
| `bulk_edit.py`   | `BulkEditView`, `RotateDocumentsView`, `MergeDocumentsView`, `DeleteDocumentsView`, `ReprocessDocumentsView`, `EditPdfDocumentsView`, `RemovePasswordDocumentsView`, `BulkEditObjectsView`, `BulkDownloadView`                                                          |
| `sharing.py`     | `ShareLinkViewSet`, `ShareLinkBundleViewSet`, `SharedLinkView`                                                                                                                                                                                                          |
| `saved_views.py` | `SavedViewViewSet`                                                                                                                                                                                                                                                      |
| `tasks.py`       | `_TasksViewSetSchema`, `TasksViewSet`                                                                                                                                                                                                                                   |
| `workflows.py`   | `WorkflowTriggerViewSet`, `WorkflowActionViewSet`, `WorkflowViewSet`                                                                                                                                                                                                    |
| `system.py`      | `UiSettingsView`, `RemoteVersionView`, `SystemStatusView`, `TrashView`                                                                                                                                                                                                  |
| `logs.py`        | `LogViewSet`                                                                                                                                                                                                                                                            |

Extraction order: `base` → `index` → `metadata` → `documents` → `upload` → `chat` → `search` → `bulk_edit` → `sharing` → `saved_views` → `tasks` → `workflows` → `system` → `logs`. Note `ChatStreamingSerializer` is defined in `views.py` today, directly above `ChatStreamingView` — it moves with it into `views/chat.py`, not into the serialisers package.

### Mechanical extraction recipe (applies to every task below)

For each module being created:

1. `grep -n "^class |^def " src/documents/<serialisers|views>.py` to get current line numbers for every symbol still in the monolith (numbers shift as earlier modules are extracted, so re-run this each time, don't reuse stale numbers).
2. Create the new file. Start it by copying the **entire top-of-file import block** from the monolith verbatim, plus a relative `from .base import ...` line if the module isn't `base.py` itself.
3. Cut each listed symbol (including any decorators/comments immediately above it) from the monolith and paste it into the new file, preserving original order.
4. Remove the cut symbols from the monolith.
5. Run `ruff check --select F401,F811,F821 <new file> <monolith file>` and fix everything reported:
   - `F401` (unused import) → delete the import line.
   - `F821` (undefined name) → the symbol lives in a sibling module already extracted; add `from .<sibling> import <Symbol>`. If it hasn't been extracted yet, that's an ordering bug — stop and re-check the extraction order table.
   - `F811` (redefinition) → duplicate import, delete one.
6. Run `ruff format <new file> <monolith file>`.

## Task 1: Scaffold `documents/serialisers/` and extract `base.py`

**Agent:** django-expert — **Model:** sonnet (mechanical extraction, but sets the foundation every later serialiser module imports from — get the base set right or every later task inherits the mistake)

**Files:**

- Create: `src/documents/serialisers/__init__.py` (empty — no re-exports, per Global Constraints)
- Create: `src/documents/serialisers/base.py`
- Modify: `src/documents/serialisers.py` (shrinks; stays in place as the monolith for the remaining tasks in this phase — it is only deleted in Task 2 once empty)
- Test: `src/documents/tests/` (full app suite), `src/paperless_mail/tests/`

**Interfaces:**

- Produces: `documents.serialisers.base` exporting `DynamicFieldsModelSerializer`, `DocumentUpdateFieldsModelSerializer`, `MatchingModelSerializer`, `SetPermissionsMixin`, `SerializerWithPerms`, `SetPermissionsSerializer`, `OwnedObjectSerializer`, `OwnedObjectListSerializer`, `ReadWriteSerializerMethodField`, `DocumentListSerializer`, `DocumentSelectionSerializer`, `SourceModeValidationMixin`, `BasicUserSerializer`, `NotesSerializer` — every later serialiser/view module that needs one of these imports `from documents.serialisers.base import <Symbol>`.

- [ ] **Step 1: Create the package directory and empty `__init__.py`**

```bash
mkdir -p src/documents/serialisers
touch src/documents/serialisers/__init__.py
```

- [ ] **Step 2: Extract `base.py` per the mechanical extraction recipe above**

Move exactly these 14 symbols (in their current relative order) out of `src/documents/serialisers.py` into `src/documents/serialisers/base.py`: `DynamicFieldsModelSerializer`, `DocumentUpdateFieldsModelSerializer`, `MatchingModelSerializer`, `SetPermissionsMixin`, `SerializerWithPerms`, `SetPermissionsSerializer`, `OwnedObjectSerializer`, `OwnedObjectListSerializer`, `ReadWriteSerializerMethodField`, `DocumentListSerializer`, `DocumentSelectionSerializer`, `SourceModeValidationMixin`, `BasicUserSerializer`, `NotesSerializer`.

Run the ruff fix-up (`ruff check --select F401,F811,F821 src/documents/serialisers/base.py src/documents/serialisers.py` then `ruff format` both files) as described in the recipe.

- [ ] **Step 3: Verify `documents.serialisers` (the monolith module, still at `src/documents/serialisers.py`) still imports cleanly and the app still boots**

Note: at this point Python resolves `documents.serialisers` to the package `src/documents/serialisers/__init__.py` (empty), **not** to `src/documents/serialisers.py` — having both a `serialisers.py` file and a `serialisers/` directory in the same parent package is invalid and Python will pick the package. So before running anything, rename the monolith out of the way so it's importable as a submodule of the new package for the rest of Phase A:

```bash
git mv src/documents/serialisers.py src/documents/serialisers/_monolith.py
```

Everywhere else in this phase, "the monolith file" now means `src/documents/serialisers/_monolith.py`. Because nothing outside this package imports the monolith directly by its old dotted path (`documents.serialisers` resolved to the file before; now it's the package), you must update every consumer of `documents.serialisers` symbols still owned by the monolith to import from `documents.serialisers._monolith` for the remainder of this phase. Concretely, in `src/documents/views.py`, change every `from documents.serialisers import <Symbol>` line for a symbol _not yet extracted_ (i.e., not one of the 14 `base.py` symbols) to `from documents.serialisers._monolith import <Symbol>`, and change the 14 now-extracted symbols' import lines to `from documents.serialisers.base import <Symbol>`. Do the same in `src/paperless_mail/serialisers.py` for `OwnedObjectSerializer` (→ `documents.serialisers.base`); its other three imports (`CorrespondentField`, `DocumentTypeField`, `TagsField`) stay pointed at `documents.serialisers._monolith` until Task 2 moves them into `metadata.py`.

This `_monolith` re-pointing is scaffolding only — Task 2 finishes emptying and deletes `_monolith.py`, and every import that currently says `._monolith` gets its final home then.

- [ ] **Step 4: Run the full test suite for this app boundary**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests src/paperless_mail/tests -v"
```

Expected: PASS, no collection errors (a collection error here almost always means a missed import update in `views.py` or `paperless_mail/serialisers.py`).

- [ ] **Step 5: Commit**

```bash
git add src/documents/serialisers src/documents/views.py src/paperless_mail/serialisers.py
git commit -m "refactor: extract documents/serialisers/base.py from the serialisers monolith"
```

## Task 2: Extract the remaining 8 serialiser domain modules and delete the monolith

**Agent:** django-expert — **Model:** sonnet (repetitive but each of the 8 modules needs its own cross-reference check against `base.py` and previously-extracted siblings; DocumentSerializer in particular is large and central)

**Files:**

- Create: `src/documents/serialisers/metadata.py`, `src/documents/serialisers/documents.py`, `src/documents/serialisers/upload.py`, `src/documents/serialisers/saved_views.py`, `src/documents/serialisers/bulk_edit.py`, `src/documents/serialisers/sharing.py`, `src/documents/serialisers/tasks.py`, `src/documents/serialisers/workflows.py`, `src/documents/serialisers/system.py`
- Delete: `src/documents/serialisers/_monolith.py` (once empty)
- Modify: `src/documents/views.py` (finish re-pointing every `from documents.serialisers._monolith import X` line at the correct new submodule), `src/paperless_mail/serialisers.py` (re-point `CorrespondentField`, `DocumentTypeField`, `TagsField` at `documents.serialisers.metadata`)
- Test: `src/documents/tests/` (full app suite), `src/paperless_mail/tests/`

**Interfaces:**

- Consumes: `documents.serialisers.base` from Task 1 (relative import `.base` within the package).
- Produces: the full `documents/serialisers/` package as specified in the Reference map above — this is what Task 3/4 (views split) and Task 5 (external call sites) import from.

- [ ] **Step 1: Extract the 8 remaining domain modules in order**

Following the mechanical extraction recipe, and in this exact order (each may depend on symbols extracted earlier in this same order, plus anything in `base.py`):

1. `metadata.py` — `CorrespondentSerializer`, `DocumentTypeSerializer`, `DeprecatedColors`, `ColorField`, `TagSerializer`, `CorrespondentField`, `TagsField`, `DocumentTypeField`, `StoragePathField`, `StoragePathSerializer`, `StoragePathTestSerializer`, `CustomFieldSerializer`, `CustomFieldInstanceSerializer`, `validate_documentlink_targets`
2. `documents.py` — `DocumentSerializer`, `SearchResultListSerializer`, `SearchResultSerializer`, `DuplicateDocumentSummarySerializer`, `_DocumentVersionInfo`, `DocumentVersionInfoSerializer`, `DocumentVersionSerializer`, `DocumentVersionLabelSerializer`, `_get_viewable_duplicates`
3. `upload.py` — `PostDocumentSerializer`
4. `saved_views.py` — `SavedViewFilterRuleSerializer`, `SavedViewSerializer`
5. `bulk_edit.py` — `RotateDocumentsSerializer`, `MergeDocumentsSerializer`, `EditPdfDocumentsSerializer`, `RemovePasswordDocumentsSerializer`, `DeleteDocumentsSerializer`, `ReprocessDocumentsSerializer`, `BulkEditSerializer`, `BulkDownloadSerializer`, `BulkEditObjectsSerializer`
6. `sharing.py` — `EmailSerializer`, `ShareLinkSerializer`, `ShareLinkBundleSerializer`
7. `tasks.py` — `TaskSerializerV10`, `TaskSerializerV9`, `TaskSummarySerializer`, `RunTaskSerializer`, `AcknowledgeTasksViewSerializer`
8. `workflows.py` — `WorkflowTriggerSerializer`, `WorkflowActionEmailSerializer`, `WorkflowActionWebhookSerializer`, `WorkflowActionSerializer`, `WorkflowSerializer`
9. `system.py` — `UiSettingsViewSerializer`, `TrashSerializer`

After each individual module extraction, run the ruff fix-up from the recipe against that new file and `_monolith.py` before moving to the next module (don't batch all 8 and fix imports once at the end — F821 errors compound and get harder to attribute to the right module).

- [ ] **Step 2: Confirm the monolith is empty and delete it**

```bash
grep -n "^class |^def " src/documents/serialisers/_monolith.py
```

Expected: no output. If anything remains, it wasn't in the Reference map — stop and reconcile with the spec rather than deleting a symbol.

```bash
git rm src/documents/serialisers/_monolith.py
```

- [ ] **Step 3: Re-point every remaining `._monolith` import**

Search for any import left pointing at the now-deleted module:

```bash
grep -rn "serialisers\._monolith\|serialisers/_monolith" src/
```

Expected: no output. Fix any that remain by pointing them at the correct submodule per the Reference map (e.g. `from documents.serialisers._monolith import DocumentSerializer` → `from documents.serialisers.documents import DocumentSerializer`).

- [ ] **Step 4: Update `paperless_mail/serialisers.py`'s remaining imports**

```python
# was: from documents.serialisers import CorrespondentField, DocumentTypeField, OwnedObjectSerializer, TagsField
from documents.serialisers.base import OwnedObjectSerializer
from documents.serialisers.metadata import CorrespondentField, DocumentTypeField, TagsField
```

- [ ] **Step 5: Ruff and full test suite**

```bash
ruff check src/documents/serialisers src/documents/views.py src/paperless_mail/serialisers.py
ruff format src/documents/serialisers src/documents/views.py src/paperless_mail/serialisers.py
```

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests src/paperless_mail/tests -v"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/documents/serialisers src/documents/views.py src/paperless_mail/serialisers.py
git commit -m "refactor: finish splitting serialisers.py into documents/serialisers/"
```

## Task 3: Scaffold `documents/views/` and extract `base.py`

**Agent:** django-expert — **Model:** sonnet (same shape as Task 1, one level up — views/base.py is imported by every other view module)

**Files:**

- Create: `src/documents/views/__init__.py` (empty), `src/documents/views/base.py`
- Modify: `src/documents/views.py` → `src/documents/views/_monolith.py` (renamed, same reasoning as Task 1 Step 3)
- Modify: `src/paperless/urls.py`, `src/paperless_mail/views.py` (re-point the 1 symbol each currently pulls from `documents.views` that now lives in `base.py`, if any — see step 3)
- Test: `src/documents/tests/` (full app suite, includes URL-resolution-dependent tests), `src/paperless_mail/tests/`

**Interfaces:**

- Consumes: `documents.serialisers.*` submodules from Tasks 1–2 (already at final locations — import these directly, e.g. `from documents.serialisers.documents import DocumentSerializer`, never through a monolith or shim).
- Produces: `documents.views.base` exporting `PassUserMixin`, `BulkPermissionMixin`, `PermissionsAwareDocumentCountMixin`, `DocumentSelectionMixin`, `DocumentOperationPermissionMixin`, `SearchParams`, `SearchResultPage`, `ResolvedRequestDocs`, `_get_tantivy_query_and_mode`, `_get_more_like_id`, `serve_file`.

- [ ] **Step 1: Create the package directory, empty `__init__.py`, and rename the monolith**

```bash
mkdir -p src/documents/views
touch src/documents/views/__init__.py
git mv src/documents/views.py src/documents/views/_monolith.py
```

- [ ] **Step 2: Extract `base.py` per the mechanical extraction recipe**

Move exactly these 11 symbols out of `_monolith.py` into `views/base.py`: `PassUserMixin`, `BulkPermissionMixin`, `PermissionsAwareDocumentCountMixin`, `DocumentSelectionMixin`, `DocumentOperationPermissionMixin`, `SearchParams`, `SearchResultPage`, `ResolvedRequestDocs`, `_get_tantivy_query_and_mode`, `_get_more_like_id`, `serve_file`.

Within `_monolith.py`, every reference to these 11 symbols needs `from .base import <Symbol>` added (they're used throughout the rest of the file by the not-yet-extracted viewsets).

- [ ] **Step 3: Re-point external consumers of the now-moved symbol**

```bash
grep -n "from documents.views import PassUserMixin" src/paperless_mail/views.py
```

Update it to `from documents.views.base import PassUserMixin`.

`paperless/urls.py` doesn't import any of the 11 `base.py` symbols directly (it only imports viewsets/views, which are all still in `_monolith.py` at this point) — confirm with:

```bash
grep -nE "from documents\.views import (PassUserMixin|BulkPermissionMixin|PermissionsAwareDocumentCountMixin|DocumentSelectionMixin|DocumentOperationPermissionMixin|serve_file)" src/paperless/urls.py
```

Expected: no output. If something does match, re-point it at `documents.views.base` the same way.

- [ ] **Step 4: Ruff and test**

```bash
ruff check src/documents/views src/paperless_mail/views.py
ruff format src/documents/views src/paperless_mail/views.py
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests src/paperless_mail/tests -v"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/documents/views src/paperless_mail/views.py
git commit -m "refactor: extract documents/views/base.py from the views monolith"
```

## Task 4: Extract the remaining 13 view domain modules and delete the monolith

**Agent:** django-expert — **Model:** opus (highest blast radius in the plan — `DocumentViewSet` alone is ~1,300 lines and central to the whole API; this task also rewires `paperless/urls.py`'s ~34 import lines that drive URL routing for the entire backend, where a mistake breaks the app at startup, not just in one test)

**Files:**

- Create: `src/documents/views/index.py`, `src/documents/views/metadata.py`, `src/documents/views/documents.py`, `src/documents/views/upload.py`, `src/documents/views/chat.py`, `src/documents/views/search.py`, `src/documents/views/bulk_edit.py`, `src/documents/views/sharing.py`, `src/documents/views/saved_views.py`, `src/documents/views/tasks.py`, `src/documents/views/workflows.py`, `src/documents/views/system.py`, `src/documents/views/logs.py`
- Delete: `src/documents/views/_monolith.py` (once empty)
- Modify: `src/paperless/urls.py` (all ~34 `from documents.views import X` lines)
- Test: `src/documents/tests/` (full app suite — includes `test_views.py`, `test_api_documents.py`), `src/paperless_mail/tests/`

**Interfaces:**

- Consumes: `documents.serialisers.*` (Tasks 1–2) and `documents.views.base` (Task 3).
- Produces: the full `documents/views/` package as specified in the Reference map above.

- [ ] **Step 1: Extract the 13 remaining domain modules in order**

Following the mechanical extraction recipe, in this exact order:

1. `index.py` — `IndexView`, `serve_logo`
2. `metadata.py` — `CorrespondentViewSet`, `TagViewSet`, `DocumentTypeViewSet`, `StoragePathViewSet`, `CustomFieldViewSet`, `_get_llm_output_language`
3. `documents.py` — `EmailDocumentDetailSchema`, `DocumentViewSet`, `UnifiedSearchViewSet`
4. `upload.py` — `PostDocumentView`
5. `chat.py` — `ChatStreamingSerializer`, `ChatStreamingView`
6. `search.py` — `SearchAutoCompleteView`, `GlobalSearchView`, `SelectionDataView`, `StatisticsView`
7. `bulk_edit.py` — `BulkEditView`, `RotateDocumentsView`, `MergeDocumentsView`, `DeleteDocumentsView`, `ReprocessDocumentsView`, `EditPdfDocumentsView`, `RemovePasswordDocumentsView`, `BulkEditObjectsView`, `BulkDownloadView`
8. `sharing.py` — `ShareLinkViewSet`, `ShareLinkBundleViewSet`, `SharedLinkView`
9. `saved_views.py` — `SavedViewViewSet`
10. `tasks.py` — `_TasksViewSetSchema`, `TasksViewSet`
11. `workflows.py` — `WorkflowTriggerViewSet`, `WorkflowActionViewSet`, `WorkflowViewSet`
12. `system.py` — `UiSettingsView`, `RemoteVersionView`, `SystemStatusView`, `TrashView`
13. `logs.py` — `LogViewSet`

After each module, run the ruff fix-up from the recipe before continuing to the next (same rationale as Task 2 Step 1 — attribute F821s to the right module while context is fresh). `documents.py` is the biggest single extraction in this whole plan (`DocumentViewSet` is ~1,300 lines) — expect the most F821 fix-ups here, mostly resolved by adding `from documents.serialisers.documents import ...`, `from documents.serialisers.metadata import ...`, and `from .base import ...` as needed.

- [ ] **Step 2: Confirm the monolith is empty and delete it**

```bash
grep -n "^class |^def " src/documents/views/_monolith.py
```

Expected: no output.

```bash
git rm src/documents/views/_monolith.py
```

- [ ] **Step 3: Re-point every remaining `._monolith` import**

```bash
grep -rn "views\._monolith\|views/_monolith" src/
```

Expected: no output. Fix any stragglers per the Reference map.

- [ ] **Step 4: Update `paperless/urls.py`**

Replace each of the ~34 `from documents.views import X` lines with `from documents.views.<domain> import X` per the Reference map. For example:

```python
# was:
from documents.views import CorrespondentViewSet
from documents.views import WorkflowViewSet
from documents.views import serve_logo
# becomes:
from documents.views.metadata import CorrespondentViewSet
from documents.views.workflows import WorkflowViewSet
from documents.views.index import serve_logo
```

Do this for every import in that block — check off against the full symbol list in the Reference map above so none are missed.

- [ ] **Step 5: Ruff and test**

```bash
ruff check src/documents/views src/paperless/urls.py
ruff format src/documents/views src/paperless/urls.py
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests src/paperless_mail/tests -v"
```

Expected: PASS, including `test_views.py` and `test_api_documents.py` — these exercise URL routing end-to-end, so a broken `urls.py` import shows up here as a collection error.

- [ ] **Step 6: Commit**

```bash
git add src/documents/views src/paperless/urls.py
git commit -m "refactor: finish splitting views.py into documents/views/"
```

## Task 5: Repo-wide verification sweep

**Agent:** general-purpose — **Model:** sonnet (an audit/verification pass: run targeted checks, read the output, fix anything found — moderate judgment, not novel design work)

**Files:**

- Modify: any file a grep in this task turns up beyond the ones already handled in Tasks 1–4 (expected: none, per the spec's stated blast radius of exactly `paperless/urls.py`, `paperless_mail/views.py`, `paperless_mail/serialisers.py` — this task exists to confirm that, not to find new work)
- Test: full backend suite (all apps, not just `documents`/`paperless_mail`)

**Interfaces:**

- Consumes: the finished `documents/views/` and `documents/serialisers/` packages from Tasks 1–4.

- [ ] **Step 1: Grep the whole repo for any remaining bare-module reference**

```bash
grep -rn "from documents\.views import\|from documents\.serialisers import\|documents\.views\.\_monolith\|documents\.serialisers\.\_monolith\|import documents\.views$\|import documents\.serialisers$" src/
```

Expected: no output. `documents/views/__init__.py` and `documents/serialisers/__init__.py` should still be empty (`0` bytes or a single blank line) — confirm with:

```bash
wc -l src/documents/views/__init__.py src/documents/serialisers/__init__.py
```

- [ ] **Step 2: Confirm import direction was never violated**

```bash
grep -rln "from documents\.views" src/documents/serialisers/
```

Expected: no output (no file in `serialisers/` imports from `views/`).

- [ ] **Step 3: Full ruff pass**

```bash
ruff check src/documents/views src/documents/serialisers src/paperless/urls.py src/paperless_mail/views.py src/paperless_mail/serialisers.py
ruff format --check src/documents/views src/documents/serialisers src/paperless/urls.py src/paperless_mail/views.py src/paperless_mail/serialisers.py
```

Expected: clean.

- [ ] **Step 4: Full backend test suite**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "-v"
```

(No path filter — this runs the whole backend suite, confirming nothing outside `documents`/`paperless_mail` was quietly relying on the old module shape, e.g. a management command or a script under `scripts/`.)

Expected: PASS.

- [ ] **Step 5: If Steps 1–4 found nothing to fix, commit is a no-op — skip it. If they found strays, fix and commit**

```bash
git add -A
git commit -m "refactor: fix stray documents.views/serialisers references found in repo sweep"
```
