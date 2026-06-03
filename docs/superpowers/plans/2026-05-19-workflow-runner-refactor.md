# Workflow Runner Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `use_overrides` dual-mode branching in `run_workflows` with a polymorphic `WorkflowRunContext`, and make the workflow-execution → file-rename sequence deterministic via a `ContextVar` guard.

**Architecture:** A new `documents/workflows/context.py` module defines a `WorkflowRunContext` `Protocol` and two implementations — `ConsumptionContext` (wraps `ConsumableDocument` + `DocumentMetadataOverrides`) and `PersistedContext` (wraps a real `Document`). `run_workflows` becomes a flat match-and-dispatch loop with no mode flag. A module-level `ContextVar` guard suppresses `update_filename_and_move_files` for the duration of a workflow run; the file rename is invoked once, explicitly, after the run.

**Tech Stack:** Python 3.12+, Django, Celery, pytest (pytest-xdist), `uv`, `ruff`.

**Reference spec:** `docs/superpowers/specs/2026-05-19-workflow-runner-refactor-design.md`

---

## Conventions for every task

- All Python commands run from `src/`. Tests: `uv run pytest`. Lint: `ruff check --fix` then `ruff format` (global `ruff`, **not** `uv run ruff`).
- New test code: group tests under classes, put `@pytest.mark.django_db` per class where DB is needed, fully type-annotate every fixture parameter, fixture return type, and test signature.
- Commit after each task with the message shown in its final step.

## File structure

| File                                           | Responsibility                                                                                                                        | Change                  |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| `src/documents/workflows/context.py`           | `ContextVar` guard, `WorkflowRunContext` Protocol, `ConsumptionContext`, `PersistedContext`, `build_workflow_context` factory         | **Create**              |
| `src/documents/signals/handlers.py`            | `run_workflows` rewritten as flat loop; `update_filename_and_move_files` split into receiver + `move_files_for_document`              | Modify                  |
| `src/documents/workflows/actions.py`           | Drop `build_workflow_action_context`; `execute_email_action` / `execute_webhook_action` take `source_file` instead of `original_file` | Modify                  |
| `src/documents/tests/test_workflow_context.py` | Unit tests for the guard and the two contexts                                                                                         | **Create**              |
| `src/documents/tests/test_workflows.py`        | Existing regression suite (must stay green) + new guard/race regression tests                                                         | Modify (add tests only) |

---

## Task 1: ContextVar guard

**Files:**

- Create: `src/documents/workflows/context.py`
- Test: `src/documents/tests/test_workflow_context.py`

- [ ] **Step 1: Write the failing test**

Create `src/documents/tests/test_workflow_context.py`:

```python
from documents.workflows.context import workflow_guard
from documents.workflows.context import workflow_run_in_progress


class TestWorkflowGuard:
    def test_guard_not_set_by_default(self) -> None:
        assert workflow_run_in_progress() is False

    def test_guard_set_inside_context_manager(self) -> None:
        with workflow_guard():
            assert workflow_run_in_progress() is True
        assert workflow_run_in_progress() is False

    def test_guard_is_reentrant(self) -> None:
        with workflow_guard():
            with workflow_guard():
                assert workflow_run_in_progress() is True
            assert workflow_run_in_progress() is True
        assert workflow_run_in_progress() is False

    def test_guard_resets_on_exception(self) -> None:
        try:
            with workflow_guard():
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert workflow_run_in_progress() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest documents/tests/test_workflow_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'documents.workflows.context'`

- [ ] **Step 3: Create the module with the guard**

Create `src/documents/workflows/context.py` with only the guard for now:

```python
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

logger = logging.getLogger("paperless.workflows")

_workflow_in_progress: ContextVar[bool] = ContextVar(
    "workflow_in_progress",
    default=False,
)


def workflow_run_in_progress() -> bool:
    """
    True while run_workflows is executing on the current thread/context.

    update_filename_and_move_files checks this and early-returns, so the file
    rename does not race the workflow's own metadata mutations.
    """
    return _workflow_in_progress.get()


@contextmanager
def workflow_guard() -> Iterator[None]:
    """
    Suppress update_filename_and_move_files for the duration of a workflow run.

    Token-based reset keeps this reentrancy-safe: nested workflow_guard() blocks
    (e.g. a workflow whose action triggers another save) restore the previous
    value rather than unconditionally clearing the flag.
    """
    token = _workflow_in_progress.set(True)
    try:
        yield
    finally:
        _workflow_in_progress.reset(token)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest documents/tests/test_workflow_context.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Lint and commit**

```bash
ruff check --fix src/documents/workflows/context.py src/documents/tests/test_workflow_context.py
ruff format src/documents/workflows/context.py src/documents/tests/test_workflow_context.py
git add src/documents/workflows/context.py src/documents/tests/test_workflow_context.py
git commit -m "Add ContextVar guard for workflow runner"
```

---

## Task 2: `WorkflowRunContext` Protocol + `ConsumptionContext`

**Files:**

- Modify: `src/documents/workflows/context.py`
- Test: `src/documents/tests/test_workflow_context.py`

The `ConsumptionContext` absorbs the `use_overrides=True` branches currently in
`run_workflows` (`handlers.py:854-1010`) and `build_workflow_action_context`
(`actions.py:33,53-83`).

- [ ] **Step 1: Write the failing test**

Append to `src/documents/tests/test_workflow_context.py`:

```python
import pytest

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import Correspondent
from documents.models import WorkflowTrigger
from documents.workflows.context import ConsumptionContext


@pytest.mark.django_db
class TestConsumptionContext:
    @pytest.fixture
    def consumable(self, tmp_path) -> ConsumableDocument:
        staged = tmp_path / "staged.pdf"
        staged.write_bytes(b"%PDF-1.4")
        return ConsumableDocument(
            source=DocumentSource.ConsumeFolder,
            original_file=staged,
        )

    def test_source_and_staged_file_are_the_staged_path(
        self,
        consumable: ConsumableDocument,
    ) -> None:
        overrides = DocumentMetadataOverrides()
        ctx = ConsumptionContext(
            WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            consumable,
            overrides,
        )
        assert ctx.source_file == consumable.original_file
        assert ctx.staged_file == consumable.original_file
        assert ctx.target is consumable

    def test_assignment_mutates_overrides_not_db(
        self,
        consumable: ConsumableDocument,
    ) -> None:
        correspondent = Correspondent.objects.create(name="ACME")
        overrides = DocumentMetadataOverrides()
        ctx = ConsumptionContext(
            WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            consumable,
            overrides,
        )

        class FakeAction:
            assign_correspondent = correspondent
            assign_document_type = None
            assign_storage_path = None
            assign_owner = None
            assign_title = None
            has_assign_tags = False
            has_assign_view_users = False
            has_assign_view_groups = False
            has_assign_change_users = False
            has_assign_change_groups = False
            has_assign_custom_fields = False

        ctx.apply_assignment(FakeAction(), logging_group=None)
        assert overrides.correspondent_id == correspondent.pk

    def test_log_action_collects_messages(
        self,
        consumable: ConsumableDocument,
    ) -> None:
        ctx = ConsumptionContext(
            WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            consumable,
            DocumentMetadataOverrides(),
        )
        ctx.log_action("hello", logging_group=None)
        assert ctx.messages == ["hello"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest documents/tests/test_workflow_context.py::TestConsumptionContext -v`
Expected: FAIL with `ImportError: cannot import name 'ConsumptionContext'`

- [ ] **Step 3: Add the Protocol and `ConsumptionContext`**

Add to `src/documents/workflows/context.py` (after the guard). Add these imports at the top of the file:

```python
import uuid
from pathlib import Path
from typing import Protocol

from django.contrib.auth.models import User
from django.utils import timezone

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowRun
from documents.models import WorkflowTrigger
from documents.workflows.mutations import apply_assignment_to_overrides
from documents.workflows.mutations import apply_removal_to_overrides
```

Then append:

```python
class WorkflowRunContext(Protocol):
    """
    Uniform surface a workflow action operates on, independent of whether the
    run targets a freshly-consumed document (overrides) or a persisted one.
    """

    trigger_type: WorkflowTrigger.WorkflowTriggerType

    @property
    def target(self) -> Document | ConsumableDocument:
        """The object passed to matching and to email/webhook/trash actions."""
        ...

    @property
    def source_file(self) -> Path:
        """Best-effort current on-disk location of the document file."""
        ...

    @property
    def staged_file(self) -> Path | None:
        """
        The staged (pre-final-move) path, when the file is not yet at its
        final storage location; otherwise None. Used by password removal.
        """
        ...

    def refresh(self, logging_group: uuid.UUID | None) -> bool:
        """Reload state before matching. Return False to stop the run."""
        ...

    def build_placeholder_context(self) -> dict:
        """Context dict for email/webhook placeholder parsing."""
        ...

    def apply_assignment(
        self,
        action: WorkflowAction,
        logging_group: uuid.UUID | None,
    ) -> None: ...

    def apply_removal(
        self,
        action: WorkflowAction,
        logging_group: uuid.UUID | None,
    ) -> None: ...

    def log_action(self, message: str, logging_group: uuid.UUID | None) -> None:
        """Record an 'applying action' message."""
        ...

    def persist(self) -> None:
        """Commit accumulated mutations (no-op for the consumption flow)."""
        ...

    def record_run(self, workflow: Workflow) -> None:
        """Create the WorkflowRun audit row."""
        ...

    def finalize_file_location(self) -> None:
        """Run the one-time file rename after the workflow run completes."""
        ...


class ConsumptionContext:
    """Workflow run against a document still being consumed."""

    def __init__(
        self,
        trigger_type: WorkflowTrigger.WorkflowTriggerType,
        consumable: ConsumableDocument,
        overrides: DocumentMetadataOverrides,
    ) -> None:
        self.trigger_type = trigger_type
        self.consumable = consumable
        self.overrides = overrides
        self.messages: list[str] = []

    @property
    def target(self) -> Document | ConsumableDocument:
        return self.consumable

    @property
    def source_file(self) -> Path:
        return self.consumable.original_file

    @property
    def staged_file(self) -> Path | None:
        return self.consumable.original_file

    def refresh(self, logging_group: uuid.UUID | None) -> bool:
        return True

    def build_placeholder_context(self) -> dict:
        overrides = self.overrides
        correspondent_obj = (
            Correspondent.objects.filter(pk=overrides.correspondent_id).first()
            if overrides.correspondent_id
            else None
        )
        document_type_obj = (
            DocumentType.objects.filter(pk=overrides.document_type_id).first()
            if overrides.document_type_id
            else None
        )
        owner_obj = (
            User.objects.filter(pk=overrides.owner_id).first()
            if overrides.owner_id
            else None
        )
        filename = (
            self.consumable.original_file if self.consumable.original_file else ""
        )
        return {
            "title": overrides.title
            if overrides.title
            else str(self.consumable.original_file),
            "doc_url": "",
            "correspondent": correspondent_obj.name if correspondent_obj else "",
            "document_type": document_type_obj.name if document_type_obj else "",
            "owner_username": owner_obj.username if owner_obj else "",
            "filename": filename,
            "current_filename": filename,
            "added": timezone.localtime(timezone.now()),
            "created": overrides.created,
            "id": "",
        }

    def apply_assignment(
        self,
        action: WorkflowAction,
        logging_group: uuid.UUID | None,
    ) -> None:
        apply_assignment_to_overrides(action, self.overrides)

    def apply_removal(
        self,
        action: WorkflowAction,
        logging_group: uuid.UUID | None,
    ) -> None:
        apply_removal_to_overrides(action, self.overrides)

    def log_action(self, message: str, logging_group: uuid.UUID | None) -> None:
        self.messages.append(message)

    def persist(self) -> None:
        return None

    def record_run(self, workflow: Workflow) -> None:
        WorkflowRun.objects.create(
            workflow=workflow,
            type=self.trigger_type,
            document=None,
        )

    def finalize_file_location(self) -> None:
        return None
```

> Note: the `build_placeholder_context` body is moved verbatim from the
> `use_overrides` branch of `build_workflow_action_context` (`actions.py:53-83`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest documents/tests/test_workflow_context.py::TestConsumptionContext -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Lint and commit**

```bash
ruff check --fix src/documents/workflows/context.py src/documents/tests/test_workflow_context.py
ruff format src/documents/workflows/context.py src/documents/tests/test_workflow_context.py
git add src/documents/workflows/context.py src/documents/tests/test_workflow_context.py
git commit -m "Add WorkflowRunContext protocol and ConsumptionContext"
```

---

## Task 3: `PersistedContext` + `build_workflow_context` factory

**Files:**

- Modify: `src/documents/workflows/context.py`
- Test: `src/documents/tests/test_workflow_context.py`

`PersistedContext` absorbs the `use_overrides=False` branches of `run_workflows`
(`handlers.py:896-1005`) and `build_workflow_action_context` (`actions.py:35-51`).

- [ ] **Step 1: Write the failing test**

Append to `src/documents/tests/test_workflow_context.py`:

```python
from documents.workflows.context import PersistedContext
from documents.workflows.context import build_workflow_context


@pytest.mark.django_db
class TestPersistedContext:
    @pytest.fixture
    def document(self) -> Document:
        return Document.objects.create(
            title="doc",
            mime_type="application/pdf",
            checksum="abc123",
        )

    def test_source_file_is_document_source_path_without_staged(
        self,
        document: Document,
    ) -> None:
        ctx = PersistedContext(
            WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
            document,
            staged_file=None,
        )
        assert ctx.source_file == document.source_path
        assert ctx.staged_file is None
        assert ctx.target is document

    def test_source_file_prefers_staged_path(
        self,
        document: Document,
        tmp_path,
    ) -> None:
        staged = tmp_path / "staged.pdf"
        staged.write_bytes(b"%PDF-1.4")
        ctx = PersistedContext(
            WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            document,
            staged_file=staged,
        )
        assert ctx.source_file == staged
        assert ctx.staged_file == staged

    def test_refresh_returns_false_when_document_deleted(
        self,
        document: Document,
    ) -> None:
        ctx = PersistedContext(
            WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
            document,
            staged_file=None,
        )
        Document.objects.filter(pk=document.pk).delete()
        assert ctx.refresh(logging_group=None) is False


@pytest.mark.django_db
class TestBuildWorkflowContext:
    def test_overrides_present_builds_consumption_context(self, tmp_path) -> None:
        from documents.data_models import DocumentSource

        consumable = ConsumableDocument(
            source=DocumentSource.ConsumeFolder,
            original_file=tmp_path / "f.pdf",
        )
        ctx = build_workflow_context(
            trigger_type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            document=consumable,
            overrides=DocumentMetadataOverrides(),
            staged_file=None,
        )
        assert isinstance(ctx, ConsumptionContext)

    def test_no_overrides_builds_persisted_context(self) -> None:
        document = Document.objects.create(
            title="d",
            mime_type="application/pdf",
            checksum="zzz",
        )
        ctx = build_workflow_context(
            trigger_type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
            document=document,
            overrides=None,
            staged_file=None,
        )
        assert isinstance(ctx, PersistedContext)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest documents/tests/test_workflow_context.py::TestPersistedContext -v`
Expected: FAIL with `ImportError: cannot import name 'PersistedContext'`

- [ ] **Step 3: Add `PersistedContext` and the factory**

Add these imports to `src/documents/workflows/context.py`:

```python
from documents.workflows.mutations import apply_assignment_to_document
from documents.workflows.mutations import apply_removal_to_document
```

Append to `src/documents/workflows/context.py`:

```python
# Fields a workflow ASSIGNMENT/REMOVAL action can set directly on a Document.
# Deliberately excludes filename / archive_filename: those are managed only by
# move_files_for_document. A workflow never sets them, and writing a stale
# in-memory value here would revert a concurrent (cross-process) file move.
# modified has auto_now=True but is not auto-added when update_fields is given.
_WORKFLOW_SAVE_FIELDS = [
    "title",
    "correspondent",
    "document_type",
    "storage_path",
    "owner",
    "modified",
]


class PersistedContext:
    """Workflow run against a document already in the database."""

    def __init__(
        self,
        trigger_type: WorkflowTrigger.WorkflowTriggerType,
        document: Document,
        staged_file: Path | None,
    ) -> None:
        self.trigger_type = trigger_type
        self.document = document
        self._staged_file = staged_file

    @property
    def target(self) -> Document | ConsumableDocument:
        return self.document

    @property
    def source_file(self) -> Path:
        return self._staged_file if self._staged_file else self.document.source_path

    @property
    def staged_file(self) -> Path | None:
        return self._staged_file

    def refresh(self, logging_group: uuid.UUID | None) -> bool:
        try:
            # run_workflows may be called repeatedly from bulk_update_documents;
            # refresh so matching data is current and we do not overwrite work
            # done by another process.
            self.document.refresh_from_db()
        except Document.DoesNotExist:
            logger.info(
                "Document no longer exists, skipping remaining workflows",
                extra={"group": logging_group},
            )
            return False
        if self.document.is_deleted:
            logger.info(
                "Document was moved to trash, skipping remaining workflows",
                extra={"group": logging_group},
            )
            return False
        return True

    def build_placeholder_context(self) -> dict:
        from django.conf import settings

        document = self.document
        return {
            "title": document.title,
            "doc_url": f"{settings.PAPERLESS_URL}{settings.BASE_URL}documents/{document.pk}/",
            "correspondent": document.correspondent.name
            if document.correspondent
            else "",
            "document_type": document.document_type.name
            if document.document_type
            else "",
            "owner_username": document.owner.username if document.owner else "",
            "filename": document.original_filename or "",
            "current_filename": document.filename or "",
            "added": timezone.localtime(document.added),
            "created": document.created,
            "id": document.pk,
        }

    def apply_assignment(
        self,
        action: WorkflowAction,
        logging_group: uuid.UUID | None,
    ) -> None:
        apply_assignment_to_document(action, self.document, logging_group)

    def apply_removal(
        self,
        action: WorkflowAction,
        logging_group: uuid.UUID | None,
    ) -> None:
        apply_removal_to_document(action, self.document)

    def log_action(self, message: str, logging_group: uuid.UUID | None) -> None:
        logger.info(message, extra={"group": logging_group})

    def persist(self) -> None:
        # limit title to 128 characters
        self.document.title = self.document.title[:128]
        self.document.save(update_fields=_WORKFLOW_SAVE_FIELDS)

    def record_run(self, workflow: Workflow) -> None:
        WorkflowRun.objects.create(
            workflow=workflow,
            type=self.trigger_type,
            document=self.document,
        )

    def finalize_file_location(self) -> None:
        # Imported here to avoid a circular import (handlers imports this module).
        from documents.signals.handlers import move_files_for_document

        try:
            self.document.refresh_from_db()
        except Document.DoesNotExist:
            return
        if self.document.is_deleted:
            return
        move_files_for_document(self.document)


def build_workflow_context(
    *,
    trigger_type: WorkflowTrigger.WorkflowTriggerType,
    document: Document | ConsumableDocument,
    overrides: DocumentMetadataOverrides | None,
    staged_file: Path | None,
) -> WorkflowRunContext:
    """
    Pick the context implementation from the call shape: a non-None `overrides`
    means the consumption flow (ConsumableDocument); otherwise a persisted
    Document.
    """
    if overrides is not None:
        assert isinstance(document, ConsumableDocument)
        return ConsumptionContext(trigger_type, document, overrides)
    assert isinstance(document, Document)
    return PersistedContext(trigger_type, document, staged_file)
```

> Note: `build_placeholder_context` here is moved verbatim from the
> non-`use_overrides` branch of `build_workflow_action_context`
> (`actions.py:35-51`). `_WORKFLOW_SAVE_FIELDS` and `persist()` reproduce the
> save at `handlers.py:987-996` — keep the field list and the comment.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest documents/tests/test_workflow_context.py -v`
Expected: PASS (all tests, ~13)

- [ ] **Step 5: Lint and commit**

```bash
ruff check --fix src/documents/workflows/context.py src/documents/tests/test_workflow_context.py
ruff format src/documents/workflows/context.py src/documents/tests/test_workflow_context.py
git add src/documents/workflows/context.py src/documents/tests/test_workflow_context.py
git commit -m "Add PersistedContext and build_workflow_context factory"
```

---

## Task 4: Extract `move_files_for_document` from the rename receiver

**Files:**

- Modify: `src/documents/signals/handlers.py:431-667`

This task is a pure extraction — no behavior change yet. The guard check is
added in Task 6.

- [ ] **Step 1: Confirm the regression baseline is green**

Run: `uv run pytest documents/tests/test_file_handling.py -q`
Expected: PASS (records the pre-change baseline for the rename logic)

- [ ] **Step 2: Split the function**

In `src/documents/signals/handlers.py`, replace the `update_filename_and_move_files`
definition (currently `def update_filename_and_move_files(...)` at line 434,
through the end of its body at line 667) with two definitions:

```python
@receiver(models.signals.post_save, sender=CustomFieldInstance, weak=False)
@receiver(models.signals.m2m_changed, sender=Document.tags.through, weak=False)
@receiver(models.signals.post_save, sender=Document, weak=False)
def update_filename_and_move_files(
    sender,
    instance: Document | CustomFieldInstance,
    **kwargs,
) -> None:
    if isinstance(instance, CustomFieldInstance):
        if not _filename_template_uses_custom_fields(instance.document):
            return
        instance = instance.document

    move_files_for_document(instance)


def move_files_for_document(instance: Document) -> None:
    def validate_move(instance, old_path: Path, new_path: Path, root: Path) -> None:
        ...  # body unchanged from current lines 444-463
```

Move the entire body currently between line 444 (`def validate_move`) and line
667 into `move_files_for_document`, **unchanged**, with one edit: the recursive
call at the end (currently `handlers.py:660-667`) must call the new function:

```python
    # Keep version files in sync with root
    if instance.root_document_id is None:
        for version_doc in Document.objects.filter(root_document_id=instance.pk).only(
            "pk",
        ):
            move_files_for_document(version_doc)
```

- [ ] **Step 3: Run the rename tests**

Run: `uv run pytest documents/tests/test_file_handling.py -q`
Expected: PASS (identical to Step 1 — extraction is behavior-preserving)

- [ ] **Step 4: Run the workflow suite**

Run: `uv run pytest documents/tests/test_workflows.py -q`
Expected: PASS (unchanged)

- [ ] **Step 5: Lint and commit**

```bash
ruff check --fix src/documents/signals/handlers.py
ruff format src/documents/signals/handlers.py
git add src/documents/signals/handlers.py
git commit -m "Extract move_files_for_document from rename receiver"
```

---

## Task 5: Rewrite `run_workflows` to use contexts

**Files:**

- Modify: `src/documents/signals/handlers.py` (`run_workflows`, `run_workflows_added`)
- Modify: `src/documents/workflows/actions.py` (`execute_email_action`, `execute_webhook_action`, delete `build_workflow_action_context`)

This removes the `use_overrides` flag, the `caller_supplied_original_file`
flag, and the `original_file` threading into `execute_*` helpers. It does **not**
yet add the guard (Task 6).

- [ ] **Step 1: Confirm baseline**

Run: `uv run pytest documents/tests/test_workflows.py -q`
Expected: PASS (baseline before the rewrite)

- [ ] **Step 2: Update `actions.py` — `execute_email_action` signature**

In `src/documents/workflows/actions.py`, change `execute_email_action` so the
parameter `original_file: Path` is renamed to `source_file: Path`, and replace
every use of `original_file` in its body (`actions.py:158-167`) with
`source_file`. The logic is otherwise unchanged.

- [ ] **Step 3: Update `actions.py` — `execute_webhook_action` signature**

In `execute_webhook_action`, rename the parameter `original_file: Path` to
`source_file: Path` and replace the two uses (`actions.py:245,250`) with
`source_file`.

- [ ] **Step 4: Delete `build_workflow_action_context`**

Delete the entire `build_workflow_action_context` function from
`src/documents/workflows/actions.py` (`actions.py:26-83`) — its two branches now
live in `ConsumptionContext.build_placeholder_context` and
`PersistedContext.build_placeholder_context`.

- [ ] **Step 5: Rewrite `run_workflows` in `handlers.py`**

In `src/documents/signals/handlers.py`, add to the imports:

```python
from documents.workflows.context import WorkflowRunContext
from documents.workflows.context import build_workflow_context
```

and remove the now-unused `build_workflow_action_context` import.

Replace the entire `run_workflows` function (`handlers.py:854-1010`) with:

```python
def run_workflows(
    trigger_type: WorkflowTrigger.WorkflowTriggerType,
    document: Document | ConsumableDocument,
    workflow_to_run: Workflow | None = None,
    logging_group: uuid.UUID | None = None,
    overrides: DocumentMetadataOverrides | None = None,
    original_file: Path | None = None,
) -> tuple[DocumentMetadataOverrides, str] | None:
    """
    Execute workflows matching a document for the given trigger.

    For the consumption flow (`overrides` provided) actions mutate the overrides
    and the function returns `(overrides, messages)`. Otherwise actions mutate
    the persisted Document and the function returns None.

    `original_file`, when given, is the staged path of a freshly-consumed file
    that has not yet been moved into its final storage location.
    """
    if isinstance(document, Document) and document.root_document_id is not None:
        logger.debug(
            "Skipping workflow execution for version document %s",
            document.pk,
        )
        return None

    context: WorkflowRunContext = build_workflow_context(
        trigger_type=trigger_type,
        document=document,
        overrides=overrides,
        staged_file=original_file,
    )

    for workflow in get_workflows_for_trigger(trigger_type, workflow_to_run):
        if not context.refresh(logging_group):
            break

        if not matching.document_matches_workflow(
            context.target,
            workflow,
            trigger_type,
        ):
            continue

        action: WorkflowAction
        has_move_to_trash_action = False
        for action in workflow.actions.order_by("order", "pk"):
            context.log_action(f"Applying {action} from {workflow}", logging_group)

            if action.type == WorkflowAction.WorkflowActionType.ASSIGNMENT:
                context.apply_assignment(action, logging_group)
            elif action.type == WorkflowAction.WorkflowActionType.REMOVAL:
                context.apply_removal(action, logging_group)
            elif action.type == WorkflowAction.WorkflowActionType.EMAIL:
                execute_email_action(
                    action,
                    context.target,
                    context.build_placeholder_context(),
                    logging_group,
                    context.source_file,
                    trigger_type,
                )
            elif action.type == WorkflowAction.WorkflowActionType.WEBHOOK:
                execute_webhook_action(
                    action,
                    context.target,
                    context.build_placeholder_context(),
                    logging_group,
                    context.source_file,
                )
            elif action.type == WorkflowAction.WorkflowActionType.PASSWORD_REMOVAL:
                execute_password_removal_action(
                    action,
                    context.target,
                    logging_group,
                    source_file=context.staged_file,
                )
            elif action.type == WorkflowAction.WorkflowActionType.MOVE_TO_TRASH:
                has_move_to_trash_action = True

        context.persist()
        context.record_run(workflow)

        if has_move_to_trash_action:
            execute_move_to_trash_action(action, context.target, logging_group)

    if isinstance(context, ConsumptionContext):
        return context.overrides, "\n".join(context.messages)
    return None
```

Add the import `from documents.workflows.context import ConsumptionContext` to
`handlers.py` (used for the `isinstance` at the end).

> Note on `staged_file` for password removal: previously the action received
> `original_file if caller_supplied_original_file else None`. `PersistedContext.
staged_file` is exactly the constructor `staged_file` arg, which is
> `original_file` — so DOCUMENT_ADDED gets the staged path and DOCUMENT_UPDATED
> / SCHEDULED get `None`, preserving the old behavior. For the consumption flow,
> `execute_password_removal_action` takes the `ConsumableDocument` branch and
> ignores `source_file` entirely.

- [ ] **Step 6: Update `run_workflows_added`**

`run_workflows_added` (`handlers.py:803-816`) already forwards `original_file`
to `run_workflows`. Leave it as-is — it still receives `original_file` from the
`document_consumption_finished` signal and passes it through; `run_workflows`
now routes it into `PersistedContext` construction.

- [ ] **Step 7: Run the full workflow suite**

Run: `uv run pytest documents/tests/test_workflows.py -q`
Expected: PASS — identical pass count to Step 1. If any test needs editing, STOP:
that is a behavior change, not a refactor outcome — investigate before continuing.

- [ ] **Step 8: Run consumer + matching suites**

Run: `uv run pytest documents/tests/test_consumer.py documents/tests/test_matchables.py -q`
Expected: PASS

- [ ] **Step 9: Lint and commit**

```bash
ruff check --fix src/documents/signals/handlers.py src/documents/workflows/actions.py
ruff format src/documents/signals/handlers.py src/documents/workflows/actions.py
git add src/documents/signals/handlers.py src/documents/workflows/actions.py
git commit -m "Refactor run_workflows around WorkflowRunContext, drop use_overrides"
```

---

## Task 6: Wire the guard into `run_workflows` and the rename receiver

**Files:**

- Modify: `src/documents/signals/handlers.py` (`run_workflows`, `update_filename_and_move_files`, `PersistedContext` use via `finalize_file_location`)
- Test: `src/documents/tests/test_workflows.py`

- [ ] **Step 1: Write the failing test**

Append a new test class to `src/documents/tests/test_workflows.py`. Use the
existing helpers/fixtures already in that file for creating a `Document`, a
`Workflow` with a `DOCUMENT_UPDATED` trigger, and an ASSIGNMENT action that
assigns a correspondent. Model it on the existing `DOCUMENT_UPDATED` tests in
that file (they call `run_workflows(...)` directly). The new test:

```python
class TestWorkflowRenameSequencing(TestCase):
    @pytest.mark.django_db
    def test_rename_suppressed_during_run_then_runs_once(self) -> None:
        """
        update_filename_and_move_files must not run while a workflow is
        executing; the move runs exactly once afterwards.
        """
        from unittest import mock

        from documents.signals import handlers

        # ... set up a Document, a storage path whose template depends on
        # correspondent, and a DOCUMENT_UPDATED workflow with an ASSIGNMENT
        # action assigning that correspondent (reuse this file's helpers) ...

        with mock.patch.object(
            handlers,
            "move_files_for_document",
            wraps=handlers.move_files_for_document,
        ) as move_spy:
            run_workflows(
                trigger_type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
                document=document,
            )

        # The m2m_changed / post_save receiver must NOT have driven the move
        # mid-run; only the single explicit finalize call remains.
        assert move_spy.call_count == 1
```

> The implementer should flesh out the document/workflow setup using the
> patterns already present in `test_workflows.py`. The assertion that matters:
> `move_files_for_document` is called exactly once, via the explicit
> `finalize_file_location()`, not once-per-`save()` from signals.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest documents/tests/test_workflows.py::TestWorkflowRenameSequencing -v`
Expected: FAIL — without the guard, `move_files_for_document` is invoked
multiple times (via `post_save` / `m2m_changed`), so `call_count != 1`.

- [ ] **Step 3: Add the guard check to the receiver**

In `src/documents/signals/handlers.py`, add the early-return to the
`update_filename_and_move_files` receiver. Add the import:

```python
from documents.workflows.context import workflow_run_in_progress
```

and make the receiver:

```python
def update_filename_and_move_files(
    sender,
    instance: Document | CustomFieldInstance,
    **kwargs,
) -> None:
    if workflow_run_in_progress():
        # A workflow run is mutating this document; the rename is deferred to a
        # single explicit call in run_workflows after the run completes.
        return

    if isinstance(instance, CustomFieldInstance):
        if not _filename_template_uses_custom_fields(instance.document):
            return
        instance = instance.document

    move_files_for_document(instance)
```

- [ ] **Step 4: Wrap the run and add the explicit rename in `run_workflows`**

In `run_workflows`, add the import:

```python
from documents.workflows.context import workflow_guard
```

Wrap the `for workflow in ...` loop in `with workflow_guard():`, and call
`context.finalize_file_location()` after the loop (outside the `with` block):

```python
    with workflow_guard():
        for workflow in get_workflows_for_trigger(trigger_type, workflow_to_run):
            ...  # loop body unchanged
            if has_move_to_trash_action:
                execute_move_to_trash_action(action, context.target, logging_group)

    context.finalize_file_location()

    if isinstance(context, ConsumptionContext):
        return context.overrides, "\n".join(context.messages)
    return None
```

`ConsumptionContext.finalize_file_location()` is a no-op; `PersistedContext`'s
runs `move_files_for_document` once against the refreshed, non-deleted document.

- [ ] **Step 5: Run the new test**

Run: `uv run pytest documents/tests/test_workflows.py::TestWorkflowRenameSequencing -v`
Expected: PASS

- [ ] **Step 6: Run the full workflow + file-handling suites**

Run: `uv run pytest documents/tests/test_workflows.py documents/tests/test_file_handling.py -q`
Expected: PASS — no pre-existing test changed.

- [ ] **Step 7: Lint and commit**

```bash
ruff check --fix src/documents/signals/handlers.py src/documents/tests/test_workflows.py
ruff format src/documents/signals/handlers.py src/documents/tests/test_workflows.py
git add src/documents/signals/handlers.py src/documents/tests/test_workflows.py
git commit -m "Defer workflow file rename via ContextVar guard"
```

---

## Task 7: Regression test for the metadata-vs-rename race (#12386)

**Files:**

- Test: `src/documents/tests/test_workflows.py`

- [ ] **Step 1: Write the regression test**

Append to `src/documents/tests/test_workflows.py` a test that reproduces the
original bug: a workflow that assigns **both** tags (firing `m2m_changed`) and a
correspondent, where the storage path template depends on the correspondent.
Before the fix the `m2m_changed`-triggered rename ran with a stale (empty)
correspondent and moved the file to the wrong path.

```python
class TestWorkflowMetadataRenameRace(TestCase):
    @pytest.mark.django_db
    def test_tag_and_correspondent_assignment_lands_file_at_final_path(
        self,
    ) -> None:
        """
        Regression for #12386: assigning tags (m2m_changed) plus a correspondent
        used by the storage-path template must not move the file using stale
        metadata. After the run the DB filename and the on-disk file agree.
        """
        # ... reuse this file's helpers to:
        #   - create a StoragePath whose path template references {correspondent}
        #   - create a Document assigned to that storage path with a real file
        #     on disk at document.source_path
        #   - create a DOCUMENT_UPDATED Workflow with one ASSIGNMENT action that
        #     assigns BOTH a tag and a correspondent
        #   - call run_workflows(DOCUMENT_UPDATED, document=document)
        # Assert:
        document.refresh_from_db()
        assert document.correspondent is not None
        assert Path(document.source_path).is_file()
        # the path reflects the assigned correspondent, not an empty value
        assert document.correspondent.name in str(document.filename)
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest documents/tests/test_workflows.py::TestWorkflowMetadataRenameRace -v`
Expected: PASS (the guard from Task 6 fixes the race; this test locks it in)

- [ ] **Step 3: Lint and commit**

```bash
ruff check --fix src/documents/tests/test_workflows.py
ruff format src/documents/tests/test_workflows.py
git add src/documents/tests/test_workflows.py
git commit -m "Add regression test for workflow metadata vs rename race"
```

---

## Task 8: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite**

Run: `uv run pytest -m "not live" -q`
Expected: PASS. Investigate any failure before claiming completion.

- [ ] **Step 2: Lint the whole change**

Run: `ruff check src/documents/` then `ruff format --check src/documents/`
Expected: clean.

- [ ] **Step 3: Type-check**

Run: `uv run mypy documents/workflows/context.py documents/signals/handlers.py documents/workflows/actions.py`
Expected: no **new** errors beyond `.mypy-baseline.txt`. Per CLAUDE.md, do not
attempt to clear the baseline — only ensure you introduced nothing new.

- [ ] **Step 4: Confirm no stray references**

Run: `git grep -n "build_workflow_action_context\|caller_supplied_original_file\|use_overrides" src/`
Expected: no matches (all three are fully removed).

- [ ] **Step 5: Final commit (if Step 2-4 required fixes)**

```bash
git add -A
git commit -m "Clean up after workflow runner refactor"
```

---

## Self-review notes (already applied)

- **Spec coverage:** §1 Protocol → Tasks 2-3; §2 branch-free `run_workflows` →
  Task 5; §3 `source_file` / staged-path relocation → Tasks 3, 5; §4 guard +
  sequencing → Tasks 4, 6; deferred password-removal hook left as-is (Task 5
  note); testing → Tasks 1-3, 6-8.
- **`update_fields` exclusion kept** (`_WORKFLOW_SAVE_FIELDS` in Task 3) — per
  the design decision that it guards a cross-process hazard the guard does not
  cover. No task removes it.
- **Type consistency:** `WorkflowRunContext` surface (`target`, `source_file`,
  `staged_file`, `refresh`, `build_placeholder_context`, `apply_assignment`,
  `apply_removal`, `log_action`, `persist`, `record_run`,
  `finalize_file_location`) is identical across the Protocol, both
  implementations, and all call sites in the rewritten `run_workflows`.
