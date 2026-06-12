# LanceDB Schema Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a schema versioning and migration system to the LanceDB vector store so that structural column changes can be applied in-place without re-embedding documents, avoiding token costs for users on paid embedding APIs.

**Architecture:** A `schema_version.json` file is written alongside the LanceDB data directory and tracks the current applied version. A `Migration` dataclass registry in `vector_store.py` holds ordered, typed migration steps; each migration is classified as `requires_reembed=True/False`. At index update time, structural-only migrations are applied in-place via LanceDB's `add_columns`/`alter_columns`/`drop_columns` APIs; if any pending migration requires re-embedding, the existing model-mismatch rebuild path is reused.

**Tech Stack:** Python 3.11, lancedb 0.33, pyarrow, pytest, pytest-mock, factory-boy

---

## File Map

| File                                          | Change                                                                                                                                |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `src/paperless_ai/vector_store.py`            | Add `CURRENT_SCHEMA_VERSION`, `Migration` dataclass, version file helpers, migration methods; modify `_ensure_table` and `drop_table` |
| `src/paperless_ai/indexing.py`                | Call migration inside `update_llm_index`'s `write_store` block                                                                        |
| `src/paperless_ai/tests/test_vector_store.py` | New `TestSchemaVersioning` and `TestMigrations` test classes                                                                          |
| `src/paperless_ai/tests/test_ai_indexing.py`  | Two new integration tests for migration path                                                                                          |

---

## Task 1: Schema version file helpers

**Files:**

- Modify: `src/paperless_ai/vector_store.py`
- Test: `src/paperless_ai/tests/test_vector_store.py`

- [ ] **Step 1: Write the failing tests**

Add a new class at the bottom of `test_vector_store.py`:

```python
class TestSchemaVersioning:
    @pytest.fixture
    def uri(self, tmp_path: Path) -> str:
        return str(tmp_path / "idx")

    def test_version_file_written_on_table_creation(self, uri: str) -> None:
        from paperless_ai.vector_store import CURRENT_SCHEMA_VERSION

        store = PaperlessLanceVectorStore(uri=uri)
        store.add([_node("1-0", "1", "text", 0.1)])

        version_file = Path(uri) / "schema_version.json"
        assert version_file.exists()
        assert json.loads(version_file.read_text())["version"] == CURRENT_SCHEMA_VERSION

    def test_stored_schema_version_returns_current_when_file_missing(
        self, uri: str
    ) -> None:
        from paperless_ai.vector_store import CURRENT_SCHEMA_VERSION

        store = PaperlessLanceVectorStore(uri=uri)
        store.add([_node("1-0", "1", "text", 0.1)])
        (Path(uri) / "schema_version.json").unlink()

        reopened = PaperlessLanceVectorStore(uri=uri)
        assert reopened.stored_schema_version() == CURRENT_SCHEMA_VERSION

    def test_stored_schema_version_persists_after_reopen(self, uri: str) -> None:
        from paperless_ai.vector_store import CURRENT_SCHEMA_VERSION

        PaperlessLanceVectorStore(uri=uri).add([_node("1-0", "1", "text", 0.1)])

        reopened = PaperlessLanceVectorStore(uri=uri)
        assert reopened.stored_schema_version() == CURRENT_SCHEMA_VERSION

    def test_drop_table_removes_version_file(self, uri: str) -> None:
        store = PaperlessLanceVectorStore(uri=uri)
        store.add([_node("1-0", "1", "text", 0.1)])
        assert (Path(uri) / "schema_version.json").exists()

        store.drop_table()
        assert not (Path(uri) / "schema_version.json").exists()

    def test_version_file_written_on_upsert_creation(self, uri: str) -> None:
        from paperless_ai.vector_store import CURRENT_SCHEMA_VERSION

        store = PaperlessLanceVectorStore(uri=uri)
        store.upsert_document("1", [_node("1-0", "1", "text", 0.1)])

        version_file = Path(uri) / "schema_version.json"
        assert json.loads(version_file.read_text())["version"] == CURRENT_SCHEMA_VERSION
```

Add `import json` and `import pytest_mock` to the top of `test_vector_store.py`.

- [ ] **Step 2: Run tests to verify they fail**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_vector_store.py::TestSchemaVersioning -v"
```

Expected: all 5 tests fail with `ImportError` or `AttributeError` — `CURRENT_SCHEMA_VERSION` and `stored_schema_version` don't exist yet.

- [ ] **Step 3: Implement the schema version helpers in `vector_store.py`**

After the existing imports and before the `DEFAULT_TABLE_NAME` constant, add:

```python
import json
from pathlib import Path
```

After `DEFAULT_TABLE_NAME = "documents"`, add:

```python
CURRENT_SCHEMA_VERSION: int = 1
```

After the `ANN_PQ_SUB_VECTORS` constant, add nothing yet — version methods go on the class.

Inside `PaperlessLanceVectorStore`, add these methods after `stored_model_name`:

```python
@property
def _schema_version_path(self) -> Path:
    return Path(self._uri) / "schema_version.json"

def stored_schema_version(self) -> int:
    """Return the schema version recorded on disk, or CURRENT_SCHEMA_VERSION if missing.

    Missing means either the table predates versioning or was just created and the
    write hasn't happened yet — treat conservatively as already current.
    """
    try:
        return int(json.loads(self._schema_version_path.read_text())["version"])
    except (FileNotFoundError, KeyError, ValueError):
        return CURRENT_SCHEMA_VERSION

def _write_schema_version(self, version: int) -> None:
    self._schema_version_path.parent.mkdir(parents=True, exist_ok=True)
    self._schema_version_path.write_text(json.dumps({"version": version}))
```

Modify `_ensure_table` to write the version after creating the table. Replace the current method body:

```python
def _ensure_table(self, rows: list[dict[str, Any]], dim: int) -> bool:
    if self._table is not None:
        return False
    self._table = self._conn.create_table(
        self._table_name,
        rows,
        schema=self._schema(dim, self._embed_model_name),
    )
    self._write_schema_version(CURRENT_SCHEMA_VERSION)
    return True
```

Modify `drop_table` to also remove the version file:

```python
def drop_table(self) -> None:
    if self.table_exists():
        self._conn.drop_table(self._table_name)
    self._table = None
    self._schema_version_path.unlink(missing_ok=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_vector_store.py::TestSchemaVersioning -v"
```

Expected: all 5 tests pass.

- [ ] **Step 5: Verify no regressions**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_vector_store.py -v"
```

Expected: all existing tests still pass.

- [ ] **Step 6: Lint**

```bash
ruff check src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
ruff format src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
git commit -m "feat(ai): add schema version file tracking to LanceDB vector store"
```

---

## Task 2: Migration dataclass and pending migration detection

**Files:**

- Modify: `src/paperless_ai/vector_store.py`
- Test: `src/paperless_ai/tests/test_vector_store.py`

- [ ] **Step 1: Write the failing tests**

Add a new class to `test_vector_store.py`:

```python
class TestMigrationRegistry:
    @pytest.fixture
    def uri(self, tmp_path: Path) -> str:
        return str(tmp_path / "idx")

    def _store_at_version(self, uri: str, version: int) -> PaperlessLanceVectorStore:
        """Create a store with a table and then fake its on-disk version."""
        store = PaperlessLanceVectorStore(uri=uri)
        store.add([_node("1-0", "1", "text", 0.1)])
        store._write_schema_version(version)
        return PaperlessLanceVectorStore(uri=uri)  # reopen to pick up written version

    def test_pending_migrations_empty_at_current_version(self, uri: str) -> None:
        from paperless_ai.vector_store import CURRENT_SCHEMA_VERSION, Migration

        store = self._store_at_version(uri, CURRENT_SCHEMA_VERSION)
        assert store.pending_migrations() == []

    def test_pending_migrations_returns_migrations_above_stored_version(
        self, uri: str, mocker: pytest_mock.MockerFixture
    ) -> None:
        from paperless_ai.vector_store import Migration

        m2 = Migration(version=2, description="add col", requires_reembed=False, apply=lambda t: None)
        m3 = Migration(version=3, description="reindex", requires_reembed=True, apply=lambda t: None)
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2, m3])

        store = self._store_at_version(uri, 1)
        pending = store.pending_migrations()
        assert pending == [m2, m3]

    def test_pending_migrations_excludes_already_applied(
        self, uri: str, mocker: pytest_mock.MockerFixture
    ) -> None:
        from paperless_ai.vector_store import Migration

        m2 = Migration(version=2, description="add col", requires_reembed=False, apply=lambda t: None)
        m3 = Migration(version=3, description="reindex", requires_reembed=True, apply=lambda t: None)
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2, m3])

        store = self._store_at_version(uri, 2)
        pending = store.pending_migrations()
        assert pending == [m3]

    def test_pending_migrations_empty_when_no_table(self, uri: str) -> None:
        store = PaperlessLanceVectorStore(uri=uri)
        assert store.pending_migrations() == []

    def test_requires_reembed_migration_false_when_none_pending(self, uri: str) -> None:
        store = self._store_at_version(uri, 1)
        assert store.requires_reembed_migration() is False

    def test_requires_reembed_migration_false_when_only_structural_pending(
        self, uri: str, mocker: pytest_mock.MockerFixture
    ) -> None:
        from paperless_ai.vector_store import Migration

        m2 = Migration(version=2, description="add col", requires_reembed=False, apply=lambda t: None)
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2])

        store = self._store_at_version(uri, 1)
        assert store.requires_reembed_migration() is False

    def test_requires_reembed_migration_true_when_reembed_migration_pending(
        self, uri: str, mocker: pytest_mock.MockerFixture
    ) -> None:
        from paperless_ai.vector_store import Migration

        m2 = Migration(version=2, description="reindex", requires_reembed=True, apply=lambda t: None)
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2])

        store = self._store_at_version(uri, 1)
        assert store.requires_reembed_migration() is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_vector_store.py::TestMigrationRegistry -v"
```

Expected: all 7 tests fail — `Migration`, `MIGRATIONS`, `pending_migrations`, `requires_reembed_migration` don't exist yet.

- [ ] **Step 3: Add `Migration` dataclass and registry to `vector_store.py`**

Add near the top of the file, after the existing imports:

```python
from dataclasses import dataclass, field
from typing import Callable
```

After the `CURRENT_SCHEMA_VERSION` constant, add:

```python
@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    requires_reembed: bool
    apply: Callable[[Any], None] = field(compare=False, hash=False)
```

(`compare=False, hash=False` excludes `apply` from `__eq__` and `__hash__` — equality is driven by `version` alone, which is the natural identity key. This avoids lambda identity issues in tests and makes the API safe for callers that construct `Migration` instances inline.)

# Ordered list of schema migrations. Each entry upgrades the table to `version`.

# Structural migrations (requires_reembed=False) are applied in-place via LanceDB's

# add_columns/alter_columns/drop_columns APIs — no re-embedding needed.

# Migrations with requires_reembed=True cause a full rebuild on next index update,

# exactly like a model-name change does today.

#

# To add a migration:

# 1. Increment CURRENT_SCHEMA_VERSION.

# 2. Append a Migration entry here with the new version number.

# 3. For structural changes, call table.add_columns/alter_columns/drop_columns in apply().

# 4. For embedding-invalidating changes, set requires_reembed=True; apply() can be a no-op.

MIGRATIONS: list[Migration] = []

````

Inside `PaperlessLanceVectorStore`, add after `requires_reembed_migration` (which we'll add next):

```python
def pending_migrations(self) -> list[Migration]:
    """Return migrations not yet applied to this table, in version order."""
    if self._table is None:
        return []
    current = self.stored_schema_version()
    return [m for m in MIGRATIONS if m.version > current]

def requires_reembed_migration(self) -> bool:
    """True when any pending migration requires a full re-embedding."""
    return any(m.requires_reembed for m in self.pending_migrations())
````

- [ ] **Step 4: Run tests to verify they pass**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_vector_store.py::TestMigrationRegistry -v"
```

Expected: all 7 tests pass.

- [ ] **Step 5: Lint**

```bash
ruff check src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
ruff format src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
```

- [ ] **Step 6: Commit**

```bash
git add src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
git commit -m "feat(ai): add Migration registry and pending migration detection"
```

---

## Task 3: Apply structural migrations in-place

**Files:**

- Modify: `src/paperless_ai/vector_store.py`
- Test: `src/paperless_ai/tests/test_vector_store.py`

- [ ] **Step 1: Write the failing tests**

Add a new class to `test_vector_store.py`:

```python
class TestApplyStructuralMigrations:
    @pytest.fixture
    def uri(self, tmp_path: Path) -> str:
        return str(tmp_path / "idx")

    def _store_at_version(self, uri: str, version: int) -> PaperlessLanceVectorStore:
        store = PaperlessLanceVectorStore(uri=uri)
        store.add([_node("1-0", "1", "text", 0.1)])
        store._write_schema_version(version)
        return PaperlessLanceVectorStore(uri=uri)

    def test_apply_structural_adds_column_via_lancedb(
        self, uri: str, mocker: pytest_mock.MockerFixture
    ) -> None:
        from paperless_ai.vector_store import Migration

        def _add_extra(table: Any) -> None:
            table.add_columns({"extra": "CAST(NULL AS VARCHAR)"})

        m2 = Migration(version=2, description="add extra col", requires_reembed=False, apply=_add_extra)
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2])

        store = self._store_at_version(uri, 1)
        applied = store.apply_structural_migrations()

        assert len(applied) == 1
        assert applied[0] == m2
        # Column actually present in the table schema.
        reopened = PaperlessLanceVectorStore(uri=uri)
        field_names = [f.name for f in reopened._table.schema]
        assert "extra" in field_names

    def test_apply_structural_updates_version_file(
        self, uri: str, mocker: pytest_mock.MockerFixture
    ) -> None:
        from paperless_ai.vector_store import Migration

        m2 = Migration(version=2, description="add col", requires_reembed=False, apply=lambda t: t.add_columns({"c": "CAST(NULL AS VARCHAR)"}))
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2])

        store = self._store_at_version(uri, 1)
        store.apply_structural_migrations()

        assert store.stored_schema_version() == 2

    def test_apply_structural_skips_reembed_migrations(
        self, uri: str, mocker: pytest_mock.MockerFixture
    ) -> None:
        from paperless_ai.vector_store import Migration

        applied_versions: list[int] = []
        m2 = Migration(version=2, description="structural", requires_reembed=False, apply=lambda t: applied_versions.append(2) or t.add_columns({"c": "CAST(NULL AS VARCHAR)"}))
        m3 = Migration(version=3, description="reembed", requires_reembed=True, apply=lambda t: applied_versions.append(3))
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2, m3])

        store = self._store_at_version(uri, 1)
        applied = store.apply_structural_migrations()

        assert [m.version for m in applied] == [2]
        assert 3 not in applied_versions
        # Version advances only to the last structural migration applied.
        assert store.stored_schema_version() == 2

    def test_apply_structural_noop_at_current_version(self, uri: str) -> None:
        store = self._store_at_version(uri, 1)
        applied = store.apply_structural_migrations()
        assert applied == []

    def test_apply_structural_noop_when_no_table(self, uri: str) -> None:
        store = PaperlessLanceVectorStore(uri=uri)
        applied = store.apply_structural_migrations()
        assert applied == []

    def test_apply_structural_refreshes_table_reference(
        self, uri: str, mocker: pytest_mock.MockerFixture
    ) -> None:
        """After add_columns the in-memory table object must reflect the new schema."""
        from paperless_ai.vector_store import Migration

        m2 = Migration(version=2, description="add col", requires_reembed=False, apply=lambda t: t.add_columns({"extra": "CAST(NULL AS VARCHAR)"}))
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2])

        store = self._store_at_version(uri, 1)
        store.apply_structural_migrations()

        # The store's own _table reference (not a re-open) must see the new column.
        field_names = [f.name for f in store._table.schema]
        assert "extra" in field_names
```

Add `from typing import Any` to the test file imports if not already present.

- [ ] **Step 2: Run tests to verify they fail**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_vector_store.py::TestApplyStructuralMigrations -v"
```

Expected: all 6 tests fail — `apply_structural_migrations` doesn't exist yet.

- [ ] **Step 3: Implement `apply_structural_migrations` in `vector_store.py`**

Add after `requires_reembed_migration` on the class:

```python
def apply_structural_migrations(self) -> list[Migration]:
    """Apply all pending structural (non-reembed) migrations in version order.

    Each applied migration's ``apply`` callable receives the live LanceDB table
    object and should call ``add_columns``, ``alter_columns``, or ``drop_columns``
    as needed.  After all structural migrations run, the version file is updated
    to the highest version applied and the in-memory table reference is refreshed.

    Migrations with ``requires_reembed=True`` are skipped — the caller is
    responsible for detecting them via ``requires_reembed_migration()`` and
    triggering a full rebuild.
    """
    if self._table is None:
        return []
    structural = [m for m in self.pending_migrations() if not m.requires_reembed]
    if not structural:
        return []
    for migration in structural:
        logger.info("Applying schema migration v%d: %s", migration.version, migration.description)
        migration.apply(self._table)
    # Refresh the in-memory table so subsequent operations see the new schema.
    self._table = self._conn.open_table(self._table_name)
    self._write_schema_version(structural[-1].version)
    return structural
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_vector_store.py::TestApplyStructuralMigrations -v"
```

Expected: all 6 tests pass.

- [ ] **Step 5: Full test_vector_store regression check**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_vector_store.py -v"
```

Expected: all tests pass.

- [ ] **Step 6: Lint**

```bash
ruff check src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
ruff format src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
```

- [ ] **Step 7: Commit**

```bash
git add src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py
git commit -m "feat(ai): implement apply_structural_migrations for in-place schema changes"
```

---

## Task 4: Wire migrations into `update_llm_index`

**Files:**

- Modify: `src/paperless_ai/indexing.py`
- Test: `src/paperless_ai/tests/test_ai_indexing.py`

- [ ] **Step 1: Write the failing tests**

Add these two tests to `test_ai_indexing.py`, after the existing `test_update_llm_index_rebuilds_on_model_name_change` test:

```python
@pytest.mark.django_db
def test_update_llm_index_applies_structural_migration_without_rebuild(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: FakeEmbedding,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """Structural migrations are applied in-place; no full rebuild (drop) occurs."""
    from paperless_ai.vector_store import Migration, PaperlessLanceVectorStore

    column_added: list[bool] = []

    def _add_extra(table) -> None:
        table.add_columns({"extra": "CAST(NULL AS VARCHAR)"})
        column_added.append(True)

    # Build the initial index at version 1 (the real CURRENT_SCHEMA_VERSION; no patches needed).
    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([real_document])
        mock_all.return_value = mock_queryset
        indexing.update_llm_index(rebuild=True)

    # Simulate a new v2 structural migration being introduced after the initial index was built.
    m2 = Migration(version=2, description="add extra col", requires_reembed=False, apply=_add_extra)
    mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2])
    mocker.patch("paperless_ai.vector_store.CURRENT_SCHEMA_VERSION", 2)
    drop_spy = mocker.spy(PaperlessLanceVectorStore, "drop_table")

    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([real_document])
        mock_all.return_value = mock_queryset
        indexing.update_llm_index(rebuild=False)

    assert column_added, "Structural migration apply() was not called"
    drop_spy.assert_not_called()


@pytest.mark.django_db
def test_update_llm_index_forces_rebuild_on_reembed_migration(
    temp_llm_index_dir: Path,
    real_document: Document,
    mock_embed_model: FakeEmbedding,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """A pending reembed migration causes a full drop+rebuild on next update."""
    from paperless_ai.vector_store import Migration, PaperlessLanceVectorStore

    # Build the initial index at version 1 (the real CURRENT_SCHEMA_VERSION; no patches needed).
    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([real_document])
        mock_all.return_value = mock_queryset
        indexing.update_llm_index(rebuild=True)

    # Simulate a reembed migration at v2 being introduced after the initial index was built.
    m2 = Migration(version=2, description="requires reembed", requires_reembed=True, apply=lambda t: None)
    mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2])
    mocker.patch("paperless_ai.vector_store.CURRENT_SCHEMA_VERSION", 2)
    drop_spy = mocker.spy(PaperlessLanceVectorStore, "drop_table")

    with patch("documents.models.Document.objects.all") as mock_all:
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__.return_value = iter([real_document])
        mock_all.return_value = mock_queryset
        indexing.update_llm_index(rebuild=False)

    drop_spy.assert_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_ai_indexing.py::test_update_llm_index_applies_structural_migration_without_rebuild src/paperless_ai/tests/test_ai_indexing.py::test_update_llm_index_forces_rebuild_on_reembed_migration -v"
```

Expected: both tests fail because `update_llm_index` doesn't call migration methods yet.

- [ ] **Step 3: Add migration check inside `update_llm_index` in `indexing.py`**

Inside the `with write_store(embed_model_name=model_name) as store:` block in `update_llm_index`, insert the migration check immediately before the `if rebuild or not store.table_exists():` line:

```python
        if not rebuild and store.table_exists():
            store.apply_structural_migrations()
            if store.requires_reembed_migration():
                logger.warning("Schema migration requires re-embedding; forcing LLM index rebuild.")
                rebuild = True
```

The relevant section of `update_llm_index` should now look like:

```python
    with write_store(embed_model_name=model_name) as store:
        if not rebuild and store.table_exists():
            store.apply_structural_migrations()
            if store.requires_reembed_migration():
                logger.warning("Schema migration requires re-embedding; forcing LLM index rebuild.")
                rebuild = True
        if rebuild or not store.table_exists():
            (settings.LLM_INDEX_DIR / "meta.json").unlink(missing_ok=True)
            logger.info("Rebuilding LLM index.")
            store.drop_table()
            ...
```

- [ ] **Step 4: Run new tests to verify they pass**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_ai_indexing.py::test_update_llm_index_applies_structural_migration_without_rebuild src/paperless_ai/tests/test_ai_indexing.py::test_update_llm_index_forces_rebuild_on_reembed_migration -v"
```

Expected: both tests pass.

- [ ] **Step 5: Full indexing regression check**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_ai_indexing.py -v"
```

Expected: all existing tests still pass.

- [ ] **Step 6: Full AI module test run**

```bash
bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/ -v"
```

Expected: all tests pass.

- [ ] **Step 7: Lint**

```bash
ruff check src/paperless_ai/indexing.py src/paperless_ai/tests/test_ai_indexing.py
ruff format src/paperless_ai/indexing.py src/paperless_ai/tests/test_ai_indexing.py
```

- [ ] **Step 8: Commit**

```bash
git add src/paperless_ai/indexing.py src/paperless_ai/tests/test_ai_indexing.py
git commit -m "feat(ai): wire schema migrations into update_llm_index; structural changes avoid re-embed"
```

---

## How to add a migration (reference for future developers)

When a future schema change is needed:

1. Increment `CURRENT_SCHEMA_VERSION` in `vector_store.py`.
2. Append a `Migration` to `MIGRATIONS` with the new version number.
3. If the change is **structural only** (add/rename/drop a column, no embedding content changed):
   - Set `requires_reembed=False`
   - In `apply`, call `table.add_columns({"col": "CAST(NULL AS string)"})`, `table.drop_columns(["col"])`, or `table.alter_columns({"path": "col", "rename": "new_name"})` as appropriate.
4. If the change affects **what text gets embedded** (new fields in `build_llm_index_text`, chunk size change baked into schema, etc.):
   - Set `requires_reembed=True`
   - `apply` can be a no-op (`lambda t: None`) — the framework will trigger a full rebuild.
5. Write tests for the migration in `test_vector_store.py` following the `TestApplyStructuralMigrations` patterns.

Example structural migration adding a `language` column:

```python
CURRENT_SCHEMA_VERSION: int = 2

MIGRATIONS: list[Migration] = [
    Migration(
        version=2,
        description="Add language column for future locale-aware filtering",
        requires_reembed=False,
        apply=lambda table: table.add_columns({"language": "CAST(NULL AS string)"}),
    ),
]
```
