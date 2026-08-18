# Workflow Runner Refactor — Design

**Date:** 2026-05-19
**Branch base:** `dev`
**Status:** Approved design, pending implementation plan

## Problem

Workflow execution and the Django signal layer have repeatedly produced fragile,
hard-to-fix bugs (see the revert/refix history around password removal: #12803,
#12814, #12716, and the filename race #12386). Three structural causes:

1. **`run_workflows` is dual-mode.** A single function handles both consumption
   (mutating a `DocumentMetadataOverrides`) and post-save (mutating a real
   `Document`), branching on a `use_overrides` flag. The branching is
   concentrated in two places — the action dispatch inside `run_workflows`
   (`handlers.py:931-1001`) and `build_workflow_action_context`
   (`actions.py:33-83`), each with two full code paths. The `apply_*` helpers in
   `workflows/mutations.py` are _already_ split by target type
   (`apply_assignment_to_document` vs `apply_assignment_to_overrides`, etc.); the
   refactor unifies their callers, not the helpers themselves.

2. **File location is an implicit, timing-dependent side channel.** The
   `DOCUMENT_ADDED` workflow fires from `run_workflows_added`, which runs while
   the consumer is still inside its transaction — _before_ the consumed file is
   copied to `document.source_path` (`document_consumption_finished` is sent at
   `consumer.py:654`; the file copy happens after, at `consumer.py:666+`). The
   staged path is therefore threaded through as `original_file` /
   `caller_supplied_original_file` parameters. Actions that read the file
   (password removal, email attachments) depend on this plumbing being correct.

3. **The workflow run races the filename rename.** `update_filename_and_move_files`
   is a raw `post_save` receiver on `Document`. When a workflow persists its
   changes via `document.save(update_fields=[...])`, that save fires `post_save`
   and runs the rename _while the workflow is still executing_. Under concurrent
   Celery/UI updates the interleaved `refresh_from_db()` calls corrupt state. The
   comment at `handlers.py:980-984` — deliberately excluding `filename` /
   `archive_filename` from the workflow save — is a load-bearing workaround for
   exactly this.

Note: `run_workflows_added` / `run_workflows_updated` are connected to the
_custom_ signals `document_consumption_finished` / `document_updated`, fired
explicitly by paperless code in a handful of known sites — not to raw Django
`post_save`. Only `update_filename_and_move_files` is a raw `post_save` receiver.
This refactor does not change where workflows are triggered from.

## Scope

In scope:

- Refactor `run_workflows` and its action helpers around an execution-context
  abstraction.
- Delete the `original_file` side-channel plumbing.
- Make the workflow-execution → persist → rename sequence explicit and
  deterministic.

Out of scope:

- Changing where/when workflows are triggered (custom signal call sites unchanged).
- Reworking the matching logic (`matching.document_matches_workflow`).
- Any change to workflow models, serializers, or the REST API.

## Design

### 1. `WorkflowRunContext` protocol

New module `documents/workflows/context.py` defining a `typing.Protocol`:

```
WorkflowRunContext (Protocol)
  source_file: Path                       # where the file actually is, now
  build_placeholder_context() -> dict
  apply_assignment(action) -> None
  apply_removal(action) -> None
  persist() -> None                        # commit accumulated mutations
  record_run(workflow, trigger_type) -> None
```

Two concrete implementations (which need not import the Protocol — structural
typing):

- **`ConsumptionContext`** — wraps `ConsumableDocument` + `DocumentMetadataOverrides`.
  `source_file` returns the staged file path. Mutations land on the overrides.
  `persist()` is a no-op (the overrides object is returned to the caller).
- **`PersistedContext`** — wraps a real `Document`. Mutations land on the
  in-memory `Document`. `persist()` performs a single save.

**Context selection** — `run_workflows` picks the context from the call shape:

- CONSUMPTION trigger (`ConsumableDocument` + non-`None` `overrides`) →
  `ConsumptionContext`.
- DOCUMENT_ADDED / DOCUMENT_UPDATED / SCHEDULED (a real `Document`,
  `overrides=None`) → `PersistedContext`.

**`source_file` for `PersistedContext`.** It cannot unconditionally return
`document.source_path`: for the `DOCUMENT_ADDED` trigger the file has not yet
been moved there. The staged path is therefore passed into the `PersistedContext`
_at construction time_ by `run_workflows_added` (which still receives it from the
`document_consumption_finished` signal). `source_file` returns that staged path
when supplied, otherwise `document.source_path`. This relocates the staged-path
information from a chain of function parameters into a single piece of
construction state — the `original_file` / `caller_supplied_original_file`
_parameter plumbing_ through `run_workflows` and the action helpers is what gets
deleted, not the staged path itself.

`WorkflowRunContext` is a plain `Protocol`, not `@runtime_checkable` — the runner
constructs the context itself, so no `isinstance` check is needed. Genuinely
shared logic goes into module-level helper functions, not a base class.

### 2. `run_workflows` becomes branch-free

`run_workflows` keeps its current public signature so all call sites are
unchanged. Its body:

1. Construct the appropriate context once, from the argument types.
2. Run a single flat match-and-dispatch loop over matching workflows/actions,
   delegating every action to context methods.

No `use_overrides` flag anywhere. The branching currently scattered across
`run_workflows`, `build_workflow_action_context`, and the `apply_*` helpers
collapses into the two context classes.

### 3. File staging via `source_file`

`source_file` is a property of the context, fixed at construction. The
`original_file` and `caller_supplied_original_file` parameters threaded through
`run_workflows` and the `execute_*` helpers are deleted; each context resolves
the path itself (see "Context selection" above).

**Deferred password removal.** `execute_password_removal_action`, when given a
`ConsumableDocument`, currently installs a one-shot handler on
`document_consumption_finished` that picks up `original_file` from `kwargs`
later (`actions.py:295-308`). This deferred hook lives outside the context
abstraction. The refactor must explicitly decide its fate: either keep it as-is
(the context still constructs correctly around it) or fold the deferral into
`ConsumptionContext`. This is called out as an open implementation decision, not
silently absorbed.

### 4. Explicit workflow → persist → rename sequencing

What must be deferred is the **file rename**, not the DB save. `run_workflows`
keeps its per-workflow `document.refresh_from_db()` at the top of each iteration
— that is deliberate concurrency protection against `bulk_update_documents`
running simultaneously. Deferring all saves to a single final `persist()` would
let one workflow's refresh wipe a prior workflow's in-memory changes. So:

1. `run_workflows` refreshes and applies actions per workflow, and
   `PersistedContext.persist()` saves after each matching workflow, as today.
2. The save deliberately **continues to exclude** `filename` /
   `archive_filename` from `update_fields`. This is not duct tape: it guards a
   _cross-process_ hazard — another Celery task may have moved the file and
   written `filename` to the DB, and a stale in-memory `filename` in our save
   would revert it. The `ContextVar` guard (below) only addresses _intra-process_
   ordering, so this exclusion stays.
3. The rename is suppressed for the whole run and invoked **exactly once,
   afterward**, against final committed state.

The actual race being fixed: `apply_assignment_to_document` assigns tags via
`document.add_nested_tags(...)`, which fires `m2m_changed` on
`Document.tags.through` _before_ the workflow's `document.save()`. The
`m2m_changed` receiver `update_filename_and_move_files` then calls
`refresh_from_db()`, wiping the workflow's in-memory correspondent/type, and
moves the file to a path computed from stale metadata. The guard prevents this.

To stop the rename from firing mid-workflow, a **`ContextVar` guard** is
introduced (e.g. `documents/workflows/context.py` module-level
`_workflow_in_progress: ContextVar[bool]`). `update_filename_and_move_files`
checks the guard and early-returns when set. `run_workflows` wraps its **entire**
persisted-path execution — not just the `persist()` call — in a context manager
that sets the guard via `set()`/`reset(token)`. Token-based reset is
reentrancy-safe for nested saves or nested workflow runs.

The guard must span the whole execution, not just `persist()`, because
`update_filename_and_move_files` is _also_ registered to `m2m_changed` on
`Document.tags.through` and to `post_save` on `CustomFieldInstance`
(`handlers.py:431-432`). A workflow action that assigns tags or custom fields
would otherwise trigger a rename mid-workflow through those signals.

After execution completes, `run_workflows` calls `persist()` once and then
explicitly invokes the move logic once. The `ContextVar` is set/reset in the
same thread that runs these receivers synchronously, so they always observe the
value. (Celery `prefork` workers run each task in its own process; greenlet
pools are also `contextvars`-aware — non-issues, noted for completeness.)

The move body of `update_filename_and_move_files` is extracted into a plain
callable that the runner invokes directly. The function is already invoked
directly (as a plain call, bypassing the decorator) for version documents at
`handlers.py:664-667`, so this extraction has precedent. The thin `post_save`
receiver remains as a guard-checking wrapper.

The two `post_save` receivers on `Document` are `update_filename_and_move_files`
(`handlers.py:433`) and `update_llm_suggestions_cache` (`handlers.py:740`). The
`ContextVar` guard suppresses **only** the former — `update_llm_suggestions_cache`
keeps running normally, as do `document_consumption_finished` receivers such as
`add_or_update_document_in_llm_index` (which is _not_ a `post_save` receiver).
This is why the guard is preferred over persisting with `.update()`, which would
silently suppress _all_ `post_save` receivers including
`update_llm_suggestions_cache`.

`WorkflowRun.objects.create(...)` is created per matching workflow as today
(`handlers.py:998-1002`); it is a separate model and is not deferred.

The comment at `handlers.py:980-984` is updated to describe the new flow
(per-workflow save under the guard; single explicit rename afterward) but the
`filename` / `archive_filename` exclusion it documents is kept — see point 2
above.

## Testing

- **Runner loop** — exercised against a fake context implementing the
  `WorkflowRunContext` surface that records `apply_assignment` / `apply_removal`
  / `persist` calls. No DB document, no staged files, no signals.
- **Concrete contexts** — `ConsumptionContext` and `PersistedContext` each get
  focused tests: given an action, assert the mutation lands on the overrides vs.
  the document, and that `source_file` resolves to the staged vs. final path.
- **ContextVar guard** — assert `update_filename_and_move_files` early-returns
  while the guard is set, and that the rename runs exactly once after
  `persist()`.
- **Regression: the racy case** — a workflow that reassigns metadata while the
  document is subject to a filename template; assert final DB filename and file
  location are consistent (the #12386 scenario).
- **Regression safety net** — the existing `test_workflows.py` suite (~100
  tests; ~19 `document_consumption_finished.send` sites plus many direct
  `run_workflows(...)` calls for the `DOCUMENT_UPDATED` path) must stay green
  **unchanged**. A test that needs editing signals a behavior change to flag
  explicitly, not a silent refactor outcome.

Per project conventions: tests grouped under classes, fixtures and test
signatures fully type-annotated.

## Implementation sequence

Each step is independently reviewable and keeps the test suite green:

1. Introduce the `Protocol` + the two contexts; `run_workflows` delegates to
   them. Pure refactor, no behavior change.
2. Move the staged path into `PersistedContext` construction (passed by
   `run_workflows_added`); delete the `original_file` /
   `caller_supplied_original_file` parameter plumbing through `run_workflows`
   and the `execute_*` helpers.
3. Extract the move body from `update_filename_and_move_files` into a callable;
   add the `ContextVar` guard; `run_workflows` invokes the move once after the
   run completes. The `filename` / `archive_filename` exclusion in the
   per-workflow save is kept; only the comment at `handlers.py:980-984` is
   updated to describe the new flow.

## Pain points addressed

- **Dual-mode** → eliminated by the `Protocol` + two contexts; no `use_overrides`.
- **File staging** → `source_file` is a context property; side-channel args deleted.
- **Rename race** → per-workflow save under a `ContextVar` guard that suppresses
  the mid-workflow rename; a single explicit rename runs once at the end against
  final state.
