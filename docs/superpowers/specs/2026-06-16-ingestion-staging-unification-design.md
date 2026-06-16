# Ingestion Staging & Enqueue Unification — Design

**Date:** 2026-06-16
**Branch base:** `dev`
**Status:** Approved design, pending implementation plan

## Problem

Every document that enters paperless converges on one operation: build a
`ConsumableDocument` + `DocumentMetadataOverrides`, stage the input file on disk,
and dispatch the `consume_file` Celery task with a `trigger_source` header. That
operation is hand-rolled at **five** sites today, plus a sixth internal one:

- consume-folder watcher — `document_consumer.py:342`
- API upload + Web UI — `views.py:3181` (one endpoint, two `DocumentSource` values)
- document-version upload — `views.py:1964`
- mail attachment — `mail.py:899`
- mail `.eml` whole-message — `mail.py:987`
- barcode split children (internal re-enqueue) — `barcodes.py:190`/`227`

The duplication causes three concrete problems:

1. **Boilerplate divergence.** Each site repeats `SCRATCH_DIR.mkdir`, a per-file
   `tempfile.mkdtemp`, the payload write, the `magic` MIME sniff, the
   `consume_file` kwargs shape, and the `DocumentSource → PaperlessTask.TriggerSource`
   mapping. That mapping is even re-implemented a second time as
   `_SOURCE_TO_TRIGGER` inside `barcodes.py:198`.

2. **A temp-directory leak from split staging/cleanup ownership.** Staged sources
   (mail, API, version, barcode-child) create a temp **directory** via `mkdtemp`
   and write the input into it, but nothing ever removes that directory:
   `ConsumerPlugin` only unlinks the input **file**, and only on the success path
   (`consumer.py`). Every mail/API ingest therefore orphans an empty
   `SCRATCH_DIR/paperless-*/` directory forever, and on failure the input file
   leaks entirely.

3. **Three test seams for one operation.** `ConsumeTaskMixin` patches
   `documents.tasks.consume_file.apply_async` (`tests/utils.py:249`); the
   consumer-folder tests patch the module-local `consume_file`
   (`test_management_consumer.py:101`); mail patches the higher-level
   `queue_consumption_tasks`. There is no single canonical point to intercept
   "a document was enqueued."

Separately, the consumption task already has **two** working temp directories that
duplicate each other: `consume_file` opens one `TemporaryDirectory` and passes it
to every plugin (`tasks.py:220`), but `ConsumerPlugin` ignores that and opens its
_own_ second `TemporaryDirectory` (`consumer.py:417`).

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
   place.

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
copy instead of opening its own second `TemporaryDirectory` (`consumer.py:417`).
One tree per document; one cleanup.

### Barcode split children (`barcodes.py`)

The split re-enqueue produces each child via `stage_document` +
`build_consume_signature` using `SOURCE_TO_TRIGGER`, removing the sixth
hand-rolled site and the `_SOURCE_TO_TRIGGER` duplicate. Each child gets its own
work_root; the parent's work_root is cleaned when the parent task stops.

### Call-site refactor (the five external sites)

Each collapses to: `with stage_document(...) as staged: staged.write(...);
overrides = DocumentMetadataOverrides(...source-specific...);
enqueue_consumption(staged.input_doc, overrides); staged.release()`. Folder source
has no payload to stage (the file is already in `CONSUMPTION_DIR`), so it builds a
`ConsumableDocument(..., staging_dir=None)` and calls `enqueue_consumption`
directly without `stage_document`. Mail builds each signature with
`build_consume_signature`, appends to its chord list, dispatches the chord
unchanged, then `release()`s each staged document.

## Data flow

```
enqueue site (synchronous)
  with stage_document(source, name=...) as staged:     # mkdtemp work_root, write input
      overrides = DocumentMetadataOverrides(... per-source ...)
      result = enqueue_consumption(staged.input_doc, overrides)   # folder/API/version
              # or: sig = build_consume_signature(...); chord.append(sig)   # mail
      staged.release()                                  # ownership → task
  # __exit__: rmtree(work_root) ONLY if release() never ran (pre-dispatch failure)

consume_file task (async, later)
  work_root = input_doc.staging_dir or TemporaryDirectory(SCRATCH_DIR)
  try:
      run plugin chain (working files under work_root/work, input at work_root/...)
  finally:
      if input_doc.staging_dir: rmtree(work_root)       # all terminal paths
      # folder source: TemporaryDirectory auto-cleans; ConsumerPlugin unlinks original
```

## Error handling & edges

- **Double-sided collation** preserves the first half across tasks: it stops with
  `StopConsumeTaskError` to await the second half, but copies that content out to
  its own staging file (`double_sided.py:74`) **before** the stop. Removing the
  parent `work_root` afterward is therefore safe. The plan MUST verify this
  copy-out-precedes-stop ordering, since it is load-bearing for the cleanup rule.
- **Folder source is intrinsically asymmetric** — its original lives in the
  watched dir, not a work_root. The "one root" model fully applies to staged
  sources; folder gets in-place-original (cleaned by `ConsumerPlugin` on success)
  plus an isolated per-task working root. This is correct, not a gap.
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

Existing tests — the single-seam payoff and its migration cost:

- `ConsumeTaskMixin` (`tests/utils.py:249`) repoints its patch from
  `documents.tasks.consume_file.apply_async` to the new `enqueue_consumption`
  seam, and its assert helper inspects `(input_doc, overrides)` directly. Its ~40
  API tests then pass unchanged through the mixin.
- The consumer-folder tests (`test_management_consumer.py`, ~15 methods) repoint
  `mock_consume_file_delay` from the module-local `consume_file` to the seam.
- Mail tests that patch `queue_consumption_tasks` stay untouched (the chord
  boundary is preserved).

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
- **Test-seam migration churn.** ~55 existing tests route through the two patch
  points being repointed. Mitigation: the changes are concentrated in
  `ConsumeTaskMixin` and the consumer test fixture, not spread across every test.
- **Double-sided ordering.** The copy-out-before-stop assumption must be verified
  in the plan before relying on it for cleanup.
