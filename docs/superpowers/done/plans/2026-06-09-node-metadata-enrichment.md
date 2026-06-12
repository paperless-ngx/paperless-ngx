# Node Metadata Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `filename`, `storage_path`, and `archive_serial_number` from the LanceDB embedding text into `node.metadata`, and register a schema migration that triggers an automatic index rebuild on upgrade.

**Architecture:** Three small, independent changes to two source files, tested first. The migration is a no-op `apply` (the rebuild regenerates all nodes with correct metadata). All three tests go red first, then each implementation makes them green.

**Tech Stack:** pytest, pytest-django, pytest-mock, factory_boy, llama_index `MetadataMode`, `feature-lancedb-schema-migrate` branch (must be the base branch for this work).

**Branch base:** `feature-lancedb-schema-migrate`

---

### Task 1: Fail — embedding text no longer contains the three fields

**Files:**

- Modify: `src/paperless_ai/tests/test_embedding.py`

- [ ] **Step 1: Update `mock_document` fixture to set an explicit `storage_path`**

  The fixture currently doesn't set `storage_path`, so the existing code path (`doc.storage_path.name if doc.storage_path else ''`) would call `.name` on a `MagicMock`. Give it an explicit value so assertions are unambiguous.

  Add these two lines to the `mock_document` fixture after `doc.archive_serial_number = "12345"`:

  ```python
  doc.storage_path = MagicMock()
  doc.storage_path.name = "Finance/Bills"
  ```

- [ ] **Step 2: Update `test_build_llm_index_text` — flip and add assertions**

  The existing test asserts these fields ARE in the result. Change them to assert they are NOT, and add the two missing ones:

  ```python
  # was: assert "Filename: test_file.pdf" in result
  assert "Filename: test_file.pdf" not in result
  assert "Storage Path: Finance/Bills" not in result
  assert "Archive Serial Number: 12345" not in result
  ```

  The assertions for `Notes`, `Content`, and `Custom Field` lines are unchanged — leave them as-is.

- [ ] **Step 3: Run the test to confirm it fails**

  ```
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_embedding.py::test_build_llm_index_text -v"
  ```

  Expected: `FAILED` — `AssertionError: assert 'Filename: test_file.pdf' not in '...'`

---

### Task 2: Pass — remove the three fields from `build_llm_index_text`

**Files:**

- Modify: `src/paperless_ai/embedding.py`

- [ ] **Step 1: Remove the three lines and the TODO comment**

  Current `build_llm_index_text` (lines 114–133). Replace the function body:

  ```python
  def build_llm_index_text(doc: Document) -> str:
      lines = [
          f"Notes: {','.join([str(c.note) for c in Note.objects.filter(document=doc)])}",
      ]

      for instance in doc.custom_fields.all():
          lines.append(f"Custom Field - {instance.field.name}: {instance}")

      lines.append("\nContent:\n")
      lines.append(doc.content or "")

      return _normalize_llm_index_text("\n".join(lines))
  ```

- [ ] **Step 2: Run the test to confirm it passes**

  ```
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_embedding.py::test_build_llm_index_text -v"
  ```

  Expected: `PASSED`

- [ ] **Step 3: Run the full embedding test module to catch regressions**

  ```
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_embedding.py -v"
  ```

  Expected: all green.

- [ ] **Step 4: Commit**

  ```bash
  git add src/paperless_ai/embedding.py src/paperless_ai/tests/test_embedding.py
  git commit -m "refactor(ai): remove filename/storage_path/asn from embedding text"
  ```

---

### Task 3: Fail — `build_document_node` exposes the three fields in metadata

**Files:**

- Modify: `src/paperless_ai/tests/test_ai_indexing.py`

- [ ] **Step 1: Extend `test_build_document_node_structured_fields_in_metadata`**

  This test already checks for `title`, `tags`, etc. Add the three new keys. The `real_document` fixture creates a document with no storage path set, so `storage_path` will be `None` — the key must still be present.

  Replace the existing test body:

  ```python
  @pytest.mark.django_db
  def test_build_document_node_structured_fields_in_metadata(
      real_document: Document,
  ) -> None:
      """Structured fields must be in node.metadata so the LLM receives them via metadata prepend."""
      nodes = indexing.build_document_node(real_document)
      assert len(nodes) > 0
      for node in nodes:
          assert "title" in node.metadata
          assert "tags" in node.metadata
          assert "correspondent" in node.metadata
          assert "document_type" in node.metadata
          assert "created" in node.metadata
          assert "added" in node.metadata
          assert "modified" in node.metadata
          assert "filename" in node.metadata
          assert "storage_path" in node.metadata        # None is fine; key must exist
          assert "archive_serial_number" in node.metadata
  ```

- [ ] **Step 2: Add a test that storage_path carries the name when set**

  Add a new test function after `test_build_document_node_structured_fields_in_metadata`:

  ```python
  @pytest.mark.django_db
  def test_build_document_node_storage_path_name_in_metadata() -> None:
      """storage_path metadata value is the StoragePath name, not None, when set."""
      from documents.tests.factories import DocumentFactory, StoragePathFactory

      sp = StoragePathFactory(name="Finance/Bills")
      doc = DocumentFactory(storage_path=sp)

      nodes = indexing.build_document_node(doc)

      assert len(nodes) > 0
      for node in nodes:
          assert node.metadata["storage_path"] == "Finance/Bills"
  ```

- [ ] **Step 3: Add a test that all three new fields are in `excluded_embed_metadata_keys`**

  Add after the previous test:

  ```python
  @pytest.mark.django_db
  def test_build_document_node_new_fields_excluded_from_embedding(
      real_document: Document,
  ) -> None:
      """filename, storage_path, and archive_serial_number must not appear in embedding text."""
      from llama_index.core.schema import MetadataMode

      nodes = indexing.build_document_node(real_document)
      assert len(nodes) > 0
      for node in nodes:
          assert "filename" in node.excluded_embed_metadata_keys
          assert "storage_path" in node.excluded_embed_metadata_keys
          assert "archive_serial_number" in node.excluded_embed_metadata_keys
          embed_text = node.get_content(metadata_mode=MetadataMode.EMBED)
          assert "filename" not in embed_text
          assert "storage_path" not in embed_text
          assert "archive_serial_number" not in embed_text
  ```

- [ ] **Step 4: Run the new tests to confirm they fail**

  ```
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_ai_indexing.py::test_build_document_node_structured_fields_in_metadata src/paperless_ai/tests/test_ai_indexing.py::test_build_document_node_storage_path_name_in_metadata src/paperless_ai/tests/test_ai_indexing.py::test_build_document_node_new_fields_excluded_from_embedding -v"
  ```

  Expected: all `FAILED` — keys not yet in `node.metadata`.

---

### Task 4: Pass — add the three fields to `build_document_node`

**Files:**

- Modify: `src/paperless_ai/indexing.py`

- [ ] **Step 1: Update the `metadata` dict in `build_document_node`**

  Current metadata dict starts at line 106. Replace it:

  ```python
  metadata = {
      "document_id": str(document.id),
      "title": document.title,
      "filename": document.filename or "",
      "storage_path": document.storage_path.name if document.storage_path else None,
      "archive_serial_number": document.archive_serial_number,
      "tags": [t.name for t in document.tags.all()],
      "correspondent": document.correspondent.name
      if document.correspondent
      else None,
      "document_type": document.document_type.name
      if document.document_type
      else None,
      "created": document.created.isoformat() if document.created else None,
      "added": document.added.isoformat() if document.added else None,
      "modified": document.modified.isoformat(),
  }
  ```

- [ ] **Step 2: Update `excluded_embed_metadata_keys`**

  The `LlamaDocument(...)` call currently has:

  ```python
  excluded_embed_metadata_keys=list(metadata.keys()),
  ```

  This already excludes all keys, so no change needed here — the new keys are automatically included since they're in the dict. Verify `excluded_llm_metadata_keys` still only excludes `"document_id"`:

  ```python
  excluded_llm_metadata_keys=["document_id"],
  ```

  No change needed.

- [ ] **Step 3: Run the failing tests to confirm they pass**

  ```
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_ai_indexing.py::test_build_document_node_structured_fields_in_metadata src/paperless_ai/tests/test_ai_indexing.py::test_build_document_node_storage_path_name_in_metadata src/paperless_ai/tests/test_ai_indexing.py::test_build_document_node_new_fields_excluded_from_embedding -v"
  ```

  Expected: all `PASSED`.

- [ ] **Step 4: Run the full indexing test module**

  ```
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_ai_indexing.py -v"
  ```

  Expected: all green.

- [ ] **Step 5: Commit**

  ```bash
  git add src/paperless_ai/indexing.py src/paperless_ai/tests/test_ai_indexing.py
  git commit -m "feat(ai): add filename/storage_path/asn to node metadata"
  ```

---

### Task 5: Fail — migration v2 is registered

**Files:**

- Modify: `src/paperless_ai/tests/test_vector_store.py`

These tests use the real (non-mocked) `MIGRATIONS` list, so they go red until the migration is registered in Task 6.

- [ ] **Step 1: Add a `TestMetadataEnrichmentMigration` class**

  Add this class near the end of `test_vector_store.py`, before the final `TestApplyStructuralMigrations`:

  ```python
  class TestMetadataEnrichmentMigration:
      def test_current_schema_version_is_2(self) -> None:
          from paperless_ai.vector_store import CURRENT_SCHEMA_VERSION
          assert CURRENT_SCHEMA_VERSION == 2

      def test_migration_v2_registered(self) -> None:
          from paperless_ai.vector_store import MIGRATIONS
          assert len(MIGRATIONS) == 1
          assert MIGRATIONS[0].version == 2
          assert MIGRATIONS[0].requires_reembed is True

      def test_store_at_v1_requires_reembed(self, uri: str) -> None:
          store = _store_at_version(uri, 1)
          assert store.requires_reembed_migration() is True

      def test_store_at_v2_no_pending_migrations(self, uri: str) -> None:
          store = _store_at_version(uri, 2)
          assert store.pending_migrations() == []
          assert store.requires_reembed_migration() is False
  ```

- [ ] **Step 2: Run the tests to confirm they fail**

  ```
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_vector_store.py::TestMetadataEnrichmentMigration -v"
  ```

  Expected: all `FAILED` — `CURRENT_SCHEMA_VERSION` is still 1 and `MIGRATIONS` is still empty.

---

### Task 6: Pass — register migration v2 in `vector_store.py`

**Files:**

- Modify: `src/paperless_ai/vector_store.py`

- [ ] **Step 1: Add the migration and bump the version constant**

  On the `feature-lancedb-schema-migrate` branch, `vector_store.py` has:

  ```python
  CURRENT_SCHEMA_VERSION: Final[int] = 1
  ...
  MIGRATIONS: list[Migration] = []
  ```

  Change both:

  ```python
  CURRENT_SCHEMA_VERSION: Final[int] = 2

  MIGRATIONS: list[Migration] = [
      Migration(
          version=2,
          description="move filename/storage_path/asn from embedding text to metadata; rebuild required",
          requires_reembed=True,
          apply=lambda table: None,
      ),
  ]
  ```

- [ ] **Step 2: Run the migration tests to confirm they pass**

  ```
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_vector_store.py::TestMetadataEnrichmentMigration -v"
  ```

  Expected: all `PASSED`.

- [ ] **Step 3: Run the full vector store test module**

  ```
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_vector_store.py -v"
  ```

  Expected: all green. In particular, `TestSchemaVersioning::test_stored_schema_version_persists_after_reopen` and the `TestMigrationRegistry` tests should still pass — they use `CURRENT_SCHEMA_VERSION` as the baseline.

---

### Task 7: Integration — `update_llm_index` rebuilds when schema version is stale

**Files:**

- Modify: `src/paperless_ai/tests/test_ai_indexing.py`

- [ ] **Step 1: Write the failing integration test**

  Add this test near `test_update_llm_index_rebuilds_on_model_name_change`:

  ```python
  @pytest.mark.django_db
  def test_update_llm_index_rebuilds_on_pending_reembed_migration(
      temp_llm_index_dir: Path,
      real_document: Document,
      mock_embed_model: FakeEmbedding,
  ) -> None:
      """A stale schema version (v1) must trigger a full rebuild on the next index run."""
      from paperless_ai.vector_store import PaperlessLanceVectorStore

      # Build an initial index and then rewind the schema version to 1 to simulate
      # an index created before migration v2 was registered.
      indexing.update_llm_index(rebuild=True)
      store = indexing.get_vector_store()
      store._write_schema_version(1)

      # An incremental run (rebuild=False) must detect the stale version and rebuild.
      with patch("documents.models.Document.objects.all") as mock_all:
          mock_queryset = MagicMock()
          mock_queryset.exists.return_value = True
          mock_queryset.__iter__.return_value = iter([real_document])
          mock_all.return_value = mock_queryset
          indexing.update_llm_index(rebuild=False)

      # After rebuild the schema version must be current.
      reopened = PaperlessLanceVectorStore(uri=str(temp_llm_index_dir))
      assert reopened.stored_schema_version() == 2
  ```

- [ ] **Step 2: Run the test to confirm it fails**

  ```
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_ai_indexing.py::test_update_llm_index_rebuilds_on_pending_reembed_migration -v"
  ```

  Expected: `FAILED` — schema version stays at 1 because migration v2 isn't registered yet.

  _(If it passes already because `update_llm_index` detects a different condition, verify the assertion is actually exercising the migration path and not the model-name path.)_

- [ ] **Step 3: Run the test again now that migration v2 is registered (Task 6)**

  ```
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_ai_indexing.py::test_update_llm_index_rebuilds_on_pending_reembed_migration -v"
  ```

  Expected: `PASSED`.

- [ ] **Step 4: Run the full indexing test module**

  ```
  bash /c/Users/tholmes/Documents/Coding/paperless/vmtest.sh "src/paperless_ai/tests/test_ai_indexing.py -v"
  ```

  Expected: all green.

- [ ] **Step 5: Final commit**

  ```bash
  git add src/paperless_ai/vector_store.py src/paperless_ai/tests/test_vector_store.py src/paperless_ai/tests/test_ai_indexing.py
  git commit -m "feat(ai): register schema migration v2; triggers rebuild for metadata enrichment"
  ```

---

## Self-review checklist

**Spec coverage:**

- ✅ `build_llm_index_text` — three lines removed (Tasks 1–2)
- ✅ `build_document_node` — three fields added to metadata + excluded_embed_metadata_keys (Tasks 3–4)
- ✅ Migration v2 registered with `requires_reembed=True` and no-op apply (Tasks 5–6)
- ✅ `update_llm_index` triggers rebuild on stale schema (Task 7)
- ✅ Tests: `test_embedding.py`, `test_ai_indexing.py`, `test_vector_store.py`

**Placeholder scan:** None found. Every step has exact code or exact commands.

**Type consistency:**

- `metadata` dict key names (`"filename"`, `"storage_path"`, `"archive_serial_number"`) used consistently across Tasks 1–4.
- `CURRENT_SCHEMA_VERSION = 2` and `MIGRATIONS[0].version == 2` are consistent across Tasks 5–6.
- `_store_at_version` and `_node` helpers referenced in Task 5 are defined in the existing `test_vector_store.py` on the `feature-lancedb-schema-migrate` branch.
