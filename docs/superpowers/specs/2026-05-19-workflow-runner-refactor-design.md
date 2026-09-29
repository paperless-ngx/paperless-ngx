# Workflow Runner Refactor — Design

**Date:** 2026-05-19
**Updated:** 2026-09-24 — see "Status update (2026-09-24)" below; line references
throughout refreshed against current `dev`.
**Branch base:** `dev`
**Status:** Approved design, pending implementation plan. Motivating bugs are now
independently fixed (see status update) — this is a structural cleanup, not an
active-bug fix.

## Status update (2026-09-24)

The acute bugs this design was written against have since been closed by two
targeted, already-merged fixes that do **not** use the `WorkflowRunContext` /
`ContextVar` approach below:

- **#12386** (cross-process "file already moved" race, cited in cause 3) was
  fixed by **#12389** ("Fix: avoid moving files if already moved", merged in
  v2.20.12): `validate_move` in `update_filename_and_move_files` now detects,
  via a checksum comparison (`_path_matches_checksum`), when the target file
  already exists because a concurrent save already moved it, and recovers the
  DB pointer instead of raising `CannotMoveFilesException`. This is a different
  mechanism from anything proposed here and stays as-is; nothing in this
  refactor should touch `_path_matches_checksum` or its call sites.
- **The intra-workflow tag/`m2m_changed` race** described in cause 3 and design
  §4 (`add_nested_tags` firing `m2m_changed` → `refresh_from_db()` → wiping an
  earlier-ordered action's unsaved `correspondent`/`storage_path`) was fixed by
  **#13178** ("Fix: prevent tag assignment from reverting other pending
  workflow assignments", merged 2026-07-20 — _after_ this design was written).
  `apply_assignment_to_document` (`mutations.py`) now applies tag changes to a
  **freshly-fetched** `Document` instance rather than the shared in-memory one,
  matching the pattern `apply_removal_to_document` already used for tag
  removal. Because the mid-run rename this triggers now reads the _old_,
  still-current DB state (nothing else has been saved yet), it recomputes the
  same path and is a no-op; the real rename happens once, correctly, at the
  final `document.save()`. Regression coverage:
  `test_document_updated_workflow_assignment_storage_path_persists_with_tag_assignment`
  in `test_workflows.py` (the only test #13178 itself added). A related,
  earlier fix (#12664) covers a similar but distinct case — tag removal
  alongside a title assignment — via
  `test_document_updated_workflow_assignment_persists_when_removing_trigger_tag`.
- The `filename`/`archive_filename` exclusion from `update_fields` (cause 3,
  design §4 point 2) was already in place before this design was written (added
  by #12390-adjacent work) and is unaffected — still correctly attributed here
  as a load-bearing cross-process guard, not duct tape.
- **#13178's own PR description is the origin of this idea**: "Once the beta
  is out, I do have some thoughts about using ContextVar to delete this class
  entirely. We've run into it plenty of times." So the guard concept predates
  this design; the acute pain it was meant to address has since been patched
  piecemeal instead.

**What this means for scope:** causes 1 and 2 below (dual-mode branching,
staged-file parameter plumbing) are unchanged and fully present in current code
— this refactor is still worth doing for them. Cause 3's race is no longer an
_active_ bug; the `ContextVar` guard is now defense-in-depth / simplification
(it also collapses two independent workarounds — the fresh-instance tag fetch
and the per-workflow `update_fields` restriction — into one clearer mechanism)
rather than a fix for a reproducible failure. Treat any "fixes a bug" framing
below as historical motivation, not a current defect claim.

## Problem

Workflow execution and the Django signal layer have repeatedly produced fragile,
hard-to-fix bugs (see the revert/refix history around password removal: #12803,
#12814, #12716, and the filename race #12386, now closed — see status update
above). Three structural causes:

1. **`run_workflows` is dual-mode.** A single function handles both consumption
   (mutating a `DocumentMetadataOverrides`) and post-save (mutating a real
   `Document`), branching on a `use_overrides` flag. The branching is
   concentrated in two places — the action dispatch inside `run_workflows`
   (`handlers.py:938-1014`, `use_overrides` first set at `handlers.py:881`) and
   `build_workflow_action_context` (`actions.py:33-83`), each with two full code
   paths. The `apply_*` helpers in `workflows/mutations.py` are _already_ split
   by target type (`apply_assignment_to_document` vs
   `apply_assignment_to_overrides`, etc.); the refactor unifies their callers,
   not the helpers themselves. **Still fully present in current code — unchanged
   by any fix since this design was written.**

2. **File location is an implicit, timing-dependent side channel.** The
   `DOCUMENT_ADDED` workflow fires from `run_workflows_added`
   (`handlers.py:811-824`), which runs while the consumer is still inside its
   transaction — _before_ the consumed file is copied to `document.source_path`
   (`document_consumption_finished` is sent from `consumer.py`, the file copy
   happens after). The staged path is therefore threaded through as
   `original_file` / `caller_supplied_original_file` parameters
   (`handlers.py:868,890-898,976-979`). Actions that read the file (password
   removal, email attachments) depend on this plumbing being correct. **Still
   fully present in current code.**

3. **The workflow run could race the filename rename — now mitigated by two
   independent, narrower fixes (see "Status update" above), not eliminated
   structurally.** `update_filename_and_move_files` (`handlers.py:437-439`
   decorators, body `440-673`) is a raw `post_save`/`m2m_changed` receiver. When
   a workflow persists its changes via `document.save(update_fields=[...])`, or
   when `apply_assignment_to_document` mutates tags via a freshly-fetched
   instance (`mutations.py:26-31`), that write fires the receiver _while the
   workflow is still executing_. As of #13178 this no longer corrupts in-memory
   state (tags are applied to a separate instance, so the mid-run rename it
   triggers reads only already-committed data and is a no-op or self-consistent
   move); as of #12389 a genuine cross-process "someone else already moved this
   file" race recovers via checksum comparison instead of erroring. The comment
   documenting the `filename`/`archive_filename` exclusion from the workflow's
   own `update_fields` (`handlers.py:1019-1027`) remains a load-bearing guard
   against a _different_, still-real cross-process hazard (an in-memory
   `document.filename` going stale while another process moves the file) and is
   unaffected by either fix above.

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

**Historical race, already fixed by other means (see "Status update"):**
`apply_assignment_to_document` used to assign tags via
`document.add_nested_tags(...)` directly on the shared in-memory `document`,
which fired `m2m_changed` on `Document.tags.through` _before_ the workflow's
`document.save()`; the `m2m_changed` receiver `update_filename_and_move_files`
then called `refresh_from_db()` on that shared instance, wiping the workflow's
in-memory correspondent/type, and moved the file to a path computed from stale
metadata. #13178 fixed this by having `apply_assignment_to_document` (and
`apply_removal_to_document`, which already did this) mutate tags on a
**freshly-fetched** `Document.objects.get(pk=document.pk)` instead of the
shared one (`mutations.py:26-31`), so the `refresh_from_db()` triggered by
`m2m_changed` no longer touches the workflow's unsaved in-memory fields. The
guard below is not needed to fix that specific corruption anymore — it instead
gives a single, general mechanism that supersedes the fresh-instance-fetch
workaround (and the equivalent one already in `apply_removal_to_document`),
rather than requiring every future mutation path to remember to fetch a
separate instance.

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
(`handlers.py:437-438`). A workflow action that assigns tags or custom fields
would otherwise trigger a rename mid-workflow through those signals. If the
`ContextVar` guard lands, the fresh-instance-fetch workaround in
`apply_assignment_to_document`/`apply_removal_to_document` becomes redundant
but is not itself incorrect — decide during implementation whether to simplify
those two call sites back to mutating `document` directly now that the guard
covers the hazard, or leave them as extra defense-in-depth. Note either way:
`document` passed to `add_nested_tags`/`tags.clear`/`tags.remove` must still be
re-fetched or `refresh_from_db()`'d for the tags relation to reflect the
change on the in-memory instance used later in the same action.

After execution completes, `run_workflows` calls `persist()` once and then
explicitly invokes the move logic once. The `ContextVar` is set/reset in the
same thread that runs these receivers synchronously, so they always observe the
value. (Celery `prefork` workers run each task in its own process; greenlet
pools are also `contextvars`-aware — non-issues, noted for completeness.)

The move body of `update_filename_and_move_files` is extracted into a plain
callable that the runner invokes directly. The function is already invoked
directly today for version documents — currently as
`update_filename_and_move_files(Document, version_doc)`
(`handlers.py:670-673`), i.e. the _whole receiver_ is called with a synthetic
`sender` positional arg, bypassing only the `@receiver` decorator/dispatch, not
the guard-check-then-body split this refactor introduces. Once the move body is
extracted into its own callable (`move_files_for_document(instance)` per the
implementation plan), this recursive call site must be updated to call that
extracted function directly (`move_files_for_document(version_doc)`) rather
than the thin wrapper — otherwise recursing into version documents would
re-enter the guard-check wrapper unnecessarily (harmless, since the guard
should be set during a workflow run and unset otherwise, but pointless
indirection). The thin `post_save`/`m2m_changed` receivers remain as a
guard-checking wrapper around the extracted callable.

The two `post_save` receivers on `Document` are `update_filename_and_move_files`
(`handlers.py:439`) and `update_llm_suggestions_cache` (`handlers.py:746-747`).
The `ContextVar` guard suppresses **only** the former —
`update_llm_suggestions_cache` keeps running normally, as do
`document_consumption_finished` receivers such as
`add_or_update_document_in_llm_index` (which is _not_ a `post_save` receiver).
This is why the guard is preferred over persisting with `.update()`, which would
silently suppress _all_ `post_save` receivers including
`update_llm_suggestions_cache`.

`WorkflowRun.objects.create(...)` is created per matching workflow as today
(`handlers.py:1039-1043`); it is a separate model and is not deferred.

The comment at `handlers.py:1019-1027` (added by the pre-existing `update_fields`
fix, predating this design) is updated to describe the new flow (per-workflow
save under the guard; single explicit rename afterward) but the `filename` /
`archive_filename` exclusion it documents is kept — see point 2 above.

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
- **Regression: the racy case is already covered, not newly needed.** The
  scenario this design originally asked for a new test for — a workflow that
  reassigns metadata (tags + correspondent/storage path) while the document is
  subject to a filename template, asserting final DB filename and file location
  stay consistent — is already exercised by
  `test_document_updated_workflow_assignment_storage_path_persists_with_tag_assignment`
  in `test_workflows.py` (added by #13178). No new regression test is required
  for this; the refactor's job is to keep it passing **unchanged**.
- **Regression safety net** — the existing `test_workflows.py` suite (~100+
  tests; many `document_consumption_finished.send` sites plus many direct
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
3. Extract the move body from `update_filename_and_move_files` into a callable
   (updating the version-document recursive call site at `handlers.py:670-673`
   to call it directly); add the `ContextVar` guard; `run_workflows` invokes the
   move once after the run completes. The `filename` / `archive_filename`
   exclusion in the per-workflow save is kept; only the comment at
   `handlers.py:1019-1027` is updated to describe the new flow.

## Pain points addressed

- **Dual-mode** → eliminated by the `Protocol` + two contexts; no `use_overrides`.
  Still an open, unfixed problem in current code — this is the refactor's main
  remaining justification.
- **File staging** → `source_file` is a context property; side-channel args
  deleted. Still an open, unfixed problem in current code.
- **Rename race** → per-workflow save under a `ContextVar` guard that suppresses
  the mid-workflow rename; a single explicit rename runs once at the end against
  final state. **No longer an active bug** — #12389 and #13178 independently
  closed the two concrete failure modes (cross-process already-moved file;
  intra-workflow tag/m2m clobbering unsaved fields) by narrower means. The
  guard is now valuable as a single general mechanism replacing two
  independent point-fixes, not as a bug fix.
