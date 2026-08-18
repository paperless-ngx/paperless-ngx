# Ingestion Staging & Enqueue Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract staging + enqueue of `consume_file` into one `documents/ingest.py`, give every staged document a single per-document `work_root` cleaned on all terminal paths (fixing the scratch leak), and collapse the three test seams to one.

**Architecture:** `ingest.py` owns `SOURCE_TO_TRIGGER`, `build_consume_signature` (returns a Celery `Signature`), `enqueue_consumption` (dispatches it), and `stage_document` (a commit-on-success guard owning a per-document temp dir). `ConsumableDocument` gains `staging_dir`; `consume_file` derives a `work_root` from it and `rmtree`s it in a `finally`. Sites call the seam **module-qualified** so one patch target intercepts all.

**Tech Stack:** Python ≥3.11, Django, Celery (`Signature`/`chord`), pytest + pytest-mock + factory-boy. Backend tests run on the Linux VM (Windows host); `ruff` runs locally.

**Spec:** `docs/superpowers/specs/2026-06-16-ingestion-staging-unification-design.md`

---

## Conventions for every task

- **Run backend tests on the VM:** `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "<targets>"` (never locally — the lockfile is linux/macOS only).
- **Lint locally:** `ruff check <paths> && ruff format <paths>` (global ruff, not `uv run`).
- **Tests are pytest-style** where new: classes, `@pytest.mark.django_db` on the class only where DB is needed, `mocker`, `parametrize`, full type annotations. Do **not** convert the existing Django-`TestCase` suites; only repoint their patch targets where a task says so.
- **Two load-bearing constraints from the spec** (the whole "one patch point" rests on them):
  1. Every site calls the seam **module-qualified**: `from documents import ingest` then `ingest.enqueue_consumption(...)` / `ingest.build_consume_signature(...)` — never `from documents.ingest import enqueue_consumption`.
  2. `build_consume_signature` builds the signature with **keyword** args (`consume_file.s(input_doc=…, overrides=…)`), so `Signature.kwargs` keeps the shape mail tests assert on.

## File structure

- **Create** `src/documents/ingest.py` — `SOURCE_TO_TRIGGER`, `build_consume_signature`, `enqueue_consumption`, `StagedDocument`, `stage_document`.
- **Create** `src/documents/tests/test_ingest.py` — unit tests for the module + `consume_file` cleanup.
- **Modify** `src/documents/data_models.py` — add `ConsumableDocument.staging_dir`.
- **Modify** `src/documents/tasks.py` — `consume_file` derives `work_root`, cleans `staging_dir`.
- **Modify** `src/documents/management/commands/document_consumer.py` — folder site.
- **Modify** `src/documents/views.py` — API/WebUI + version sites.
- **Modify** `src/paperless_mail/mail.py` — attachment + `.eml` sites via `ExitStack`.
- **Modify** `src/documents/barcodes.py` — split children via the module + per-child work_roots.
- **Modify** `src/documents/tests/utils.py` — rewrite `ConsumeTaskMixin`.
- **Modify** consumer/version/mail test files — repoint patch targets (per task).

---

## Task 1: `ingest.py` — trigger map + signature + dispatch seam

**Files:**

- Create: `src/documents/ingest.py`
- Test: `src/documents/tests/test_ingest.py`

- [ ] **Step 1: Write the failing tests**

Create `src/documents/tests/test_ingest.py`:

```python
import pytest

from documents import ingest
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import PaperlessTask


class TestTriggerMapping:
    @pytest.mark.parametrize(
        ("source", "trigger"),
        [
            (DocumentSource.ConsumeFolder, PaperlessTask.TriggerSource.FOLDER_CONSUME),
            (DocumentSource.ApiUpload, PaperlessTask.TriggerSource.API_UPLOAD),
            (DocumentSource.MailFetch, PaperlessTask.TriggerSource.EMAIL_CONSUME),
            (DocumentSource.WebUI, PaperlessTask.TriggerSource.WEB_UI),
        ],
    )
    def test_source_maps_to_trigger(
        self,
        source: DocumentSource,
        trigger: PaperlessTask.TriggerSource,
    ) -> None:
        assert ingest.SOURCE_TO_TRIGGER[source] == trigger


@pytest.mark.django_db
class TestBuildConsumeSignature:
    def test_signature_uses_keyword_args_and_header(self, tmp_path) -> None:
        f = tmp_path / "a.pdf"
        f.write_bytes(b"%PDF-1.4 test")
        doc = ConsumableDocument(source=DocumentSource.ApiUpload, original_file=f)
        overrides = DocumentMetadataOverrides(title="x")

        sig = ingest.build_consume_signature(doc, overrides)

        # keyword args preserved (mail tests depend on this)
        assert sig.kwargs["input_doc"] is doc
        assert sig.kwargs["overrides"] is overrides
        assert (
            sig.options["headers"]["trigger_source"]
            == PaperlessTask.TriggerSource.API_UPLOAD
        )

    def test_enqueue_dispatches_and_returns_result(self, tmp_path, mocker) -> None:
        f = tmp_path / "a.pdf"
        f.write_bytes(b"%PDF-1.4 test")
        doc = ConsumableDocument(source=DocumentSource.ApiUpload, original_file=f)
        sentinel = object()
        apply = mocker.patch.object(
            ingest,
            "build_consume_signature",
            return_value=mocker.Mock(apply_async=mocker.Mock(return_value=sentinel)),
        )
        result = ingest.enqueue_consumption(doc, None)
        apply.assert_called_once_with(doc, None)
        assert result is sentinel
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_ingest.py -v"`
Expected: FAIL with `ModuleNotFoundError: No module named 'documents.ingest'`.

- [ ] **Step 3: Implement the trigger map + signature + seam**

Create `src/documents/ingest.py`:

```python
from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pathvalidate
from django.conf import settings

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import PaperlessTask
from documents.utils import copy_file_with_basic_stats

if TYPE_CHECKING:
    from collections.abc import Iterator

    from celery import Signature
    from celery.result import AsyncResult


SOURCE_TO_TRIGGER: dict[DocumentSource, PaperlessTask.TriggerSource] = {
    DocumentSource.ConsumeFolder: PaperlessTask.TriggerSource.FOLDER_CONSUME,
    DocumentSource.ApiUpload: PaperlessTask.TriggerSource.API_UPLOAD,
    DocumentSource.MailFetch: PaperlessTask.TriggerSource.EMAIL_CONSUME,
    DocumentSource.WebUI: PaperlessTask.TriggerSource.WEB_UI,
}


def build_consume_signature(
    input_doc: ConsumableDocument,
    overrides: DocumentMetadataOverrides | None = None,
) -> Signature:
    """Build the consume_file signature with the trigger_source header derived
    from input_doc.source. Keyword args are required (mail tests assert on
    Signature.kwargs)."""
    # Local import avoids a tasks <-> ingest import cycle.
    from documents.tasks import consume_file

    trigger_source = SOURCE_TO_TRIGGER.get(
        input_doc.source,
        PaperlessTask.TriggerSource.MANUAL,
    )
    return consume_file.s(input_doc=input_doc, overrides=overrides).set(
        headers={"trigger_source": trigger_source},
    )


def enqueue_consumption(
    input_doc: ConsumableDocument,
    overrides: DocumentMetadataOverrides | None = None,
) -> AsyncResult:
    """Canonical single-dispatch seam. Tests patch documents.ingest.enqueue_consumption."""
    return build_consume_signature(input_doc, overrides).apply_async()
```

- [ ] **Step 4: Run to verify it passes**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_ingest.py -v"`
Expected: PASS.

- [ ] **Step 5: Lint**

Run: `ruff check src/documents/ingest.py src/documents/tests/test_ingest.py && ruff format src/documents/ingest.py src/documents/tests/test_ingest.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/documents/ingest.py src/documents/tests/test_ingest.py
git commit -m "Feature: add ingest module (trigger map, signature builder, enqueue seam)"
```

---

## Task 2: `stage_document` — the commit-on-success staging guard

**Files:**

- Modify: `src/documents/ingest.py`
- Test: `src/documents/tests/test_ingest.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_ingest.py`:

```python
class TestStageDocument:
    def test_writes_file_and_builds_consumable(self, tmp_path, settings) -> None:
        settings.SCRATCH_DIR = tmp_path
        with ingest.stage_document(DocumentSource.MailFetch, name="a.pdf") as staged:
            staged.write(b"%PDF-1.4 hello")
            doc = staged.build(mailrule_id=7)
            staged.release()
        assert doc.source == DocumentSource.MailFetch
        assert doc.mailrule_id == 7
        assert doc.staging_dir is not None
        assert doc.original_file.read_bytes() == b"%PDF-1.4 hello"
        # released → work_root survives for the task
        assert doc.original_file.exists()

    def test_cleans_up_on_exception_before_release(self, tmp_path, settings) -> None:
        settings.SCRATCH_DIR = tmp_path
        captured: dict = {}
        with pytest.raises(RuntimeError):
            with ingest.stage_document(DocumentSource.ApiUpload, name="a.pdf") as staged:
                staged.write(b"data")
                captured["root"] = staged.input_doc.staging_dir
                raise RuntimeError("boom")
        assert not captured["root"].exists()  # leak closed

    def test_cleans_up_on_normal_exit_without_release(self, tmp_path, settings) -> None:
        settings.SCRATCH_DIR = tmp_path
        with ingest.stage_document(DocumentSource.ApiUpload, name="a.pdf") as staged:
            staged.write(b"data")
            root = staged.input_doc.staging_dir
            # caller forgot to release / never dispatched
        assert not root.exists()

    def test_sanitizes_name(self, tmp_path, settings) -> None:
        settings.SCRATCH_DIR = tmp_path
        with ingest.stage_document(DocumentSource.ApiUpload, name="../../evil.pdf") as staged:
            staged.write(b"d")
            doc = staged.build()
            staged.release()
        assert ".." not in doc.original_file.name
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_ingest.py::TestStageDocument -v"`
Expected: FAIL with `AttributeError: module 'documents.ingest' has no attribute 'stage_document'`.

- [ ] **Step 3: Implement `StagedDocument` + `stage_document`**

Append to `ingest.py`:

```python
class StagedDocument:
    """Owns a per-document work_root until release() transfers ownership to the task.

    See stage_document(). On context exit, if release() was not called, the whole
    work_root is removed (closing the pre-dispatch leak); after release() the
    directory survives and is owned by consume_file via input_doc.staging_dir.
    """

    def __init__(self, source: DocumentSource, work_root: Path, file_path: Path) -> None:
        self._source = source
        self._work_root = work_root
        self._file_path = file_path
        self._released = False
        self._input_doc: ConsumableDocument | None = None

    @property
    def path(self) -> Path:
        return self._file_path

    def write(self, data: bytes) -> None:
        self._file_path.write_bytes(data)

    def write_from(self, src: Path) -> None:
        copy_file_with_basic_stats(src, self._file_path)

    def build(self, **extra) -> ConsumableDocument:
        """Construct the ConsumableDocument (the file must already be written —
        ConsumableDocument.__post_init__ runs magic.from_file on it)."""
        self._input_doc = ConsumableDocument(
            source=self._source,
            original_file=self._file_path,
            staging_dir=self._work_root,
            **extra,
        )
        return self._input_doc

    @property
    def input_doc(self) -> ConsumableDocument:
        if self._input_doc is None:
            return self.build()
        return self._input_doc

    def release(self) -> None:
        self._released = True

    @property
    def released(self) -> bool:
        return self._released

    def _discard(self) -> None:
        if self._work_root.exists():
            shutil.rmtree(self._work_root, ignore_errors=True)


@contextmanager
def stage_document(source: DocumentSource, *, name: str) -> Iterator[StagedDocument]:
    """Create a per-document work_root under SCRATCH_DIR and yield a StagedDocument
    to write the payload into. Removes work_root on exit unless release() was called."""
    settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    work_root = Path(
        tempfile.mkdtemp(dir=settings.SCRATCH_DIR, prefix="paperless-stage-"),
    ).resolve()
    safe_name = pathvalidate.sanitize_filename(name) or "no-name-attachment"
    staged = StagedDocument(source, work_root, work_root / safe_name)
    try:
        yield staged
    finally:
        if not staged.released:
            staged._discard()
```

- [ ] **Step 4: Run to verify it passes**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_ingest.py -v"`
Expected: PASS (all of Task 1 + Task 2).

- [ ] **Step 5: Lint & commit**

```bash
ruff check src/documents/ingest.py src/documents/tests/test_ingest.py && ruff format src/documents/ingest.py src/documents/tests/test_ingest.py
git add src/documents/ingest.py src/documents/tests/test_ingest.py
git commit -m "Feature: add stage_document commit-on-success staging guard"
```

---

## Task 3: `ConsumableDocument.staging_dir` + `consume_file` work_root cleanup

**Files:**

- Modify: `src/documents/data_models.py:161-187`
- Modify: `src/documents/tasks.py:181-278`
- Test: `src/documents/tests/test_ingest.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_ingest.py`:

```python
from documents import tasks


@pytest.mark.django_db
class TestConsumeFileWorkRoot:
    def _staged_doc(self, settings, tmp_path) -> ConsumableDocument:
        settings.SCRATCH_DIR = tmp_path
        root = tmp_path / "paperless-stage-x"
        root.mkdir()
        f = root / "a.pdf"
        f.write_bytes(b"%PDF-1.4 test")
        return ConsumableDocument(
            source=DocumentSource.ApiUpload,
            original_file=f,
            staging_dir=root,
        )

    def test_staging_dir_removed_on_plugin_exception(
        self,
        settings,
        tmp_path,
        mocker,
    ) -> None:
        doc = self._staged_doc(settings, tmp_path)
        # Force the plugin loop to raise.
        mocker.patch.object(
            tasks,
            "ConsumerPreflightPlugin",
            side_effect=RuntimeError("boom"),
        )
        with pytest.raises(RuntimeError):
            tasks.consume_file(doc)
        assert not doc.staging_dir.exists()

    def test_none_staging_dir_is_noop(self, settings, tmp_path, mocker) -> None:
        # Folder-style doc: no staging_dir. consume_file must not try to rmtree.
        settings.SCRATCH_DIR = tmp_path
        f = tmp_path / "loose.pdf"
        f.write_bytes(b"%PDF-1.4 test")
        doc = ConsumableDocument(source=DocumentSource.ConsumeFolder, original_file=f)
        assert doc.staging_dir is None
        mocker.patch.object(
            tasks,
            "ConsumerPreflightPlugin",
            side_effect=RuntimeError("boom"),
        )
        with pytest.raises(RuntimeError):
            tasks.consume_file(doc)
        assert f.exists()  # the loose file is NOT removed by consume_file
```

(Note: `consume_file` is a bound task; calling it directly runs it synchronously in-process, which is fine for these focused tests.)

- [ ] **Step 2: Run to verify it fails**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_ingest.py::TestConsumeFileWorkRoot -v"`
Expected: FAIL — `ConsumableDocument` has no `staging_dir`, and `consume_file` doesn't clean it.

- [ ] **Step 3: Add the `staging_dir` field**

In `src/documents/data_models.py`, add the field to `ConsumableDocument` (before the `init=False` `mime_type`):

```python
    source: DocumentSource
    original_file: Path
    root_document_id: int | None = None
    original_path: Path | None = None
    mailrule_id: int | None = None
    staging_dir: Path | None = None
    mime_type: str = dataclasses.field(init=False, default=None)
```

`Path | None` is picklable, so the HMAC-pickle Celery serializer is unaffected.

- [ ] **Step 4: Derive `work_root` and clean it in `consume_file`**

In `src/documents/tasks.py`, add `import shutil` and `from contextlib import contextmanager` (if not present), then add a helper above `consume_file`:

```python
@contextmanager
def _consume_working_dir(input_doc: ConsumableDocument):
    """Yield the plugins' working directory.

    Staged sources reuse their per-document work_root (a `work/` subfolder);
    folder source gets a throwaway TemporaryDirectory. Removal of the staged
    work_root itself happens in consume_file's finally, so it covers every
    terminal path (success, stop, duplicate, exception)."""
    if input_doc.staging_dir is not None:
        work = Path(input_doc.staging_dir) / "work"
        work.mkdir(parents=True, exist_ok=True)
        yield work
    else:
        with TemporaryDirectory(dir=settings.SCRATCH_DIR) as tmp:
            yield Path(tmp)
```

Then change the body of `consume_file` so the `with` uses the helper and the
`finally` removes `staging_dir`:

```python
    token = consume_task_id.set((self.request.id or "")[:8])
    try:
        if overrides is None:
            overrides = DocumentMetadataOverrides()

        plugins: list[type[ConsumeTaskPlugin]] = (
            [ConsumerPreflightPlugin, ConsumerPlugin]
            if input_doc.root_document_id is not None
            else [
                ConsumerPreflightPlugin,
                AsnCheckPlugin,
                CollatePlugin,
                BarcodePlugin,
                AsnCheckPlugin,  # Re-run ASN check after barcode reading
                WorkflowTriggerPlugin,
                ConsumerPlugin,
            ]
        )

        with (
            ProgressManager(
                overrides.filename or input_doc.original_file.name,
                self.request.id,
            ) as status_mgr,
            _consume_working_dir(input_doc) as tmp_dir,
        ):
            msg = None
            for plugin_class in plugins:
                # ... unchanged plugin loop ...
                ...
        return msg
    finally:
        consume_task_id.reset(token)
        if input_doc.staging_dir is not None:
            shutil.rmtree(input_doc.staging_dir, ignore_errors=True)
```

Only the `with` line and the `finally` change; the plugin loop body is untouched
(`tmp_dir` is still a `Path`). The early `return ConsumeFileStoppedResult(...)` /
`return ConsumeFileDuplicateResult(...)` and the re-`raise` all pass through the
`finally`, so the staged work_root is removed on every terminal path.

- [ ] **Step 5: Run the new tests + the full consume/import regression**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_ingest.py src/documents/tests/test_consumer.py -v"`
Expected: PASS. The `staging_dir is None` path is byte-for-byte today's behavior, so existing consumer tests stay green.

- [ ] **Step 6: Lint & commit**

```bash
ruff check src/documents/data_models.py src/documents/tasks.py && ruff format src/documents/data_models.py src/documents/tasks.py
git add src/documents/data_models.py src/documents/tasks.py src/documents/tests/test_ingest.py
git commit -m "Feature: consume_file owns and cleans the staged work_root"
```

---

## Task 4: Migrate the consume-folder site

**Files:**

- Modify: `src/documents/management/commands/document_consumer.py:344-357`
- Test: `src/documents/tests/test_management_consumer.py:99-103`

- [ ] **Step 1: Repoint the consumer test fixture**

In `src/documents/tests/test_management_consumer.py`, change the mock fixture (lines ~99-103) to patch the seam instead of the module-local task:

```python
@pytest.fixture
def mock_consume_file_delay(mocker: MockerFixture) -> MagicMock:
    """Mock the enqueue seam used by the consumer."""
    return mocker.patch(
        "documents.management.commands.document_consumer.ingest.enqueue_consumption",
    )
```

Then, wherever tests assert on the queued call, they now read positional args.
Update the two assertion shapes used in this file:

- `mock_consume_file_delay.apply_async.assert_called_once()` → `mock_consume_file_delay.assert_called_once()`
- `call_args.kwargs["kwargs"]["input_doc"]` → `call_args.args[0]`; `["overrides"]` → `call_args.args[1]`

- [ ] **Step 2: Run to verify the consumer tests now fail**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_management_consumer.py -v"`
Expected: FAIL — the folder site still calls `consume_file.apply_async`, not the seam, so the mock is never called.

- [ ] **Step 3: Migrate the folder enqueue site**

In `src/documents/management/commands/document_consumer.py`, add `from documents import ingest` at the top, and replace the enqueue block (lines ~344-357):

```python
    # Queue for consumption
    try:
        logger.info(f"Adding {filepath} to the task queue")
        ingest.enqueue_consumption(
            ConsumableDocument(
                source=DocumentSource.ConsumeFolder,
                original_file=filepath,
            ),
            DocumentMetadataOverrides(tag_ids=tag_ids),
        )
    except Exception:
        logger.exception(f"Error while queuing document {filepath}")
```

Folder source builds a `ConsumableDocument` with `staging_dir=None` (the default)
because the file already lives in `CONSUMPTION_DIR`; it does not use
`stage_document`. The `trigger_source` header now comes from `SOURCE_TO_TRIGGER`
inside `build_consume_signature`, so the explicit `headers=` is gone. Remove the
now-unused `consume_file` import from this module if present.

- [ ] **Step 4: Run to verify the consumer tests pass**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_management_consumer.py -v"`
Expected: PASS.

- [ ] **Step 5: Lint & commit**

```bash
ruff check src/documents/management/commands/document_consumer.py src/documents/tests/test_management_consumer.py && ruff format src/documents/management/commands/document_consumer.py src/documents/tests/test_management_consumer.py
git add src/documents/management/commands/document_consumer.py src/documents/tests/test_management_consumer.py
git commit -m "Refactor: route consume-folder ingest through ingest.enqueue_consumption"
```

---

## Task 5: Migrate API/WebUI + version sites and rewrite `ConsumeTaskMixin`

These are coupled: the ~40 API tests run through `ConsumeTaskMixin`, so the mixin
rewrite and the site migration land together.

**Files:**

- Modify: `src/documents/tests/utils.py:242-274`
- Modify: `src/documents/views.py:3275-3338` (PostDocumentView) and `:2036-2098` (update_version)
- Modify: `src/documents/tests/test_api_document_versions.py` (patch target)

- [ ] **Step 1: Rewrite `ConsumeTaskMixin` to patch the seam**

Replace `ConsumeTaskMixin` (`src/documents/tests/utils.py:242-274`):

```python
class ConsumeTaskMixin:
    """Mocks the canonical enqueue seam and decodes its (input_doc, overrides) args."""

    def setUp(self) -> None:
        self.consume_file_patcher = mock.patch(
            "documents.ingest.enqueue_consumption",
        )
        self.consume_file_mock = self.consume_file_patcher.start()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        self.consume_file_patcher.stop()

    def assert_queue_consumption_task_call_args(
        self,
    ) -> tuple[ConsumableDocument, DocumentMetadataOverrides]:
        self.consume_file_mock.assert_called_once()
        args = self.consume_file_mock.call_args.args
        return (args[0], args[1])

    def get_all_consume_task_call_args(
        self,
    ) -> Iterator[tuple[ConsumableDocument, DocumentMetadataOverrides]]:
        self.consume_file_mock.assert_called()
        for call in self.consume_file_mock.call_args_list:
            yield (call.args[0], call.args[1])
```

This patches `documents.ingest.enqueue_consumption`, which intercepts every site
that calls it module-qualified (folder already does; API/version after Step 3).
Mail does not use `enqueue_consumption`, so this mock does not affect mail tests.

- [ ] **Step 2: Run to verify API tests now fail**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_api_documents.py -k upload -v"`
Expected: FAIL — `PostDocumentView` still calls `consume_file.apply_async`, so the seam mock is never called (`assert_called_once` fails). Confirms the mixin is wired but the site isn't migrated yet.

- [ ] **Step 3: Migrate `PostDocumentView.post`**

In `src/documents/views.py`, ensure `from documents import ingest` is imported,
then replace the staging + dispatch (lines ~3275-3338) with a `stage_document`
block:

```python
        from_webui = serializer.validated_data.get("from_webui")
        source = DocumentSource.WebUI if from_webui else DocumentSource.ApiUpload

        t = int(mktime(datetime.now().timetuple()))

        with ingest.stage_document(source, name=doc_name) as staged:
            staged.write(doc_data)
            os.utime(staged.path, times=(t, t))
            input_doc = staged.build()

            custom_fields = None
            if isinstance(cf, dict) and cf:
                custom_fields = cf
            elif isinstance(cf, list) and cf:
                custom_fields = dict.fromkeys(cf, None)

            input_doc_overrides = DocumentMetadataOverrides(
                filename=doc_name,
                title=title,
                correspondent_id=correspondent_id,
                document_type_id=document_type_id,
                storage_path_id=storage_path_id,
                tag_ids=tag_ids,
                created=created,
                asn=archive_serial_number,
                owner_id=request.user.id,
                custom_fields=custom_fields,
            )

            async_task = ingest.enqueue_consumption(input_doc, input_doc_overrides)
            staged.release()

        return Response(async_task.id)
```

The old `SCRATCH_DIR.mkdir` + `mkdtemp` + `write_bytes` + the explicit
`headers=` block are all replaced by `stage_document` + `enqueue_consumption`.

- [ ] **Step 4: Migrate `update_version`**

In `src/documents/views.py` `update_version` (lines ~2036-2098), replace its
`mkdtemp`/`write`/`consume_file.apply_async` with the same pattern, preserving its
specific fields (`root_document_id`, `version_label`, `actor_id`):

```python
        with ingest.stage_document(DocumentSource.WebUI, name=doc_name) as staged:
            staged.write(doc_data)
            input_doc = staged.build(root_document_id=root_doc.pk)
            overrides = DocumentMetadataOverrides(
                version_label=version_label,
                actor_id=request.user.id,
            )
            async_task = ingest.enqueue_consumption(input_doc, overrides)
            staged.release()
```

(Match the exact existing variable names for `doc_name`/`doc_data`/`version_label`
at that site; the shape above is the transformation.)

- [ ] **Step 5: Repoint the version test patch target**

In `src/documents/tests/test_api_document_versions.py`, change the patch from
`documents.views.consume_file` to `documents.ingest.enqueue_consumption`, and the
assertion from `consume_mock.apply_async.call_args.kwargs["kwargs"]["input_doc"]`
to `consume_mock.call_args.args[0]` (and `args[1]` for overrides).

- [ ] **Step 6: Run the API + version suites**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_api_documents.py src/documents/tests/test_api_document_versions.py src/documents/tests/test_api_post_document_nfc.py -v"`
Expected: PASS. `test_api_post_document_nfc.py` patches `documents.tasks.consume_file.apply_async` directly — repoint that fixture to `documents.ingest.enqueue_consumption` and read `call_args.args[0]` if it fails.

- [ ] **Step 7: Lint & commit**

```bash
ruff check src/documents/views.py src/documents/tests/utils.py && ruff format src/documents/views.py src/documents/tests/utils.py
git add src/documents/views.py src/documents/tests/utils.py src/documents/tests/test_api_document_versions.py src/documents/tests/test_api_post_document_nfc.py
git commit -m "Refactor: route API/WebUI/version ingest through the staging seam"
```

---

## Task 6: Migrate mail (attachment + `.eml`) with `ExitStack`

**Files:**

- Modify: `src/paperless_mail/mail.py` (`_handle_message` ~790-835, `_process_attachments` ~893-1024, `_process_eml` ~1026-1097)
- Test: `src/paperless_mail/tests/test_mail.py`, `test_mail_nfc.py` (verify, likely no change)

- [ ] **Step 1: Wrap the message's staging in an `ExitStack`**

`build_consume_signature` already uses keyword args, so the mail tests that patch
`paperless_mail.mail.queue_consumption_tasks` and assert on
`consume_task.kwargs["input_doc"]` keep working. Add `import contextlib` and
`from documents import ingest` to `mail.py`. Restructure `_handle_message` so all
of a message's staged docs share one `ExitStack`, released only after
`queue_consumption_tasks` dispatches:

```python
    def _handle_message(self, message, rule) -> int:
        processed = 0
        with contextlib.ExitStack() as staging_stack:
            consume_tasks: list[Signature] = []
            staged_docs: list[ingest.StagedDocument] = []

            if rule.consumption_scope in (...EML scopes...):
                self._process_eml(message, rule, staging_stack, consume_tasks, staged_docs)
            if rule.consumption_scope in (...attachment scopes...):
                processed += self._process_attachments(
                    message, rule, staging_stack, consume_tasks, staged_docs,
                )

            if consume_tasks:
                queue_consumption_tasks(
                    consume_tasks=consume_tasks, rule=rule, message=message,
                )
                for staged in staged_docs:
                    staged.release()
        return processed
```

(Match the file's actual scope-branching; the load-bearing parts are: one
`ExitStack` for the whole message, `release()` only after `queue_consumption_tasks`
returns, so a chord-dispatch failure unwinds the stack and rmtrees every staged
work_root for the message.)

- [ ] **Step 2: Stage each attachment via the stack**

Replace the attachment staging (`mail.py:893-1024`) inside `_process_attachments`:

```python
                staged = staging_stack.enter_context(
                    ingest.stage_document(DocumentSource.MailFetch, name=att.filename or ""),
                )
                staged.write(att.payload)
                input_doc = staged.build(mailrule_id=rule.pk)
                staged_docs.append(staged)

                attachment_name = input_doc.original_file.name
                doc_overrides = DocumentMetadataOverrides(
                    title=title,
                    filename=attachment_name,
                    correspondent_id=correspondent.id if correspondent else None,
                    document_type_id=doc_type.id if doc_type else None,
                    tag_ids=tag_ids,
                    owner_id=(
                        rule.owner.id
                        if (rule.assign_owner_from_rule and rule.owner)
                        else None
                    ),
                )
                consume_tasks.append(
                    ingest.build_consume_signature(input_doc, doc_overrides),
                )
```

The old `SCRATCH_DIR.mkdir` + `mkdtemp` + `write_bytes` + `consume_file.s(...).set(...)`
are gone; `stage_document` handles the temp dir and `build_consume_signature` the
header. Do the analogous replacement in `_process_eml` (`mail.py:1026-1097`),
staging the `.eml` bytes and building the signature the same way.

- [ ] **Step 3: Run the mail suites**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_mail/tests/test_mail.py src/paperless_mail/tests/test_mail_nfc.py src/paperless_mail/tests/test_preprocessor.py -v"`
Expected: PASS. The assertions on `consume_task.kwargs["input_doc"]`/`["overrides"]`
hold because `build_consume_signature` uses keyword args. If any fail on
`input_doc.original_file` existence, ensure `staged.write(...)` precedes
`staged.build(...)`.

- [ ] **Step 4: Lint & commit**

```bash
ruff check src/paperless_mail/mail.py && ruff format src/paperless_mail/mail.py
git add src/paperless_mail/mail.py src/paperless_mail/tests/
git commit -m "Refactor: stage mail attachments/eml via ExitStack + ingest seam"
```

---

## Task 7: Migrate barcode split children (per-child work_roots)

**Files:**

- Modify: `src/documents/barcodes.py:183-230`
- Test: `src/documents/tests/test_barcodes.py`

- [ ] **Step 1: Replace the shared dir + `_SOURCE_TO_TRIGGER` with per-child staging**

In `src/documents/barcodes.py`, add `from documents import ingest`, delete the
local `_SOURCE_TO_TRIGGER` dict (lines ~198-207) and the shared `mkdtemp`
(lines ~188-194), and stage each child separately:

```python
            # Create the split document tasks — each child gets its OWN work_root,
            # so its consume_file task can clean it independently.
            for new_document in self.separate_pages(separator_pages):
                with ingest.stage_document(
                    self.input_doc.source,
                    name=new_document.name,
                ) as staged:
                    staged.write_from(new_document)
                    input_doc = staged.build(
                        mailrule_id=self.input_doc.mailrule_id,
                        original_path=self.input_doc.original_file,
                    )
                    task = ingest.enqueue_consumption(input_doc, self.metadata)
                    staged.release()
                logger.info(f"Created new task {task.id} for {new_document.name}")
```

This removes the sixth hand-rolled site and the duplicated trigger map; each child
is independently cleaned by its own `consume_file` `finally`. The parent's own
temp tree is unaffected (children are copied out via `write_from`).

- [ ] **Step 2: Run the barcode suite**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_barcodes.py -v"`
Expected: PASS. If a test patched `documents.tasks.consume_file.apply_async` to
inspect child dispatch, repoint it to `documents.ingest.enqueue_consumption` and
read `call_args.args[0]`.

- [ ] **Step 3: Lint & commit**

```bash
ruff check src/documents/barcodes.py && ruff format src/documents/barcodes.py
git add src/documents/barcodes.py src/documents/tests/test_barcodes.py
git commit -m "Refactor: barcode split children use per-child staging + ingest seam"
```

---

## Task 8: Fold `ConsumerPlugin`'s redundant working dir into the handed-in `tmp_dir`

This is the consolidation noted in the spec; do it last so the regression net is
already stable. **Keep `ConsumerPlugin`'s success-path unlink of `original_file`** —
folder source needs it (its loose file in `CONSUMPTION_DIR` is removed on success).

**Files:**

- Modify: `src/documents/consumer.py:408-414`
- Test: `src/documents/tests/test_consumer.py`

- [ ] **Step 1: Use the handed-in working dir instead of a second `TemporaryDirectory`**

`ConsumerPlugin` already receives the task's working dir as `self.base_tmp_dir`
(the `tmp_dir` arg from `tasks.py:227-233`). Replace its own
`tempfile.TemporaryDirectory(...)` (`consumer.py:408`) with a subfolder of that
handed-in dir:

```python
        # For the actual work, copy the file into the task-provided working dir
        tmpdir = self.base_tmp_dir / "consumer"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.working_copy = tmpdir / Path(self.filename)
        copy_file_with_basic_stats(self.input_doc.original_file, self.working_copy)
        self.unmodified_original = None
        # ... rest of the method body unchanged, de-indented out of the old `with` ...
```

Confirm the qpdf `--replace-input` recovery (`unmodified_original`,
`consumer.py:452+`) still resolves paths under `tmpdir`. Removing the `with` means
the working copy is now cleaned by the task's `work_root`/`TemporaryDirectory`
teardown instead of the plugin's own context — which is the intended consolidation.

- [ ] **Step 2: Run the consumer + full ingest regression**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_consumer.py src/documents/tests/test_ingest.py -v"`
Expected: PASS.

- [ ] **Step 3: Lint & commit**

```bash
ruff check src/documents/consumer.py && ruff format src/documents/consumer.py
git add src/documents/consumer.py
git commit -m "Refactor: ConsumerPlugin reuses the task working dir"
```

---

## Task 9: Full verification

- [ ] **Step 1: Run every affected suite together**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_ingest.py src/documents/tests/test_consumer.py src/documents/tests/test_api_documents.py src/documents/tests/test_api_document_versions.py src/documents/tests/test_management_consumer.py src/documents/tests/test_barcodes.py src/documents/tests/test_double_sided.py src/documents/tests/test_workflows.py src/paperless_mail/tests/ -v"`
Expected: PASS, no failures.

- [ ] **Step 2: Type-check on the VM (pyrefly)**

```bash
tar czf - src pyproject.toml uv.lock .pyrefly-baseline.json | ssh -o BatchMode=yes -p 2244 trenton@localhost 'tar xzf - -C ~/projects/paperless-ngx'
ssh -o BatchMode=yes -p 2244 trenton@localhost 'bash -lc "cd ~/projects/paperless-ngx && uv run pyrefly check"'
```

Expected: no new errors beyond the baseline.

- [ ] **Step 3: Final lint**

Run: `ruff check src/documents/ src/paperless_mail/mail.py && ruff format --check src/documents/ingest.py src/documents/tasks.py src/documents/views.py src/paperless_mail/mail.py src/documents/barcodes.py src/documents/consumer.py`
Expected: clean.

- [ ] **Step 4: Confirm the leak is closed (manual reasoning check)**

Verify by inspection that every staged source now sets `staging_dir` and that
`consume_file`'s `finally` removes it: API (Task 5), version (Task 5), mail (Task 6),
barcode children (Task 7). Folder source sets `staging_dir=None` and is unchanged.

---

## Notes for the implementer

- **The "one patch point" is real only with both constraints** (Conventions): module-qualified calls + keyword-arg signatures. If you import `enqueue_consumption` as a bare name into a site, `documents.ingest.enqueue_consumption` patches will silently miss it and tests will fail confusingly.
- **`bulk_edit.py` is intentionally NOT in this plan** (8 dispatch sites, ~35 tests) — it's the phase-2 follow-up. Its `consume_file.apply_async`/`.s` calls keep working unchanged; do not touch them here.
- **Double-sided** is out of the work_root model: its first-half preservation is a `shutil.move` to `SCRATCH_DIR` (`double_sided.py:~134`) performed before the `StopConsumeTaskError`, so the parent `rmtree` in Task 3 is safe. `test_double_sided.py` must stay green (Task 9).
- **`staging_dir is None` must remain a strict no-op** in `consume_file` — the many real-task integration tests (`test_workflows.py`, `test_barcodes.py`, `test_double_sided.py`) build `ConsumableDocument`s by hand without it.
- **Enabled future work (not here):** the single `finally` in `consume_file` is the one hook for a future "quarantine failed files to a review folder" feature — relocate `staging_dir` instead of `rmtree` on a genuine exception.
