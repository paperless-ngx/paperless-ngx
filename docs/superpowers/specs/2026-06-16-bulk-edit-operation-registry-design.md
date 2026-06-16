# Bulk-Edit Operation Registry — Design

**Date:** 2026-06-16
**Branch base:** `dev`
**Status:** Draft (rev. 2 — corrected per critical review)

## Problem

A single bulk-edit operation's definition is smeared across **eight sites in
three files**, keyed **three different ways**, with no single source of truth.
Taking `merge` as the worked example:

| #   | Location                  | What it holds                                             | Keyed by              |
| --- | ------------------------- | --------------------------------------------------------- | --------------------- |
| 1   | `serialisers.py:1758`     | name in the `method` `ChoiceField.choices`                | **string**            |
| 2   | `serialisers.py:1849`     | `validate_method` `elif` → returns `bulk_edit.merge`      | **string → function** |
| 3   | `serialisers.py:2070`     | the `all=true`-unsupported list                           | **function identity** |
| 4   | `serialisers.py:2115`     | `validate()` dispatch → `_validate_parameters_merge`      | **function identity** |
| 5   | `serialisers.py:2008`     | `_validate_parameters_merge` (validate + coerce defaults) | —                     |
| 6   | `views.py:2687`           | `METHOD_NAMES_REQUIRING_USER` / `_TRIGGER_SOURCE`         | **`__name__`**        |
| 7   | `views.py:2727,2738,2754` | three permission blocks (`method in [...]`)               | **function identity** |
| 8   | `views.py:2844`           | `MODIFIED_FIELD_BY_METHOD` audit field                    | **string**            |

Plus the execution function itself in `bulk_edit.py`.

Three structural problems follow:

- **`validate_method` resolves the request string to a _function object_**
  (`serialisers.py:1826-1860`), so everything downstream compares either
  `method == bulk_edit.merge` (identity), `method.__name__` (string), or the raw
  request string. Three keying schemes for one concept. Adding an operation — or
  editing one — means touching all eight sites, and forgetting one fails
  _silently_ (an op that runs but isn't audited, or skips an ownership check)
  rather than loudly.

- **The permission matrix is parameter-conditional and security-critical.** From
  `views.py:2713-2760`: ownership is required for `merge`/`split` _only_ when
  `delete_originals` is set; `add_document` is required for `edit_pdf`/
  `remove_password` _only_ when `update_document` is not set; `delete_document`
  for `merge`/`split` _only_ when `delete_originals`. This logic is correct but
  lives far from the operations it governs, so it is hard to audit and easy to
  break.

- **The API is self-undocumenting.** `parameters` is a bare
  `serializers.DictField` (`serialisers.py:1773`). drf-spectacular renders it as
  a free-form object, so the OpenAPI schema tells a caller nothing about what
  `merge` versus `set_correspondent` actually expect. The repo uses
  `@extend_schema`/`inline_serializer` widely (62 sites) but has **no**
  `PolymorphicProxySerializer`, `OpenApiExample`, or `discriminator` usage to
  describe this polymorphic endpoint.

## Goal

Make each bulk-edit operation a **single object** that owns all eight facts —
name, execution callable, parameter validation/coercion, audit field, the
`all=`/single-document constraints, the user/trigger-source needs, and its
parameter-conditional permission requirements. Operations live in a registry;
the serializer and view consume the registry instead of re-encoding the
operation list. Adding an operation becomes one class plus one registry entry,
not an eight-site edit. As a deliberate, contract-preserving bonus, each
operation also contributes a **per-operation request example** so the bulk API
finally documents itself in the OpenAPI schema.

**The wire contract does not change.** This is a relocation of internal logic,
not a redefinition of the endpoint.

## Scope

In scope:

- New `documents/bulk_operations.py` (registry + `BulkEditOperation` classes +
  `PermissionRequirements`). The execution functions stay in `bulk_edit.py`;
  operation classes wrap them.
- Rewrite `BulkEditSerializer.validate_method` / `validate()` and the
  `_validate_parameters_*` methods to delegate to the operation's parameter
  serializer.
- Rewrite `BulkEditView._has_document_permissions`, the `METHOD_NAMES_*` sets,
  and `MODIFIED_FIELD_BY_METHOD` to read from the registry.
- Add `examples=[...]` to the `bulk_edit` `@extend_schema`, generated from the
  registry (one example per operation).
- Unit tests per operation; keep every existing `test_api_bulk_edit*` test green.

Out of scope:

- Changing any operation's behavior, accepted method strings, parameter names,
  defaults, coercion, or permission outcome. Byte-for-byte wire compatibility.
- The legacy-method deprecation-warning machinery
  (`MOVED_DOCUMENT_ACTION_ENDPOINTS`, the API-v9-drop TODO at `views.py:2855`):
  legacy methods log a warning and process **inline** — there is **no** redirect
  (`views.py:2856-2866`). Preserved as-is.
- A full polymorphic request schema (`oneOf`/discriminated `parameters`). Examples
  (option 1) are in scope; a discriminated schema is a possible future follow-up
  and is **not** built here — the discriminator (`method`) and the variant
  payload (`parameters`) are sibling fields, which `PolymorphicProxySerializer`
  does not model cleanly. YAGNI until examples prove insufficient.
- Converting `bulk_edit.py` into a package, or touching the execution functions'
  internals.
- Any third-party / entry-point registration of operations. The registry is
  in-tree only; an entry point could be layered on later but the PDF/page ops are
  tightly bound to internal helpers, so ecosystem value is low and unproven.

## Decisions

These shape the design and are the reviewable choices:

1. **Operations wrap, not replace, the `bulk_edit.py` functions.** Each
   `BulkEditOperation.execute` calls the existing function. The execution code is
   correct and well-tested; this refactor is about the metadata and dispatch
   around it, exactly as the export-sink refactor moved _plumbing_ without
   touching export _contents_.
2. **Parameter validation moves into a per-operation DRF `Serializer`**, not an
   ad-hoc `clean_*` method. A real serializer (a) validates and coerces in one
   place (replacing the `_validate_parameters_*` methods _and_ their in-place
   mutation of defaults / the `pages`-string parse), (b) accepts `context`
   (`user`, `documents`) for the cross-field/DB checks (page-bounds vs
   `document.page_count`, documentlink targets, owner existence), and (c) is a
   structure drf-spectacular already understands. Operations with no parameters
   (`delete`, `reprocess`) declare `parameter_serializer_class = None`.
3. **Permission requirements are computed by the operation, given the validated
   parameters**, returning a `PermissionRequirements` value object. The
   parameter-conditional kernel (ownership iff `delete_originals`, etc.) lives
   next to the operation it governs. The view's three permission blocks collapse
   to "build requirements, then check each flag generically."
4. **Examples are derived from the registry** (option 1 from the design
   discussion). Each operation declares a canonical `example_parameters` dict; a
   helper builds one `OpenApiExample` per operation for the `bulk_edit`
   `@extend_schema`. Adding an operation therefore auto-adds its example — the
   examples cannot drift out of sync with the registry. This is the only piece
   that _adds_ to the schema; it does not alter the request/response structure.
5. **The registry is the single source of the method enum.** Today's enum is the
   8 hardcoded field-ops (`serialisers.py:1758-1766`) plus
   `LEGACY_DOCUMENT_ACTION_METHODS` — but the legacy methods (`delete, reprocess,
rotate, merge, edit_pdf, remove_password, split, delete_pages`) **are
   themselves operations**, not a disjoint set, so all **16 unique** methods live
   in the registry. `ChoiceField.choices` is therefore
   `list(BULK_EDIT_OPERATIONS)` **alone** — do NOT append
   `LEGACY_DOCUMENT_ACTION_METHODS` (that would duplicate 8 entries and churn the
   enum, the exact thing this decision prevents). The registry must be **ordered**
   to reproduce today's member order — the 8 field-ops first (in
   `serialisers.py:1758-1766` order), then the 8 legacy methods in
   `MOVED_DOCUMENT_ACTION_ENDPOINTS` **key/insertion order** (`delete, reprocess,
rotate, merge, edit_pdf, remove_password, split, delete_pages`;
   `serialisers.py:1745-1754`) — so the generated OpenAPI `enum` is byte-identical.
   NB: that legacy order is `edit_pdf, remove_password` _before_ `split,
delete_pages` — do not reorder them.

## Architecture

### `PermissionRequirements`

```python
@dataclass(frozen=True)
class PermissionRequirements:
    change: bool = True          # documents.change_document + object-level, always
    ownership: bool = False      # user owns (or doc.owner is None for) ALL docs
    add_document: bool = False    # documents.add_document
    delete_document: bool = False # documents.delete_document
```

### `BulkEditOperation`

New module `documents/bulk_operations.py`:

```python
class BulkEditOperation(ABC):
    name: ClassVar[str]
    audit_field: ClassVar[str | None] = None          # → MODIFIED_FIELD_BY_METHOD
    supports_all: ClassVar[bool] = True               # → the all=true guard
    max_documents: ClassVar[int | None] = None        # split/delete_pages/edit_pdf = 1
    too_many_documents_message: ClassVar[str | None] = None  # per-op error text (H3)
    needs_user: ClassVar[bool] = False                # → METHOD_NAMES_REQUIRING_USER
    needs_trigger_source: ClassVar[bool] = False      # → ..._REQUIRING_TRIGGER_SOURCE
    parameter_serializer_class: ClassVar[type[serializers.Serializer] | None] = None
    example_parameters: ClassVar[dict] = {}           # → OpenApiExample payload

    def clean_parameters(self, parameters: dict, *, user, documents) -> dict:
        """Validate + coerce via parameter_serializer_class (context=user,documents).
        Returns the normalized parameters. Raises serializers.ValidationError.
        No-op passthrough when parameter_serializer_class is None."""

    def required_permissions(self, parameters: dict) -> PermissionRequirements:
        """The parameter-conditional permission kernel. Default: change only."""
        return PermissionRequirements()

    @abstractmethod
    def execute(self, doc_ids: list[int], **parameters) -> str: ...
```

The two subtle operations, stated next to their own rules:

```python
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
    needs_user = needs_trigger_source = True
    parameter_serializer_class = EditPdfParametersSerializer
    example_parameters = {
        "operations": [{"page": 1, "rotate": 90}],
        "update_document": False,
        "include_metadata": True,
    }

    def required_permissions(self, parameters):
        update = parameters.get("update_document", False)
        # edit_pdf is ALWAYS ownership-gated (views.py:2722); add_document only
        # when NOT update_document (views.py:2740-2741).
        return PermissionRequirements(
            change=True, ownership=True, add_document=not update,
        )
```

### Registry

```python
BULK_EDIT_OPERATIONS: dict[str, BulkEditOperation] = {
    op.name: op
    for op in (
        SetCorrespondentOperation(), SetDocumentTypeOperation(),
        SetStoragePathOperation(), AddTagOperation(), RemoveTagOperation(),
        ModifyTagsOperation(), ModifyCustomFieldsOperation(),
        SetPermissionsOperation(),
        # legacy section — MUST match MOVED_DOCUMENT_ACTION_ENDPOINTS key order
        # (serialisers.py:1745-1754) so the generated enum is byte-identical:
        DeleteOperation(), ReprocessOperation(), RotateOperation(),
        MergeOperation(), EditPdfOperation(), RemovePasswordOperation(),
        SplitOperation(), DeletePagesOperation(),
    )
}
```

There is **no** `redo_ocr` entry. `validate_method` has a `method == "redo_ocr"`
branch (`serialisers.py:1843`), but `"redo_ocr"` is absent from `choices`
(`serialisers.py:1758-1768`), so the `ChoiceField` rejects it _before_
`validate_method` runs — that branch is unreachable dead code today. Do **not**
add `redo_ocr` to the registry: doing so would make it a valid `choices` entry
and newly accept it on the wire (a contract change). `reprocess` is registered
once, under `reprocess`.

### How each call site collapses

- **`ChoiceField.choices`** → `list(BULK_EDIT_OPERATIONS)` (the 16 unique
  methods, registry ordered to match today). Legacy methods are already registry
  ops, so they are **not** appended separately (see Decision 5).
- **`validate_method`** → `return BULK_EDIT_OPERATIONS[method]` (the validated
  value becomes an _operation object_ instead of a function — internal only,
  `method` is `write_only`).
- **`validate()`** → `op.clean_parameters(parameters, user=…, documents=…)`; the
  `all=true` guard becomes `if attrs.get("all") and not op.supports_all: raise
ValidationError("This method does not support all=true.")` (today's single
  shared message, `serialisers.py:2077`, asserted verbatim by
  `test_api_bulk_edit.py:763`); the per-method "only one document" checks become
  an `op.max_documents` check that raises `op.too_many_documents_message`. That
  text is **per-op** — "Split method only supports one document", "Delete pages
  method only supports one document", "Edit PDF method only supports one document"
  (`serialisers.py:2105,2111,2119`) — and is asserted verbatim (e.g.
  `test_api_bulk_edit.py:1519`), so it **cannot** be collapsed to one generic
  string.
- **`METHOD_NAMES_REQUIRING_USER` / `_TRIGGER_SOURCE`** → `op.needs_user` /
  `op.needs_trigger_source`.
- **The three permission blocks** → one pass:
  ```python
  reqs = op.required_permissions(parameters)
  ok = user.has_perm("documents.change_document") and all(
      has_perms_owner_aware(user, "change_document", d) for d in document_objs
  )
  if ok and reqs.ownership:       ok = user_is_owner_of_all_documents
  if ok and reqs.add_document:    ok = user.has_perm("documents.add_document")
  if ok and reqs.delete_document: ok = user.has_perm("documents.delete_document")
  ```
- **`MODIFIED_FIELD_BY_METHOD`** → `op.audit_field`.

**Two call sites consume this, not one.** `BulkEditView.post`
(`views.py:2852-2947`) is a fully **inlined** path — it is the only path the
`bulk_edit/` endpoint uses. It checks permissions, sets `user`/`trigger_source`,
runs the audit-log block (`views.py:2896-2940`, currently keyed on
`method.__name__` → becomes `op.audit_field`), and calls `method(documents,
**parameters)`. `_execute_document_action` (`views.py:2764-2807`) is a
**separate** path used by the _moved single-action_ endpoints
(`/api/documents/delete/`, `/rotate/`, …); it builds `parameters`, sets
user/trigger, and checks permissions independently and has **no** audit logging.
The refactor must convert **both** to the registry; audit logging stays only in
`post`.

## Operation inventory (the faithful matrix)

Compiled from `bulk_edit.py` signatures, `serialisers.py:2067-2126`, and
`views.py:2679-2760`. `change` is required for every operation and omitted.
`[source_mode]` is the shared optional param accepted by the PDF-touching ops
(validated by `_validate_source_mode` only when present).

| Operation (`name`)             | Parameters                                                                                                    | `supports_all` | `max_documents` | user/trigger | `audit_field`   | ownership              | add_doc                   | delete_doc             |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------- | -------------- | --------------- | ------------ | --------------- | ---------------------- | ------------------------- | ---------------------- |
| `set_correspondent`            | `correspondent: int\|null`                                                                                    | yes            | —               | no           | `correspondent` | —                      | —                         | —                      |
| `set_document_type`            | `document_type: int\|null`                                                                                    | yes            | —               | no           | `document_type` | —                      | —                         | —                      |
| `set_storage_path`             | `storage_path: int\|null`                                                                                     | yes            | —               | no           | `storage_path`  | —                      | —                         | —                      |
| `add_tag`                      | `tag: int`                                                                                                    | yes            | —               | no           | `tags`          | —                      | —                         | —                      |
| `remove_tag`                   | `tag: int`                                                                                                    | yes            | —               | no           | `tags`          | —                      | —                         | —                      |
| `modify_tags`                  | `add_tags: int[]`, `remove_tags: int[]`                                                                       | yes            | —               | no           | `tags`          | —                      | —                         | —                      |
| `modify_custom_fields`         | `add_custom_fields: int[]\|{id:val}`, `remove_custom_fields: int[]`                                           | yes            | —               | no           | `custom_fields` | —                      | —                         | —                      |
| `set_permissions`              | `set_permissions: obj`, `owner: int\|null`, `merge: bool=false`                                               | yes            | —               | no           | `None`          | **yes**                | —                         | —                      |
| `delete`                       | _(none)_                                                                                                      | yes            | —               | no           | `deleted_at`    | **yes**                | —                         | **yes**                |
| `reprocess` (alias `redo_ocr`) | _(none)_                                                                                                      | yes            | —               | no           | `checksum`      | —                      | —                         | —                      |
| `rotate`                       | `degrees: int`, `[source_mode]`                                                                               | yes            | —               | **yes**      | `None`          | **yes**                | —                         | —                      |
| `merge`                        | `delete_originals: bool=false`, `archive_fallback: bool=false`, `metadata_document_id?: int`, `[source_mode]` | **no**         | —               | **yes**      | `None`          | iff `delete_originals` | **yes**                   | iff `delete_originals` |
| `split`                        | `pages: str→int[][]`, `delete_originals: bool=false`, `[source_mode]`                                         | **no**         | **1**           | **yes**      | `None`          | iff `delete_originals` | **yes**                   | iff `delete_originals` |
| `delete_pages`                 | `pages: int[]`, `[source_mode]`                                                                               | **no**         | **1**           | **yes**      | `None`          | **yes**                | —                         | —                      |
| `edit_pdf`                     | `operations: obj[]`, `update_document: bool=false`, `include_metadata: bool=true`, `[source_mode]`            | **no**         | **1**           | **yes**      | `None`          | **yes**                | iff not `update_document` | —                      |
| `remove_password`              | `password: str`, `update_document: bool=false`, `[source_mode]`                                               | **no**         | —               | **yes**      | `None`          | **yes**                | iff not `update_document` | —                      |

Notes that are easy to get wrong and are pinned here:

- `edit_pdf` ownership is **unconditional** — it is in the unconditional
  ownership list (`views.py:2722`); the separate `edit_pdf and update_document`
  clause (`views.py:2730`) is redundant and folds away.
- `remove_password` **does** accept an `update_document` param
  (`bulk_edit.py:881`), and `parameters` is a passthrough `DictField` whose
  validator (`serialisers.py:2061-2065`) neither strips nor defaults it. So its
  `add_document` requirement is `not parameters.get("update_document", False)` —
  identical to `edit_pdf`, **not** an unconditional `True`. Sending
  `update_document: true` legitimately drops the add_document requirement today,
  and that behavior must be preserved. (Earlier drafts claimed the param did not
  exist — that was a permission-correctness bug.)
- `merge` and `remove_password` are **not** single-document (no `max_documents`),
  even though both set `supports_all = False`.

## Parameter coercion contract to preserve

`clean_parameters` must reproduce every in-place coercion the current
`_validate_parameters_*` methods perform, not merely the validation. Full list
(an implementation-plan checklist):

- `merge` / `split`: default `delete_originals=False`
  (`serialisers.py:1998,2013`); `merge` also defaults `archive_fallback=False`
  (`:2018`).
- `edit_pdf`: default `update_document=False`, `include_metadata=True`
  (`:2038,2043`); reject `update_document=True` with multiple output docs
  (`:2045-2050`).
- `set_permissions`: default `merge=False` (`:1951-1952`) and **mutate**
  `parameters["set_permissions"]` in place via `validate_set_permissions`
  (`:1946`, `SetPermissionsMixin`); validate `owner` existence
  (`:1939-1943,1949-1950`). Needs its own `SetPermissionsParametersSerializer`.
- `split`: parse the `pages` string `"1-3,5"` → `[[1,2,3],[5]]` (`:1974-1990`).
- `source_mode`: validated and applied **only when present** in `parameters`
  (`:2084-2085` gate → `validate_source_mode`, `:1964-1969`), independent of
  method — so each PDF-touching op's serializer opts into it conditionally.
- `modify_custom_fields`: accept **list OR `{id: value}` dict**, and for
  DOCUMENTLINK fields validate targets via `validate_documentlink_targets`
  (`:1787-1824`).
- **Param-name spelling differs by op** and must match exactly: `merge`/`split`
  use `delete_originals` (plural); `edit_pdf`/`remove_password` use
  `delete_original` (singular) (`bulk_edit.py:509,619,751,882`).

## OpenAPI examples (the "make it useful" piece)

A single helper builds the examples from the registry:

```python
def _bulk_edit_examples() -> list[OpenApiExample]:
    return [
        OpenApiExample(
            name=op.name,
            summary=op.name,
            value={"documents": [1, 2], "method": op.name,
                   "parameters": op.example_parameters},
            request_only=True,
        )
        for op in BULK_EDIT_OPERATIONS.values()
    ]
```

wired into the existing decorator (the response schema at `views.py:2818-2825`
is untouched):

```python
@extend_schema_view(
    post=extend_schema(
        operation_id="bulk_edit",
        description="Perform a bulk edit operation on a list of documents",
        examples=_bulk_edit_examples(),
        responses={200: inline_serializer(name="BulkEditDocumentsResult",
                                          fields={"result": serializers.CharField()})},
    ),
)
```

Result: the Swagger/Redoc page shows a concrete, valid request body for every
operation (`merge`, `edit_pdf`, …), generated from the same objects that
validate the request — they cannot drift apart. The request _structure_
(`{documents, method, parameters, …}`) and the `method` `enum` are unchanged;
examples are purely additive.

## Data flow

```
POST /api/documents/bulk_edit/  {documents|all|filters, method, parameters, from_webui}
  ├─ legacy method? → log deprecation warning, then process INLINE  (no redirect; views.py:2856-2866)
  ├─ BulkEditSerializer.validate_method(method) → op = BULK_EDIT_OPERATIONS[method]
  ├─ validate():
  │    ├─ all=true and not op.supports_all                  → ValidationError (shared message)
  │    ├─ op.max_documents and len(documents) > it          → ValidationError (op.too_many_documents_message)
  │    └─ parameters = op.clean_parameters(parameters, user=…, documents=…)
  └─ BulkEditView.post  (inlined; the only path bulk_edit/ uses):
       ├─ if op.needs_user:           parameters["user"] = user
       ├─ if op.needs_trigger_source: parameters["trigger_source"] = WEB_UI|API_UPLOAD
       ├─ reqs = op.required_permissions(parameters); check change/ownership/add/delete
       │     → 403 HttpResponseForbidden on failure                       (unchanged)
       ├─ if op.audit_field and AUDIT_LOG_ENABLED: snapshot old values    (views.py:2896-2910)
       ├─ result = op.execute(documents, **parameters)                    (call-time bulk_edit.<fn> lookup)
       └─ if op.audit_field and AUDIT_LOG_ENABLED: LogEntry per doc → Response({"result": …})
note: _execute_document_action (views.py:2764-2807) is the SEPARATE moved-single-action path
      (/api/documents/delete/, /rotate/, …); it converts to the registry too, but has NO audit log.
      audit "reason" string uses op.name (== bulk_edit.<fn>.__name__ today, so unchanged at runtime).
```

## Backwards compatibility

- **Wire contract:** request/response shapes, accepted `method` strings,
  parameter names, defaults, coercion, and every permission outcome are
  byte-for-byte preserved. `method` becoming an operation object is internal
  (`write_only`).
- **`bulk_edit.<fn>` patching keeps working — by module identity, not luck.**
  Existing tests patch `documents.serialisers.bulk_edit.<fn>` and
  `documents.views.bulk_edit.<fn>` (e.g. `test_api_bulk_edit.py:203,485,1100,1271`).
  All of `documents.serialisers.bulk_edit`, `documents.views.bulk_edit`, and the
  new `documents.bulk_operations.bulk_edit` are the **same module object** in
  `sys.modules`; patching an attribute via any path mutates the one shared module.
  So as long as each `op.execute` does a **call-time** lookup
  (`return bulk_edit.merge(doc_ids, **kw)`, not a function captured at
  class-definition time), the existing patches still intercept and those tests
  stay untouched.
- **The `method.__name__` dependency disappears.** `setup_mock`
  (`test_api_bulk_edit.py:61-63`) sets `m.__name__` because dispatch reads
  `method.__name__` (`views.py:2783,2879,2896,2938`). The refactor replaces every
  such read with `op.name` / `op.needs_user` / `op.audit_field`, so the mock's
  `__name__` no longer affects dispatch. The audit "reason" becomes
  `f"Bulk edit: {op.name}"`; since `bulk_edit.merge.__name__ == "merge" ==
op.name`, real-run audit text is unchanged. No test asserts
  `validated_data["method"]` identity (verified), so `validate_method` returning
  an operation object is safe.
- **Legacy methods:** `MOVED_DOCUMENT_ACTION_ENDPOINTS` /
  `LEGACY_DOCUMENT_ACTION_METHODS` and the v9-drop TODO are unchanged. They drive
  only the inline deprecation warning (`views.py:2856-2866`), **not** the
  `choices` — which come wholly from the registry, since the legacy methods _are_
  registry ops (see C1/Decision 5).
- **OpenAPI:** the `method` `enum` and request/response structure are unchanged
  (Decision 5); `examples` are additive. Regenerated schema diff should be
  _examples only_.

## Testing

New `documents/tests/test_bulk_operations.py` (pytest classes, factory-boy
factories, the `mocker` fixture, `parametrize`, full type annotations; run on the
Linux VM):

- **Permission matrix, parametrized over every operation** — the highest-value
  test. For each op and each relevant parameter combination
  (`delete_originals` on/off, `update_document` on/off), assert
  `op.required_permissions(params)` equals the expected
  `PermissionRequirements`. This freezes the security kernel against drift.
- **Registry/serializer parity** — `ChoiceField.choices` equals the **16 unique**
  method strings in today's exact order (8 field-ops, then the 8
  `MOVED_DOCUMENT_ACTION_ENDPOINTS` keys); **no duplicates**; `redo_ocr` absent;
  every method resolves to an operation. (Guards against the C1 duplication bug.)
- **Parameter validation/coercion** per op — defaults applied (`merge` →
  `delete_originals=False`, `archive_fallback=False`; `split`/`edit_pdf` defaults),
  the `pages` string→list parse, page-bounds-vs-`page_count`, documentlink target
  and owner-existence checks — mirroring the current `_validate_parameters_*` tests.
- **`supports_all` / `max_documents`** — `all=true` rejected for the five
  no-all ops; `>1` document rejected for `split`/`delete_pages`/`edit_pdf`.
- **Examples** — `_bulk_edit_examples()` yields one entry per distinct operation,
  each `value["parameters"]` validates clean through that op's
  `parameter_serializer_class` (guarantees documented examples are valid).

Existing `test_api_bulk_edit.py` / `test_api_bulk_download.py` stay green
unchanged — external behavior (accepted methods, validation errors, permission
403s, audit fields, results) is preserved.

## Risks

- **Permission-matrix mistranslation is a privilege-escalation bug, not a
  cosmetic one.** This is the whole ballgame. Mitigation: move the logic verbatim
  into per-op `required_permissions`, and the parametrized permission test above
  is written _first_ against the current behavior, then held invariant across the
  refactor.
- **The `method`-as-function-object contract** is relied on by existing tests
  (identity compares, `bulk_edit.<fn>` patching). Mitigation: keep `execute`
  delegating to the module-level function so patches still bite; adjust only the
  identity asserts. Audit `test_api_bulk_edit.py` before coding.
- **Serializer-based validation subtly changing error messages/shapes.** The
  current validators raise specific `ValidationError` strings that tests assert
  on. Mitigation: preserve message text when porting each `_validate_parameters_*`
  into its serializer; diff the test expectations.
- **Enum churn in the generated schema.** Mitigation: Decision 5 fixes member set
  and order; the schema-diff check in CI should show examples-only changes.
