# Bulk-Edit Operation Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the bulk-edit operation definition — today smeared across 8 sites in 3 files, keyed 3 different ways — into a single `BulkEditOperation` object per operation, held in an ordered registry. The serializer and both view call sites consume the registry instead of re-encoding the operation list. The wire/API contract is preserved byte-for-byte; per-operation OpenAPI examples are added so the bulk API documents itself.

**Architecture:** A new `documents/bulk_operations.py` defines a `BulkEditOperation` ABC, a frozen `PermissionRequirements` value object, a per-operation DRF parameter serializer (validation + coercion), and an ordered `BULK_EDIT_OPERATIONS` registry whose 16 entries wrap the existing `bulk_edit.py` functions (which are unchanged). `BulkEditSerializer` resolves a method string to an operation and delegates parameter validation; `BulkEditView.post` and `_execute_document_action` read `op.needs_user` / `op.audit_field` / `op.required_permissions(...)` instead of the `METHOD_NAMES_*` sets, `MODIFIED_FIELD_BY_METHOD`, and the three `method in [...]` permission blocks.

**Tech Stack:** Python ≥3.11, Django REST Framework, drf-spectacular, pytest + pytest-mock + factory-boy. Backend tests run on the Linux VM (this is a Windows host); `ruff` runs locally.

**Spec:** `docs/superpowers/specs/2026-06-16-bulk-edit-operation-registry-design.md` (rev. 2 — read the Operation inventory matrix and the Parameter coercion contract before starting; they are the source of truth for every per-op cell).

---

## Conventions for every task

- **Run backend tests on the VM** via the helper (never locally — the lockfile is linux/macOS only):
  ```bash
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "<pytest targets/args>"
  ```
- **Lint locally** with the global ruff binary (not `uv run`):
  ```bash
  ruff check src/documents/bulk_operations.py src/documents/serialisers.py src/documents/views.py
  ruff format src/documents/bulk_operations.py src/documents/serialisers.py src/documents/views.py
  ```
- **New tests are pytest-style** (per CLAUDE.md): grouped in classes, `@pytest.mark.django_db` on the class where DB is needed, factory-boy factories (`UserFactory`, `DocumentFactory`, `TagFactory`, …), the `mocker` fixture, `@pytest.mark.parametrize`, full type annotations on fixtures and tests.
- **`CustomFieldFactory` does not exist yet** in `tests/factories.py` (only `Correspondent`/`DocumentType`/`Tag`/`StoragePath`/`Document`/`User`/`PaperlessTask`). The `modify_custom_fields` `clean_parameters` tests need `CustomField` rows — add a `CustomFieldFactory` there first (per CLAUDE.md's "add a factory when a model lacks one").
- **Do NOT convert the existing `test_api_bulk_edit.py`** (DRF `APITestCase` style) — it is the regression net and stays as-is. It must be green at every commit. Its `mock.patch("documents.serialisers.bulk_edit.<fn>")` / `documents.views.bulk_edit.<fn>` targets keep working **only if** the two invariants below hold — verify them, do not assume them.

### Two load-bearing invariants (the contract-preservation kernel)

1. **Module identity:** `serialisers.py`, `views.py`, and the new `bulk_operations.py` must each import the operations module as `from documents import bulk_edit` (module import, not `from documents.bulk_edit import merge`). All three then reference the _same_ `sys.modules["documents.bulk_edit"]` object, so a `mock.patch("documents.serialisers.bulk_edit.merge")` mutates the attribute every call site sees. **Verify** `serialisers.py` and `views.py` already use `from documents import bulk_edit` before relying on this.
2. **Call-time lookup:** each `BulkEditOperation.execute` must call `bulk_edit.merge(doc_ids, **kw)` (attribute lookup at call time), NOT capture the function at class-definition time (`fn = bulk_edit.merge` as a class attribute). Otherwise the patch — applied after import — won't be seen.

## File structure

- **Create** `src/documents/bulk_operations.py` — `PermissionRequirements`, `BulkEditOperation` ABC, the per-op parameter serializers, the 16 operation classes, and the ordered `BULK_EDIT_OPERATIONS` registry. One cohesive module.
- **Create** `src/documents/tests/test_bulk_operations.py` — pytest-style unit tests: the permission-matrix characterization (Task 1), then `required_permissions` / `clean_parameters` / registry-parity unit tests (Task 2).
- **Modify** `src/documents/serialisers.py` — rewrite `BulkEditSerializer.method` choices, `validate_method`, and `validate()`; delete the `_validate_parameters_*` methods (their logic moves into the per-op serializers).
- **Modify** `src/documents/views.py` — rewrite `_has_document_permissions`; delete `METHOD_NAMES_REQUIRING_USER`/`_TRIGGER_SOURCE` and `MODIFIED_FIELD_BY_METHOD`; route `BulkEditView.post` through the registry; change `_execute_document_action`'s signature from `method` to `op`; and update the **six** moved-endpoint caller views (`RotateDocumentsView`, `MergeDocumentsView`, `DeleteDocumentsView`, `ReprocessDocumentsView`, `EditPdfDocumentsView`, `RemovePasswordDocumentsView`, `views.py:2964-3109`) to pass `op=BULK_EDIT_OPERATIONS["<name>"]` instead of `method=bulk_edit.<fn>`. Add `from drf_spectacular.utils import OpenApiExample` (Task 4 needs it — not currently imported).

---

## Task 1: Permission-matrix characterization test (the safety net)

This test freezes today's permission behavior **before** any refactor. It must PASS against the current code unchanged — if any case is red now, the spec's matrix (or your reading of it) is wrong; stop and reconcile before proceeding. After the cutover (Task 3) it must still pass identically.

**Files:**

- Create: `src/documents/tests/test_bulk_operations.py`

- [ ] **Step 1: Write the behavior-level permission test against the live API**

Drive the real `bulk_edit/` endpoint so the test is independent of internal structure (it survives the refactor without edits). Build users with precise permission sets and owners, and assert the 200-vs-403 outcome per operation and parameter combination. Cover, at minimum, the conditional cases the spec calls out:

- ownership required: `set_permissions`, `delete`, `rotate`, `delete_pages`, `edit_pdf`, `remove_password` (unconditional); `merge`/`split` only when `delete_originals=true`.
- `add_document` required: `split`, `merge` (unconditional); `edit_pdf`/`remove_password` only when `update_document` is falsy.
- `delete_document` required: `delete` (unconditional); `merge`/`split` only when `delete_originals=true`.

```python
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from documents.models import Document
from documents.tests.factories import DocumentFactory
from documents.tests.factories import UserFactory


@pytest.mark.django_db
class TestBulkEditPermissionMatrix:
    @pytest.fixture()
    def owned_docs(self, ...) -> list[Document]: ...

    # parametrize (method, parameters, perms_to_grant, is_owner) -> expected_status
    @pytest.mark.parametrize(("method", "parameters", "grant", "owner", "expected"), [
        ("set_correspondent", {"correspondent": None}, ["change"], False, status.HTTP_200_OK),
        ("delete", {}, ["change"], True, status.HTTP_200_OK),
        ("delete", {}, ["change"], False, status.HTTP_403_FORBIDDEN),  # ownership
        ("delete", {}, ["change", "delete"], False, status.HTTP_403_FORBIDDEN),  # still needs ownership
        ("merge", {"delete_originals": False}, ["change", "add"], False, status.HTTP_200_OK),  # no ownership when not deleting
        ("merge", {"delete_originals": True}, ["change", "add", "delete"], False, status.HTTP_403_FORBIDDEN),  # ownership now required
        ("edit_pdf", {"operations": [{"page": 1}], "update_document": False}, ["change"], True, status.HTTP_403_FORBIDDEN),  # needs add_document
        ("edit_pdf", {"operations": [{"page": 1}], "update_document": True}, ["change"], True, status.HTTP_200_OK),  # update => owner+change only
        ("remove_password", {"password": "x", "update_document": False}, ["change"], True, status.HTTP_403_FORBIDDEN),  # needs add_document
        ("remove_password", {"password": "x", "update_document": True}, ["change"], True, status.HTTP_200_OK),
        # ... fill every row of the spec matrix, both polarities of each conditional ...
    ])
    def test_permission_outcome(self, method, parameters, grant, owner, expected, ...) -> None:
        # mock the actual bulk_edit.<fn> so execution is a no-op; we test ONLY the
        # permission gate's status code, not the operation's effect.
        ...
```

Notes:

- Mock the underlying `bulk_edit.<fn>` (patch `documents.views.bulk_edit.<fn>`) so the operations don't actually run — this test is purely about the permission gate returning 200 vs 403.
- A superuser short-circuits to allowed (`views.py:2833`); include one superuser row to pin that.
- This is verbose by design; the matrix is the security contract. Prefer one parametrized test over hand-written methods.
- **Cover the six moved single-action endpoints too (REQUIRED — C2).** `/api/documents/rotate/`, `/merge/`, `/delete/`, `/reprocess/`, `/edit_pdf/`, `/remove_password/` run the **same** `_has_document_permissions` gate via `_execute_document_action`, and that path is rewritten in Task 3 (C1). Add a parallel parametrized test that POSTs to each (their request bodies are the dedicated serializers' fields — e.g. `{"documents": [...], "degrees": 90}` for rotate — **not** a `method`+`parameters` envelope). The existing `test_api_bulk_edit.py` already covers these endpoints' permission gates (`test_rotate_insufficient_permissions:1320`, `test_merge_and_delete_insufficient_permissions:1381`, `test_edit_pdf_insufficient_permissions:1635`, `test_remove_password_insufficient_permissions:1719`), so this is hardening rather than the sole net — but make the moved-endpoint matrix explicit here so the `_execute_document_action` rewrite is guarded by a parametrized characterization, not scattered one-offs.
- **`edit_pdf` test docs need a `page_count` (M3).** `clean_parameters` for `edit_pdf` bounds-checks `op["page"]` against `Document.page_count` (`serialisers.py:2052-2059`); this test mocks execution but **not** validation, so an `edit_pdf` row with `page: 1` needs its target doc created with `page_count >= 1`, else it fails with a 400 (out-of-bounds) instead of the expected 200/403.

- [ ] **Step 2: Run it against CURRENT code — it must PASS**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_bulk_operations.py -v"`
Expected: PASS. If any row is red, the spec matrix is misread — reconcile against `views.py:2843-2906` before writing any production code.

- [ ] **Step 3: Commit**

```bash
git add src/documents/tests/test_bulk_operations.py
git commit -m "Test: characterize bulk-edit permission matrix before refactor"
```

---

## Task 2: Build `bulk_operations.py` (registry, ABC, ops, serializers) — old path untouched

Build the entire new module with full unit coverage **while the existing dispatch still runs**, so the whole suite stays green throughout. Nothing in `serialisers.py`/`views.py` changes in this task.

**Files:**

- Create: `src/documents/bulk_operations.py`
- Modify (append): `src/documents/tests/test_bulk_operations.py`

- [ ] **Step 1: Write failing unit tests for `PermissionRequirements`, `required_permissions`, and `clean_parameters`**

Append to `test_bulk_operations.py`. White-box this time — assert the value objects directly:

```python
from documents import bulk_operations as ops


class TestRequiredPermissions:
    @pytest.mark.parametrize(("name", "params", "expected"), [
        ("set_correspondent", {}, ops.PermissionRequirements(change=True)),
        ("delete", {}, ops.PermissionRequirements(change=True, ownership=True, delete_document=True)),
        ("merge", {"delete_originals": False}, ops.PermissionRequirements(change=True, add_document=True)),
        ("merge", {"delete_originals": True}, ops.PermissionRequirements(change=True, add_document=True, ownership=True, delete_document=True)),
        ("edit_pdf", {"update_document": False}, ops.PermissionRequirements(change=True, ownership=True, add_document=True)),
        ("edit_pdf", {"update_document": True}, ops.PermissionRequirements(change=True, ownership=True)),
        ("remove_password", {"update_document": False}, ops.PermissionRequirements(change=True, ownership=True, add_document=True)),
        ("remove_password", {"update_document": True}, ops.PermissionRequirements(change=True, ownership=True)),
        # ... every operation, both polarities of each conditional (spec matrix) ...
    ])
    def test_required_permissions(self, name, params, expected) -> None:
        assert ops.BULK_EDIT_OPERATIONS[name].required_permissions(params) == expected


class TestRegistryParity:
    def test_choices_are_16_unique_in_canonical_order(self) -> None:
        # 8 field-ops, then MOVED_DOCUMENT_ACTION_ENDPOINTS key order
        assert list(ops.BULK_EDIT_OPERATIONS) == [
            "set_correspondent", "set_document_type", "set_storage_path",
            "add_tag", "remove_tag", "modify_tags", "modify_custom_fields",
            "set_permissions",
            "delete", "reprocess", "rotate", "merge",
            "edit_pdf", "remove_password", "split", "delete_pages",
        ]
        assert "redo_ocr" not in ops.BULK_EDIT_OPERATIONS

    def test_every_op_executes_via_module_attribute(self, mocker) -> None:
        # guards invariant #2: call-time lookup so patches still bite
        m = mocker.patch("documents.bulk_operations.bulk_edit.merge", return_value="OK")
        ops.BULK_EDIT_OPERATIONS["merge"].execute([1], delete_originals=False)
        m.assert_called_once()


@pytest.mark.django_db
class TestCleanParameters:
    # mirror the existing _validate_parameters_* tests: defaults applied, pages
    # string parse, page-bounds vs page_count, custom-field list-or-dict +
    # documentlink targets, owner existence, source_mode gating. Assert the SAME
    # ValidationError message strings the old validators raised.
    ...
```

- [ ] **Step 2: Run to verify it fails**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_bulk_operations.py::TestRequiredPermissions -v"`
Expected: FAIL with `ModuleNotFoundError: No module named 'documents.bulk_operations'`.

- [ ] **Step 3: Implement `PermissionRequirements` and the `BulkEditOperation` ABC**

```python
from __future__ import annotations

import dataclasses
from abc import ABC
from abc import abstractmethod
from typing import ClassVar

from rest_framework import serializers

from documents import bulk_edit  # module import — invariant #1


@dataclasses.dataclass(frozen=True)
class PermissionRequirements:
    change: bool = True           # documents.change_document + object-level, always
    ownership: bool = False       # user owns (or doc.owner is None for) ALL docs
    add_document: bool = False     # documents.add_document
    delete_document: bool = False  # documents.delete_document


class BulkEditOperation(ABC):
    name: ClassVar[str]
    audit_field: ClassVar[str | None] = None
    supports_all: ClassVar[bool] = True
    max_documents: ClassVar[int | None] = None
    too_many_documents_message: ClassVar[str | None] = None
    needs_user: ClassVar[bool] = False
    needs_trigger_source: ClassVar[bool] = False
    parameter_serializer_class: ClassVar[type[serializers.Serializer] | None] = None
    example_parameters: ClassVar[dict] = {}

    def clean_parameters(self, parameters: dict, *, user, documents: list[int]) -> dict:
        if self.parameter_serializer_class is None:
            return parameters
        serializer = self.parameter_serializer_class(
            data=parameters,
            context={"user": user, "documents": documents},
        )
        serializer.is_valid(raise_exception=True)
        # merge coerced/validated values back over the raw dict so passthrough
        # keys (e.g. metadata_document_id, source_mode) survive.
        return {**parameters, **serializer.validated_data}

    def required_permissions(self, parameters: dict) -> PermissionRequirements:
        return PermissionRequirements()

    @abstractmethod
    def execute(self, doc_ids: list[int], **parameters) -> str: ...
```

- [ ] **Step 4: Implement the 16 operation classes + parameter serializers**

Follow the spec's Operation inventory matrix for every cell. Representative examples — the simple assignment op, and the two conditional ones:

```python
class SetCorrespondentOperation(BulkEditOperation):
    name = "set_correspondent"
    audit_field = "correspondent"
    parameter_serializer_class = SetCorrespondentParametersSerializer  # validates correspondent id|null
    example_parameters = {"correspondent": 1}

    def execute(self, doc_ids, **kw):
        return bulk_edit.set_correspondent(doc_ids, **kw)


class MergeOperation(BulkEditOperation):
    name = "merge"
    supports_all = False
    needs_user = needs_trigger_source = True
    parameter_serializer_class = MergeParametersSerializer
    example_parameters = {"delete_originals": False, "archive_fallback": False}

    def required_permissions(self, parameters):
        delete = parameters.get("delete_originals", False)
        return PermissionRequirements(
            change=True, add_document=True,
            ownership=delete, delete_document=delete,
        )

    def execute(self, doc_ids, **kw):
        return bulk_edit.merge(doc_ids, **kw)


class EditPdfOperation(BulkEditOperation):
    name = "edit_pdf"
    supports_all = False
    max_documents = 1
    too_many_documents_message = "Edit PDF method only supports one document"
    needs_user = needs_trigger_source = True
    parameter_serializer_class = EditPdfParametersSerializer
    example_parameters = {"operations": [{"page": 1, "rotate": 90}], "update_document": False, "include_metadata": True}

    def required_permissions(self, parameters):
        # edit_pdf is ALWAYS ownership-gated (views.py:2722); add_document only
        # when NOT update_document (views.py:2740-2741).
        update = parameters.get("update_document", False)
        return PermissionRequirements(change=True, ownership=True, add_document=not update)

    def execute(self, doc_ids, **kw):
        return bulk_edit.edit_pdf(doc_ids, **kw)
```

Parameter serializers carry the validation+coercion the spec's "Parameter coercion contract to preserve" section enumerates — preserve the exact `ValidationError` message strings. Example for the DB/cross-field case:

```python
class EditPdfParametersSerializer(serializers.Serializer):
    operations = serializers.ListField(child=serializers.DictField())
    update_document = serializers.BooleanField(required=False, default=False)
    include_metadata = serializers.BooleanField(required=False, default=True)
    # source_mode handled here too, only when present

    def validate(self, attrs):
        # reproduce serialisers.py:2045-2059 verbatim, incl. messages:
        #  - "update_document only allowed with a single output document"
        #  - page-bounds: "Page {n} is out of bounds for document with {k} pages."
        #    using self.context["documents"][0] / Document.objects.get(...)
        return attrs
```

`RemovePasswordOperation` keeps an `update_document` param (it exists — `bulk_edit.py:881`); its `required_permissions` mirrors `EditPdfOperation`'s `add_document=not update` (but ownership is unconditional too — see matrix). `DeleteOperation` / `ReprocessOperation` set `parameter_serializer_class = None`. Do **not** register `redo_ocr`.

**Defaulting parity (H3) — match each old validator exactly, no more, no less.** `test_api_bulk_edit.py` asserts `mock.call_args` kwargs, so a serializer that injects a default the old validator didn't will break those asserts. `edit_pdf` _did_ default `update_document=False` / `include_metadata=True` (`serialisers.py:2038-2043`) → keep them. `remove_password` validated **only** `password` (`serialisers.py:2061-2065`) and did **not** default `update_document` / `include_metadata` / `delete_original` → `RemovePasswordParametersSerializer` must declare only `password`. `update_document` then survives as a **raw passthrough key** in `parameters` (so `required_permissions` still reads it via `parameters.get("update_document", False)`), and no extra kwargs reach `bulk_edit.remove_password`. Apply the same "match the old defaulting" rule to every op.

**`set_permissions` transform (H2) — the QuerySet shape is load-bearing.** `SetPermissionsParametersSerializer` must run `validate_set_permissions` (from `SetPermissionsMixin`, which `BulkEditSerializer` already inherits) so that `validated_data["set_permissions"]` carries the **QuerySet-dict** structure `bulk_edit.set_permissions` consumes — not the raw `{view:{users:[ids]}}` dict. A plain `DictField` would leave the raw dict in `validated_data`, and `{**parameters, **validated_data}` would then feed the function the wrong shape. Also default `merge=False` and validate `owner` existence (`serialisers.py:1946-1952`).

Build the **ordered** registry (legacy section in `MOVED_DOCUMENT_ACTION_ENDPOINTS` key order — `edit_pdf, remove_password` before `split, delete_pages`):

```python
BULK_EDIT_OPERATIONS: dict[str, BulkEditOperation] = {
    op.name: op
    for op in (
        SetCorrespondentOperation(), SetDocumentTypeOperation(),
        SetStoragePathOperation(), AddTagOperation(), RemoveTagOperation(),
        ModifyTagsOperation(), ModifyCustomFieldsOperation(), SetPermissionsOperation(),
        DeleteOperation(), ReprocessOperation(), RotateOperation(), MergeOperation(),
        EditPdfOperation(), RemovePasswordOperation(), SplitOperation(), DeletePagesOperation(),
    )
}
```

- [ ] **Step 5: Run unit tests to green**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_bulk_operations.py -v"`
Expected: PASS (permission matrix, required_permissions, registry parity, clean_parameters). The existing `test_api_bulk_edit.py` is untouched and still green (old path runs).

- [ ] **Step 6: Lint & commit**

```bash
ruff check src/documents/bulk_operations.py && ruff format src/documents/bulk_operations.py
git add src/documents/bulk_operations.py src/documents/tests/test_bulk_operations.py
git commit -m "Feature: add bulk-edit operation registry (not yet wired)"
```

---

## Task 3: Cutover — wire the serializer and BOTH view call sites

This is the atomic swap: `validate_method` returning an operation object ripples to both view sites, so serializer + views land in **one commit**. The full `test_api_bulk_edit.py` regression suite plus Task 1's matrix test are the contract; both must be green at the end.

**Files:**

- Modify: `src/documents/serialisers.py`
- Modify: `src/documents/views.py`

- [ ] **Step 1: Confirm invariant #1**

Grep that `serialisers.py` and `views.py` import `from documents import bulk_edit` (not `from documents.bulk_edit import ...`). If they use member imports, the existing patches break — convert to module import as part of this task and note it.

- [ ] **Step 2: Rewrite `BulkEditSerializer`**

- `method = serializers.ChoiceField(choices=list(bulk_operations.BULK_EDIT_OPERATIONS), ...)` — registry alone (16, canonical order), **not** `+ LEGACY_DOCUMENT_ACTION_METHODS`.
- `validate_method` → `return bulk_operations.BULK_EDIT_OPERATIONS[method]` (returns the op; raise `ValidationError("Unsupported method.")` on KeyError to preserve the message).
- `validate()`:
  ```python
  op = attrs["method"]
  if attrs.get("all", False) and not op.supports_all:
      raise serializers.ValidationError("This method does not support all=true.")
  if op.max_documents is not None and len(attrs["documents"]) > op.max_documents:
      raise serializers.ValidationError(op.too_many_documents_message)
  attrs["parameters"] = op.clean_parameters(
      attrs["parameters"], user=self.user, documents=attrs["documents"],
  )
  return attrs
  ```
- **Delete** all `_validate_parameters_*` / `_validate_storage_path` / `validate_parameters_remove_password` methods (their logic now lives in the per-op serializers). Keep `MOVED_DOCUMENT_ACTION_ENDPOINTS` / `LEGACY_DOCUMENT_ACTION_METHODS` (still used by the view's deprecation warning).

- [ ] **Step 3: Rewrite `_has_document_permissions` to consume `PermissionRequirements`**

```python
def _has_document_permissions(self, *, user, documents, op, parameters) -> bool:
    if user.is_superuser:
        return True
    document_objs = Document.objects.select_related("owner").filter(pk__in=documents)
    reqs = op.required_permissions(parameters)
    ok = user.has_perm("documents.change_document") and all(
        has_perms_owner_aware(user, "change_document", doc) for doc in document_objs
    )
    if ok and reqs.ownership:
        ok = all((doc.owner == user or doc.owner is None) for doc in document_objs)
    if ok and reqs.add_document:
        ok = user.has_perm("documents.add_document")
    if ok and reqs.delete_document:
        ok = user.has_perm("documents.delete_document")
    return ok
```

- [ ] **Step 4: Route BOTH call sites through the op — they obtain the op differently**

There are two distinct paths, and `_execute_document_action` does **NOT** read `validated_data["method"]` (its serializers have no `method` field — it receives the operation as an argument). Handle each:

- **Delete** `METHOD_NAMES_REQUIRING_USER`, `METHOD_NAMES_REQUIRING_TRIGGER_SOURCE` (note: it is an alias — `METHOD_NAMES_REQUIRING_TRIGGER_SOURCE = METHOD_NAMES_REQUIRING_USER` at `views.py:2687` — so they are one object), and `MODIFIED_FIELD_BY_METHOD`.

- **`BulkEditView.post`** (`views.py:2852-2947`) — the `/bulk_edit/` path: `op = serializer.validated_data["method"]` (the registry object `validate_method` now returns). Replace `method.__name__ in METHOD_NAMES_REQUIRING_USER` → `op.needs_user`; trigger-source check → `op.needs_trigger_source`; the permission call → `_has_document_permissions(op=op, ...)`; `method(documents, **parameters)` → `op.execute(documents, **parameters)`. Audit block: `modified_field = op.audit_field` (replaces `MODIFIED_FIELD_BY_METHOD.get(method.__name__)`), reason → `f"Bulk edit: {op.name}"`. Snapshot/`log_create` otherwise unchanged.

- **`_execute_document_action`** (`views.py:2764-2807`) — the moved single-action path used by six views: change its signature from `method` to `op: BulkEditOperation`. Inside, replace `method.__name__ in METHOD_NAMES_REQUIRING_USER` → `op.needs_user`; trigger check → `op.needs_trigger_source`; `_has_document_permissions(method=method, ...)` → `_has_document_permissions(op=op, ...)`; `method(documents, **parameters)` → `op.execute(documents, **parameters)`. This path has **no** audit block — leave it that way. `op.clean_parameters` is **not** called here: each moved view's own serializer (`RotateDocumentsSerializer`, `MergeDocumentsSerializer`, …) already validated its parameters; the op supplies only needs_user / needs_trigger_source / required_permissions / execute.

- **The six caller views** (`RotateDocumentsView:2964`, `MergeDocumentsView:2991`, `DeleteDocumentsView:3018`, `ReprocessDocumentsView:3045`, `EditPdfDocumentsView:3072`, `RemovePasswordDocumentsView:3099`): change each `method=bulk_edit.<fn>` argument to `op=BULK_EDIT_OPERATIONS["<name>"]` (e.g. `op=BULK_EDIT_OPERATIONS["rotate"]`).

- [ ] **Step 5: Run the FULL regression + matrix suites**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_api_bulk_edit.py src/documents/tests/test_bulk_operations.py -v"`
Expected: PASS — every existing `test_api_bulk_edit.py` test (patch targets still bite via invariant #1; `__name__`-dependent asserts gone), plus Task 1's matrix unchanged. If a `documents.serialisers.bulk_edit.X` / `documents.views.bulk_edit.X` patch stops biting, invariant #1 or #2 is violated — check the import style and that `execute` does call-time lookup.

- [ ] **Step 6: Run the broader API + audit suites** (signals/audit log touch this path)

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_api_documents.py src/documents/tests/test_api_bulk_download.py -k bulk or audit -v"`
Expected: PASS.

- [ ] **Step 7: Lint & commit**

```bash
ruff check src/documents/serialisers.py src/documents/views.py && ruff format src/documents/serialisers.py src/documents/views.py
git add src/documents/serialisers.py src/documents/views.py
git commit -m "Refactor: route bulk_edit through the operation registry"
```

---

## Task 4: Registry-driven OpenAPI examples

**Files:**

- Modify: `src/documents/views.py`
- Test: `src/documents/tests/test_bulk_operations.py`

- [ ] **Step 1: Write a failing test that every example validates**

```python
class TestBulkEditExamples:
    def test_every_operation_has_a_valid_example(self) -> None:
        from documents.views import _bulk_edit_examples
        examples = _bulk_edit_examples()
        assert {e.summary for e in examples} == set(ops.BULK_EDIT_OPERATIONS)
        for ex in examples:
            op = ops.BULK_EDIT_OPERATIONS[ex.value["method"]]
            if op.parameter_serializer_class is not None:
                s = op.parameter_serializer_class(data=ex.value["parameters"], context={...})
                assert s.is_valid(), s.errors
```

- [ ] **Step 2: Implement the helper and wire `@extend_schema`**

First add the import — `OpenApiExample` is **not** currently in `views.py` (extend the existing `from drf_spectacular.utils import ...` line):

```python
from drf_spectacular.utils import OpenApiExample
```

```python
def _bulk_edit_examples() -> list[OpenApiExample]:
    return [
        OpenApiExample(
            name=op.name, summary=op.name,
            value={"documents": [1, 2], "method": op.name, "parameters": op.example_parameters},
            request_only=True,
        )
        for op in BULK_EDIT_OPERATIONS.values()
    ]
```

Add `examples=_bulk_edit_examples()` to the existing `bulk_edit` `extend_schema(...)` (`views.py:2811-2825`). Leave `operation_id`, `description`, and the `responses` inline serializer unchanged.

- [ ] **Step 3: Run the example test + a schema smoke check**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_bulk_operations.py::TestBulkEditExamples -v"`
Then regenerate the OpenAPI schema on the VM and confirm the diff is **examples-only** — the `method` enum membership/order is byte-identical and the request/response structure is unchanged:

```bash
ssh -o BatchMode=yes -p 2244 trenton@localhost 'bash -lc "cd ~/projects/paperless-ngx && uv run manage.py spectacular --file /tmp/schema.yml"'
```

Expected: schema generates without error; the `bulk_edit` `method` enum lists the 16 methods in canonical order; examples appear.

- [ ] **Step 4: Lint & commit**

```bash
ruff check src/documents/views.py && ruff format src/documents/views.py
git add src/documents/views.py src/documents/tests/test_bulk_operations.py
git commit -m "Feature: document bulk_edit parameters via per-operation OpenAPI examples"
```

---

## Task 5: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Full bulk-edit-related suite**

Run: `bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/documents/tests/test_api_bulk_edit.py src/documents/tests/test_bulk_operations.py src/documents/tests/test_api_bulk_download.py -v"`
Expected: PASS, no failures, no errors.

- [ ] **Step 2: Type-check on the VM (pyrefly, with baseline)**

```bash
tar czf - src pyproject.toml uv.lock .pyrefly-baseline.json | ssh -o BatchMode=yes -p 2244 trenton@localhost 'tar xzf - -C ~/projects/paperless-ngx'
ssh -o BatchMode=yes -p 2244 trenton@localhost 'bash -lc "cd ~/projects/paperless-ngx && uv run pyrefly check"'
```

Expected: no new type errors beyond the baseline.

- [ ] **Step 3: Final lint/format pass**

Run: `ruff check src/documents/bulk_operations.py src/documents/serialisers.py src/documents/views.py src/documents/tests/test_bulk_operations.py && ruff format --check src/documents/bulk_operations.py src/documents/serialisers.py src/documents/views.py`
Expected: clean.

- [ ] **Step 4: Confirm the smear is gone**

Grep to verify no orphaned references remain: `MODIFIED_FIELD_BY_METHOD`, `METHOD_NAMES_REQUIRING_USER`, `_validate_parameters_`, and `method.__name__` in `views.py` should all be gone; `bulk_edit.<fn>` should appear only inside `bulk_operations.py` `execute` methods.

---

## Notes for the implementer

- **The permission matrix is the whole ballgame.** A wrong `required_permissions` cell is a privilege-escalation bug, not a cosmetic one. Task 1's parametrized characterization test (written and green _before_ the refactor) is the guardrail — never weaken a case to make the refactor pass; if it goes red, the production code is wrong.
- **Preserve `ValidationError` message text verbatim** when porting `_validate_parameters_*` into the per-op serializers — `test_api_bulk_edit.py` asserts specific strings (e.g. the three distinct "only one document" messages, the all=true message, "out of bounds", "update_document only allowed with a single output document").
- **Two call sites, obtained differently.** `BulkEditView.post` reads `op` from `validated_data["method"]` and owns the audit logging; `_execute_document_action` receives `op` as an argument from its **six** caller views (which change `method=bulk_edit.<fn>` → `op=BULK_EDIT_OPERATIONS["<name>"]`) and has no audit. Convert both paths and all six caller views; Task 1 must characterize both before cutover.
- **`redo_ocr` stays unregistered** (dead/unreachable today; registering it would newly accept it on the wire).
- **Out of scope:** a discriminated `oneOf` request schema for `parameters` — examples (Task 4) are the agreed approach; the polymorphic schema is a possible later follow-up (the discriminator `method` and payload `parameters` are sibling fields, which `PolymorphicProxySerializer` does not model cleanly).
