# Ingestion Staging & Enqueue Unification — Design

**Date:** 2026-06-16
**Branch base:** `dev`
**Status:** Approved design (revised per critical review), pending implementation plan

## Problem

Every document that enters paperless converges on one operation: build a
`ConsumableDocument` + `DocumentMetadataOverrides`, stage the input file on disk,
and dispatch the `consume_file` Celery task with a `trigger_source` header. That
operation is hand-rolled at **five** sites today, plus a sixth internal one:

- consume-folder watcher — `document_consumer.py:346`
- API upload + Web UI — `views.py:3327` (one endpoint, two `DocumentSource` values)
- document-version upload — `views.py:2086`
- mail attachment — `mail.py:993`
- mail `.eml` whole-message — `mail.py:1084`
- barcode split children (internal re-enqueue) — `barcodes.py:190`/`227`

The duplication causes three concrete problems:

1. **Boilerplate divergence.** Each site repeats `SCRATCH_DIR.mkdir`, a per-file
   `tempfile.mkdtemp`, the payload write, the `magic` MIME sniff, the
   `consume_file` kwargs shape, and the `DocumentSource → PaperlessTask.TriggerSource`
   mapping. That mapping is even re-implemented a second time as
   `_SOURCE_TO_TRIGGER` inside `barcodes.py:198`.

2. **A scratch leak from split staging/cleanup ownership.** Staged sources create
   scratch input under `SCRATCH_DIR` that nothing ever fully removes:
   `ConsumerPlugin` unlinks only the input **file**, and only on the success path
   (`consumer.py:738`). The exact leak shape varies by site — mail attachments and
   API/version use `mkdtemp` + a file inside, so the **directory** is orphaned
   (empty after success, dir-with-file on failure); the mail `.eml` path uses
   `mkstemp` (`mail.py:~1034`), so it leaks a **file** directly in `SCRATCH_DIR` on
   failure. Either way there is no owner that removes the staged input on every
   terminal path.

3. **Three test seams for one operation.** `ConsumeTaskMixin` patches
   `documents.tasks.consume_file.apply_async` (`tests/utils.py:249`); the
   consumer-folder tests patch the module-local `consume_file`
   (`test_management_consumer.py:101`); mail patches the higher-level
   `queue_consumption_tasks`. There is no single canonical point to intercept
   "a document was enqueued."

Separately, the consumption task already has **two** working temp directories that
duplicate each other: `consume_file` opens one `TemporaryDirectory` and passes it
to every plugin (`tasks.py:220`), but `ConsumerPlugin` ignores that and opens its
_own_ second `TemporaryDirectory` (`consumer.py:408`).

## Goal

Introduce one small ingestion module that owns staging and enqueue, so each site
declares only its genuinely source-specific logic (how the overrides dict is
built). Give every ingested document a single per-document working directory that
holds the staged input _and_ all pipeline working artifacts, cleaned up as a unit
on every terminal path. Collapse the three test seams to one.

## Scope

In scope:

- New `src/documents/ingest.py`: the canonical `SOURCE_TO_TRIGGER` map,
  `build_consume_signature`, `enqueue_consumption`, and `stage_document`.
- `ConsumableDocument` gains `staging_dir: Path | None`.
- `consume_file` derives a per-document `work_root` from `staging_dir` and removes
  it on every terminal path; `ConsumerPlugin` reuses the handed-in working dir
  instead of opening a second one.
- Refactor all six enqueue sites (including the barcode split children) onto the
  new module.
- Update the shared test seam (`ConsumeTaskMixin`) and the consumer-folder tests;
  add unit tests for `ingest.py`.

Out of scope (explicitly — confirmed during exploration):

- **`bulk_edit.py`'s 8 dispatch sites (phase 2).** Bulk merge/split/version
  (`bulk_edit.py:485,588,661,727,811,844,938,961`) also build `ConsumableDocument`s
  and dispatch `consume_file`. They are deferred to a follow-up plan that adopts
  the seam this refactor establishes. Consequence: until phase 2, the "single
  canonical seam" is partial — those paths still call `consume_file` directly. The
  spec states this rather than implying full unification.
- **New poller sources (S3/SFTP/webhook).** They need infrastructure that does not
  exist (a scheduling/registration framework, per-source credential/config models,
  a generic already-seen dedup table, new `DocumentSource`/`TriggerSource` enum
  values). This refactor unifies the _last mile_ (staging + enqueue); it does not
  build poller infrastructure and should not be sold as doing so.
- **Finishing Gmail/Outlook OAuth.** Both already work via IMAP+XOAUTH2; the
  remaining items (`oauth.py:94` missing `else` guard, the callback
  `update_or_create` lookup-key bug, unpopulated username, no Graph API path) are
  independent bug fixes that neither need nor are needed by this refactor.
- **The `DocumentSource.WebUI` vs `ApiUpload` split** (a request-body boolean on
  one endpoint) — left as-is.
- Any entry-point / third-party plugin extensibility for sources.

## Decisions

Settled during brainstorming:

1. **Shape: a staging object + an enqueue seam, not per-source adapter classes.**
   Source-specific override-building stays inline at each site; only staging and
   dispatch are extracted. A `SourceAdapter` class hierarchy is premature (the
   pollers that would justify it are out of scope).
2. **Cleanup: an explicit lifecycle carried on `ConsumableDocument`.** A
   `staging_dir` field transfers ownership of the staged file from the enqueue
   site to the worker. No periodic sweep (the only residual leak window —
   broker accepts the task then loses it before execution — is negligibly small).
3. **Grouping: one per-document root holds everything.** The staged input and the
   task's working artifacts live under a single directory, removed by one
   `rmtree`. This also folds away `ConsumerPlugin`'s redundant second temp dir.
4. **One canonical dispatch seam: `enqueue_consumption`.** Tests patch it in one
   place — **but only because** of two implementation constraints the plan must
   enforce: (a) sites call it **module-qualified** (`ingest.enqueue_consumption(...)`,
   not a bare imported name), so a single `documents.ingest.enqueue_consumption`
   patch intercepts every site; (b) `build_consume_signature` passes
   `input_doc`/`overrides` as **keyword** args, so `Signature.kwargs` keeps the
   shape mail tests already assert on. Without both, the "one patch point" claim is
   false.

## Architecture

### New module `src/documents/ingest.py`

```python
SOURCE_TO_TRIGGER: dict[DocumentSource, PaperlessTask.TriggerSource] = { ... }
# the single source of truth; barcodes.py imports this instead of redefining it.

def build_consume_signature(
    input_doc: ConsumableDocument,
    overrides: DocumentMetadataOverrides | None = None,
) -> Signature:
    """Build the consume_file signature with the trigger_source header derived
    from input_doc.source. Returns a Celery Signature — the caller decides how to
    dispatch (direct .apply_async(), or collected into mail's chord)."""

def enqueue_consumption(
    input_doc: ConsumableDocument,
    overrides: DocumentMetadataOverrides | None = None,
) -> AsyncResult:
    """Canonical dispatch seam: build_consume_signature(...).apply_async().
    The single point tests patch to intercept 'a document was enqueued'."""

class StagedDocument:
    """Commit-on-success guard for a staged input file.

    Created via stage_document(). Owns a per-document work_root under SCRATCH_DIR
    until the caller calls release() (after successful dispatch), at which point
    ownership transfers to the consume_file task via input_doc.staging_dir.
    """
    input_doc: ConsumableDocument          # carries staging_dir = work_root
    def write(self, data: bytes) -> None: ...        # write payload into work_root
    def write_from(self, src: Path) -> None: ...     # copy an existing file in
    def release(self) -> None: ...                   # dispatch succeeded; don't clean
    # __enter__ -> self;  __exit__ -> if not released, rmtree(work_root)

@contextmanager
def stage_document(source: DocumentSource, *, name: str) -> Iterator[StagedDocument]:
    """mkdtemp a per-document work_root under SCRATCH_DIR, yield a StagedDocument
    to write into. MIME type is sniffed when the ConsumableDocument is built."""
```

### `ConsumableDocument.staging_dir` (`data_models.py`)

Add `staging_dir: Path | None = None`. It is the field that crosses the
enqueue→worker boundary (picklable; the HMAC-pickle Celery serializer is
unaffected). Folder source leaves it `None`; all staged sources set it to their
`work_root`.

### Ownership-transfer model

The staged file must outlive the synchronous enqueue and be consumed later by the
worker, so a context manager around the enqueue site cannot delete it. Ownership
transfers at the **successful-dispatch boundary**:

- **Enqueue side (`StagedDocument`):** owns `work_root` only until `release()`. If
  an exception occurs before/at dispatch (building overrides, writing the file,
  `apply_async` raising), `__exit__` runs without a prior `release()` and
  `rmtree`s `work_root` — closing the failure-path leak. After `release()`,
  `__exit__` is a no-op and the directory deliberately survives.
- **Worker side (`consume_file`):** once the task runs, the task owns `work_root`
  (via `input_doc.staging_dir`) and removes it in a `finally` on **every**
  terminal path.

### `consume_file` work_root + cleanup (`tasks.py`)

Replace the unconditional `TemporaryDirectory(dir=SCRATCH_DIR)` (`tasks.py:220`)
with a derived work_root:

- `input_doc.staging_dir` set → `work_root = staging_dir` (already holds the
  input). The task owns it and `rmtree`s it in a `finally` covering success,
  `StopConsumeTaskError`, `ConsumeFileDuplicateError`, and unexpected exceptions.
- `staging_dir is None` (folder) → `work_root` is a fresh `TemporaryDirectory`
  (auto-cleaned); the in-place original in `CONSUMPTION_DIR` is unlinked by
  `ConsumerPlugin` on success exactly as today.

The per-task working directory passed to plugins becomes a **subfolder of
work_root**, and `ConsumerPlugin` uses that handed-in directory for its working
copy instead of opening its own second `TemporaryDirectory` (`consumer.py:408`).
One tree per document; one cleanup.

### Barcode split children (`barcodes.py`)

The split re-enqueue produces each child via `stage_document` +
`build_consume_signature` using `SOURCE_TO_TRIGGER`, removing the sixth
hand-rolled site and the `_SOURCE_TO_TRIGGER` duplicate. **This is a
restructuring, not a swap:** today all children share a single `mkdtemp` dir
(`barcodes.py:188-194`, deliberately separate from the parent's `base_temp_dir`).
Each child must instead get its **own** work_root, because each child is a
separate `consume_file` task whose `finally` will `rmtree` its `staging_dir` — a
shared dir would let one child delete siblings' not-yet-consumed files. The
children already copy their split file out of the parent tree
(`copy_file_with_basic_stats`, `barcodes.py:211`), so the parent's work_root is
independently cleanable when the parent stops.

### Mail ownership boundary (the batch case — `mail.py`)

Mail is the one source that does **not** dispatch per file: `_handle_message`
collects N attachment signatures (and optionally the `.eml` signature), then
`queue_consumption_tasks` wraps them in a single `chord(...).delay()` _after_ the
loop (`mail.py:1014`). A per-file `release()` is therefore wrong — if `release()`
ran per attachment and the later chord dispatch threw, every staged file would be
orphaned, reopening the leak. **The ownership boundary is the whole message:**

```python
def _handle_message(...):
    with contextlib.ExitStack() as staging_stack:
        consume_tasks = []
        for att in attachments:               # and the .eml branch
            staged = staging_stack.enter_context(stage_document(MailFetch, name=...))
            staged.write(att.payload)
            consume_tasks.append(build_consume_signature(staged.input_doc, overrides))
        queue_consumption_tasks(consume_tasks, rule, message)   # chord(...).delay()
        for staged in staged_docs:
            staged.release()                  # only after the chord is dispatched
    # ExitStack __exit__: any un-released staged doc → rmtree (covers a chord-dispatch failure)
```

`queue_consumption_tasks` itself is unchanged. `build_consume_signature` **must
pass `input_doc`/`overrides` as keyword args** (`consume_file.s(input_doc=...,
overrides=...)`) so the resulting `Signature.kwargs` keeps the shape mail tests
assert on (`test_mail.py:389-390`).

### Call-site refactor (the external sites)

Folder/API/version collapse to: `with stage_document(...) as staged:
staged.write(...); overrides = DocumentMetadataOverrides(...source-specific...);
ingest.enqueue_consumption(staged.input_doc, overrides); staged.release()`. Folder
source has no payload to stage (the file is already in `CONSUMPTION_DIR`), so it
builds a `ConsumableDocument(..., staging_dir=None)` and calls
`ingest.enqueue_consumption` directly without `stage_document`. Mail uses the
`ExitStack` pattern above.

**Call style is module-qualified.** Sites do `from documents import ingest` and
call `ingest.enqueue_consumption(...)` / `ingest.build_consume_signature(...)` —
_not_ a bare imported name. This is what makes a single patch target
(`documents.ingest.enqueue_consumption`) intercept every site; a direct
`from documents.ingest import enqueue_consumption` would bind the name per-module
and force per-module patching (the existing `from documents.tasks import
consume_file` style is exactly why tests today need multiple patch targets).

## Data flow

```
folder / API / version site (synchronous, single dispatch)
  with stage_document(source, name=...) as staged:     # mkdtemp work_root, write input
      overrides = DocumentMetadataOverrides(... per-source ...)
      result = ingest.enqueue_consumption(staged.input_doc, overrides)
      staged.release()                                  # ownership → task
  # __exit__: rmtree(work_root) ONLY if release() never ran (pre-dispatch failure)
  # (folder source: no stage_document; ConsumableDocument(staging_dir=None) + enqueue_consumption)

mail site (synchronous, BATCH dispatch — see "Mail ownership boundary")
  with ExitStack() as staging_stack:                   # owns ALL of the message's staged docs
      build N signatures via ingest.build_consume_signature(... keyword args ...)
      queue_consumption_tasks(...)                      # one chord(...).delay()
      release() every staged doc                        # only after the chord dispatches
  # __exit__: rmtree any un-released work_root (a chord-dispatch failure cleans the whole batch)

consume_file task (async, later)
  work_root = input_doc.staging_dir or TemporaryDirectory(SCRATCH_DIR)
  try:
      run plugin chain (working files under work_root/work, input at work_root/...)
  finally:
      if input_doc.staging_dir: rmtree(work_root)       # all terminal paths
      # folder source: TemporaryDirectory auto-cleans; ConsumerPlugin unlinks original
```

## Error handling & edges

- **Double-sided collation — safe, but outside the work_root model.** It stops
  with `StopConsumeTaskError` to await the second half, and preserves that half by
  **`shutil.move(pdf_file, staging)`** to `SCRATCH_DIR/<staging-name>`
  (`double_sided.py:~134`) — a _move_, to a location _outside_ any work_root,
  performed **before** the stop. So `rmtree`-ing the parent work_root afterward is
  safe (the half already left the tree). Two consequences the plan must honor:
  (a) the preserved staging file lives in `SCRATCH_DIR`, is **never** covered by
  the per-document cleanup, and is cleaned by the second-half collate
  (`staging.unlink()`) or timeout as today — the "one root" framing does not
  extend to it; (b) the plan must verify the move-precedes-stop ordering, since it
  is load-bearing for the cleanup rule.
- **`ConsumerPlugin`'s own cleanup becomes partly redundant.** On success it
  unlinks `original_file` and `working_copy` (`consumer.py:738/740`), both of
  which now live inside work_root that the task `finally` `rmtree`s. The redundant
  unlinks are harmless but the plan should remove them for clarity, while keeping
  the qpdf `--replace-input` recovery (`unmodified_original`, `consumer.py:452+`)
  working when `working_copy` lives under work_root.
- **Folder source is intrinsically asymmetric** — its original lives in the
  watched dir, not a work_root. The "one root" model fully applies to staged
  sources; folder gets in-place-original (cleaned by `ConsumerPlugin` on success)
  plus an isolated per-task working root. This is correct, not a gap.
- **`staging_dir is None` must be a strict no-op.** Many integration tests call
  the real `consume_file` with hand-built `ConsumableDocument`s that never set
  `staging_dir` (`test_workflows.py`, `test_barcodes.py`, `test_double_sided.py`).
  The new work_root/`finally` logic must reduce to exactly today's behavior when
  `staging_dir is None`, or those currently-passing tests regress.
- **Duplicate/stop are not failures.** The worker `finally` cleans `work_root` on
  every terminal path, but a future quarantine feature (below) would relocate the
  input only on a genuine exception, never on `ConsumeFileDuplicateError` or
  `StopConsumeTaskError`.

## Testing

New `src/documents/tests/` unit tests for `ingest.py` (pytest-style classes,
`mocker`, type-annotated):

- `stage_document` cleans `work_root` on an exception before `release()`, and does
  **not** clean it after `release()` (ownership transferred) — i.e. the leak is
  closed and the file survives for the task.
- `build_consume_signature` sets the correct `trigger_source` header for each
  `DocumentSource` (drives `SOURCE_TO_TRIGGER`).
- `enqueue_consumption` dispatches and returns the `AsyncResult`.
- `consume_file` removes `staging_dir` on success, on `StopConsumeTaskError`, on
  duplicate, and on exception; and does nothing destructive when `staging_dir`
  is `None` (folder source) beyond today's behavior.
- The `trigger_source` header survives `Signature.set(headers=...).apply_async()`
  **and** chord dispatch (a guard against chord wrapping dropping per-signature
  headers — the one path where header propagation could silently break).

Existing tests — the migration is centralized but **not** trivial:

- `ConsumeTaskMixin` (`tests/utils.py:242-280`): repoint the patch from
  `documents.tasks.consume_file.apply_async` to `documents.ingest.enqueue_consumption`,
  **and rewrite both assert helpers** — they currently read the raw `apply_async`
  shape `call_args.kwargs["kwargs"]["input_doc"]` (`assert_queue_consumption_task_call_args`
  at :259 and `get_all_consume_task_call_args` at :267). With the seam called
  positionally as `enqueue_consumption(input_doc, overrides)`, those become
  `call_args.args[0]/[1]`. This is concentrated in the mixin, so its ~15 helper
  call sites in `test_api_documents.py` + 1 in `test_barcodes.py` pass once the
  helpers are fixed — but it is a helper rewrite, not a one-line change.
- The consumer-folder tests (`test_management_consumer.py`, ~15 methods) repoint
  `mock_consume_file_delay` to the seam.
- `test_api_document_versions.py` (3 tests) patches the **module-local**
  `documents.views.consume_file` — repoint to `documents.views`-qualified usage or
  the central seam.
- Real-task integration tests that build `ConsumableDocument`s by hand and call
  `consume_file` directly (`test_workflows.py` ~15, `test_barcodes.py` ~5,
  `test_double_sided.py` ~9) exercise the `staging_dir is None` path; they should
  stay green **iff** that path is a strict no-op (see Error handling).
- Mail tests that patch `queue_consumption_tasks` stay untouched **only if**
  `build_consume_signature` uses keyword args (above); otherwise their assertions
  on `Signature.kwargs` (`test_mail.py`, `test_mail_nfc.py`, `test_preprocessor.py`,
  ~15 methods) break.

**Realistic blast radius: ~70–90 in-scope test methods** route through the
changed seams (the export-style "one patch point" still holds, but the helper
rewrite + keyword-arg + module-qualified constraints are what make it true). This
excludes `bulk_edit.py`'s ~35 tests, which are deferred with their migration to
the bulk-edit phase-2 plan.

## Enabled future work (not built here)

**Quarantine failed files for review.** Because failure cleanup collapses to the
single `finally` in `consume_file` that owns `work_root`, a "save failed
documents to a review folder" feature becomes a one-site change: on a genuine
exception (not duplicate/stop), move the staged input to a configured
`PAPERLESS_FAILED_DIR` instead of `rmtree`-ing it, then drop the working
subfolder. `staging_dir` already names the file and marks it relocatable, and the
terminal result type is already known at that point, so the feature applies
uniformly to every staged source from one edit. It would also unify a current
inconsistency (failed folder files loop in `CONSUMPTION_DIR`; failed mail/API
files are lost). Note: this refactor changes mail/API failure behavior from
"silently leak the temp file" to "cleanly delete it," so until a review folder
lands, a failed mail/API input is gone — mild pressure to build quarantine sooner
if it is wanted.

## Risks

- **Cleanup must run on all terminal paths.** The worker `finally` must cover
  success, `StopConsumeTaskError`, `ConsumeFileDuplicateError`, and unexpected
  exceptions, or the leak reappears. Covered by the `consume_file` tests above.
- **Test-seam migration churn.** ~70–90 in-scope test methods route through the
  changed seams. Mitigation: concentrated in `ConsumeTaskMixin` (helper rewrite)
  and a few fixtures — but it is a helper rewrite plus a keyword-arg and a
  module-qualified-call contract, not a one-line repoint. The plan must encode all
  three constraints or the "single patch point" promise is false.
- **Mail batch ownership.** The `ExitStack` boundary (release all only after the
  chord dispatches; rmtree-all on dispatch failure) is load-bearing; getting it
  per-attachment instead reopens the leak for the whole message.
- **Double-sided ordering.** The move-precedes-stop assumption
  (`shutil.move` to `SCRATCH_DIR` at `double_sided.py:~134`) must be verified in
  the plan before relying on it for cleanup.
- **`bulk_edit.py` is deferred, not done.** Until the phase-2 plan migrates its 8
  dispatch sites, the "single canonical seam" is partial: bulk merge/split/version
  still call `consume_file` directly. The spec states this honestly rather than
  implying full unification.
