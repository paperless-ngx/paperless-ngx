# Split `documents/views.py` and `documents/serialisers.py` into modules

## Problem

`src/documents/views.py` (5,395 lines) and `src/documents/serialisers.py`
(3,532 lines) have grown into monolithic files covering every REST resource
in the `documents` app: correspondents, tags, document types, storage paths,
custom fields, the core document viewset and search, chat, bulk-edit
operations, sharing, saved views, tasks, workflows, and system/UI settings.
Their size makes them hard to navigate, hard to review incrementally, and
increases the chance of unrelated changes colliding in the same file.

This document specifies splitting both files into packages, one module per
domain area, with no behavior change.

## Non-goals

- No behavior change. Class names, method bodies, and public API responses
  are unchanged — this is a pure move/reorganize.
- No change to `test_views.py` or `test_api_documents.py`. They exercise the
  moved classes via imports or via the live API; class names and behavior
  don't change, so they need no edits. Splitting those test files is a
  separate, later task if desired.
- No change to the frontend, migrations, or any other app beyond the three
  files that import from `documents.views` / `documents.serialisers`
  (`paperless/urls.py`, `paperless_mail/views.py`,
  `paperless_mail/serialisers.py`).
- This work happens as its own branch/PR against `dev`, after the in-flight
  `feature-ai-taxonomy-hints-v2` work merges — not layered on top of it.

## Architecture

`documents/views.py` becomes the package `documents/views/`, and
`documents/serialisers.py` becomes `documents/serialisers/`. Each gets one
module per domain area (table below). Neither package's `__init__.py`
re-exports its submodules' contents — it stays empty (or a short docstring
only). The three external call sites that currently do
`from documents.views import X` / `from documents.serialisers import X` are
updated to import from the specific submodule instead
(`from documents.views.workflows import WorkflowViewSet`, etc.). This avoids
adding an indirection layer that could quietly regrow into a second dumping
ground, at the cost of touching those three files.

### Import direction

`views/*` modules may import from `serialisers/*` modules; `serialisers/*`
modules never import from `views/*`. This keeps the dependency graph acyclic
by construction — there is no case in the current code where a serializer
needs a view.

Domain module names are the same across both packages (e.g. `bulk_edit.py`
exists in both), which makes the natural import `from documents.serialisers.bulk_edit import BulkEditSerializer`
inside `documents/views/bulk_edit.py` easy to find, but a view is free to
import a serializer from a different domain module when needed (e.g. a
`documents.py` view using a `metadata.py` field serializer) — that's a plain
cross-module import, not a cycle risk, since the reverse direction never
happens.

## Module breakdown — `documents/views/`

| Module           | Contents                                                                                                                                                                                                                                                                                     |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `base.py`        | Shared mixins/helpers: `PassUserMixin`, `BulkPermissionMixin`, `PermissionsAwareDocumentCountMixin`, `DocumentSelectionMixin`, `DocumentOperationPermissionMixin`, `SearchParams`/`SearchResultPage`/`ResolvedRequestDocs`, `_get_tantivy_query_and_mode`, `_get_more_like_id`, `serve_file` |
| `index.py`       | `IndexView`, `serve_logo`                                                                                                                                                                                                                                                                    |
| `metadata.py`    | `CorrespondentViewSet`, `TagViewSet`, `DocumentTypeViewSet`, `StoragePathViewSet`, `CustomFieldViewSet`, `_get_llm_output_language`                                                                                                                                                          |
| `documents.py`   | `EmailDocumentDetailSchema`, `DocumentViewSet`, `UnifiedSearchViewSet`                                                                                                                                                                                                                       |
| `upload.py`      | `PostDocumentView`                                                                                                                                                                                                                                                                           |
| `chat.py`        | `ChatStreamingSerializer`, `ChatStreamingView`                                                                                                                                                                                                                                               |
| `search.py`      | `SearchAutoCompleteView`, `GlobalSearchView`, `SelectionDataView`, `StatisticsView`                                                                                                                                                                                                          |
| `bulk_edit.py`   | `BulkEditView`, `RotateDocumentsView`, `MergeDocumentsView`, `DeleteDocumentsView`, `ReprocessDocumentsView`, `EditPdfDocumentsView`, `RemovePasswordDocumentsView`, `BulkEditObjectsView`, `BulkDownloadView`                                                                               |
| `sharing.py`     | `ShareLinkViewSet`, `ShareLinkBundleViewSet`, `SharedLinkView`                                                                                                                                                                                                                               |
| `saved_views.py` | `SavedViewViewSet`                                                                                                                                                                                                                                                                           |
| `tasks.py`       | `_TasksViewSetSchema`, `TasksViewSet`                                                                                                                                                                                                                                                        |
| `workflows.py`   | `WorkflowTriggerViewSet`, `WorkflowActionViewSet`, `WorkflowViewSet`                                                                                                                                                                                                                         |
| `system.py`      | `UiSettingsView`, `RemoteVersionView`, `SystemStatusView`, `TrashView`                                                                                                                                                                                                                       |
| `logs.py`        | `LogViewSet`                                                                                                                                                                                                                                                                                 |

`documents.py` remains the largest module at roughly 1,600 lines
(`DocumentViewSet` alone is ~1,300 lines in the current file); every other
module is well under 500 lines.

## Module breakdown — `documents/serialisers/`

| Module           | Contents                                                                                                                                                                                                                                                                                                                                                                                           |
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

Note: `ChatStreamingSerializer` is defined in `views.py` today (not
`serialisers.py`), directly above `ChatStreamingView`. It moves with
`ChatStreamingView` into `documents/views/chat.py` rather than into the
serialisers package, preserving its current co-location.

## External call sites to update

Only three files import from these two modules today, and all move to
importing from the specific new submodule:

- `src/paperless/urls.py` — ~34 `from documents.views import X` lines, one
  per viewset/view used in URL routing. Each becomes
  `from documents.views.<domain> import X`.
- `src/paperless_mail/views.py` — `from documents.views import PassUserMixin`
  becomes `from documents.views.base import PassUserMixin`.
- `src/paperless_mail/serialisers.py` — `CorrespondentField`,
  `DocumentTypeField`, `OwnedObjectSerializer`, `TagsField` move to
  `from documents.serialisers.metadata import CorrespondentField, DocumentTypeField, TagsField`
  and `from documents.serialisers.base import OwnedObjectSerializer`.

## Migration order

1. Split `serialisers.py` into `documents/serialisers/` first — serializers
   have no dependency on views, so this half can be verified in isolation.
   Run the full backend test suite after this step.
2. Split `views.py` into `documents/views/`, importing from the new
   `documents/serialisers/*` modules per the table above. Run the full
   backend test suite.
3. Update the three external call sites (`paperless/urls.py`,
   `paperless_mail/views.py`, `paperless_mail/serialisers.py`).
4. Run `ruff check` / `ruff format` and the full backend test suite once
   more end to end.

Splitting serialisers before views (rather than in parallel) means step 2
can immediately import finished, correctly-located serializer modules
instead of guessing at not-yet-final paths.

## Risks / error handling

- **Circular imports**: prevented by construction (serialisers never import
  from views — see Import direction above). If a genuine cross-domain need
  is discovered during implementation that seems to require a
  views→views import cycle (e.g. `UnifiedSearchViewSet` extending
  `DocumentViewSet` from a different module — both already live in
  `documents.py` so this doesn't arise), resolve it by moving the shared
  piece to `base.py` rather than introducing a cycle.
- **Missed re-export consumers**: verified via a full-repo grep for
  `from documents.views import` / `from documents.serialisers import` /
  `documents.views.` / `documents.serialisers.` before considering the split
  complete, in case something beyond the three known call sites appears
  (e.g. in a management command or a rarely-run script).
- **Silent behavior drift during move**: since this is a pure reorganization,
  the full test suite passing after each step (rather than only at the end)
  is the primary safety net; no new tests are required for this refactor
  itself.

## Testing

No new tests. Existing coverage (`test_views.py`, `test_api_documents.py`,
and the rest of the `documents` test suite) is run after each migration step
per the ordering above, and must pass unchanged — a failure indicates the
move altered behavior, not that new coverage is needed.
