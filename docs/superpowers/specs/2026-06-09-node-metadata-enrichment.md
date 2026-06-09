# LanceDB Node Metadata Enrichment

**Status:** Design
**Date:** 2026-06-09
**Branch target:** `dev`
**Prerequisite for:** AI taxonomy hints (`2026-05-20-ai-taxonomy-hints-design.md`)
**Depends on:** `feature-lancedb-schema-migrate`

## Problem

`build_llm_index_text` currently includes three short structured values in the embedding text:

```python
lines = [
    f"Filename: {doc.filename}",
    f"Storage Path: {doc.storage_path.name if doc.storage_path else ''}",
    f"Archive Serial Number: {doc.archive_serial_number or ''}",
    ...
]
```

These don't belong in the embedding. The embedding should capture semantic content — the meaning of the document — not structured identifiers. Including them means vectors are partly "polluted" with filing metadata, making similarity search less accurate. The existing TODO in `embedding.py:115` explicitly calls this out.

The right home for structured values is `node.metadata` (excluded from the embedding, but surfaced to the LLM when nodes are retrieved as context). `title`, `tags`, `correspondent`, and `document_type` already follow this pattern.

Notes and custom fields stay in the embedding text — Notes is long free text, custom fields are dynamic and their semantic content belongs in the vector.

## Changes

### `paperless_ai/embedding.py` — `build_llm_index_text`

Remove the three lines and the TODO comment:

```python
# remove:
f"Filename: {doc.filename}",
f"Storage Path: {doc.storage_path.name if doc.storage_path else ''}",
f"Archive Serial Number: {doc.archive_serial_number or ''}",
```

`Notes` and `Custom Fields` lines remain.

### `paperless_ai/indexing.py` — `build_document_node`

Add the three fields to the metadata dict:

```python
metadata = {
    "document_id": str(document.id),
    "title": document.title,
    "filename": document.filename or "",
    "storage_path": document.storage_path.name if document.storage_path else None,
    "archive_serial_number": document.archive_serial_number,
    "tags": [t.name for t in document.tags.all()],
    "correspondent": document.correspondent.name if document.correspondent else None,
    "document_type": document.document_type.name if document.document_type else None,
    "created": document.created.isoformat() if document.created else None,
    "added": document.added.isoformat() if document.added else None,
    "modified": document.modified.isoformat(),
}
```

All three new keys must also appear in `excluded_embed_metadata_keys` (consistent with all existing keys — none of the metadata is included in the embedding text).

### `paperless_ai/vector_store.py` — schema migration

Register migration version 2 on the `feature-lancedb-schema-migrate` framework. The embedding text changes, so all existing vectors are stale — a full rebuild is required. The migration's `apply` is a no-op; the rebuild handles regenerating all nodes with the correct metadata.

```python
MIGRATIONS: list[Migration] = [
    Migration(
        version=2,
        description="move filename/storage_path/asn from embedding text to metadata",
        requires_reembed=True,
        apply=lambda table: None,
    ),
]
CURRENT_SCHEMA_VERSION: Final[int] = 2
```

On next `update_llm_index` run, `requires_reembed_migration()` returns `True`, triggering a full drop-and-rebuild. All new nodes carry the three metadata fields. No manual intervention required.

## Impact

- Similarity search quality improves slightly — vectors are more purely semantic.
- The LLM receives `filename`, `storage_path`, and `archive_serial_number` as structured metadata alongside retrieved chunks, rather than embedded in the chunk text. Same information, cleaner separation.
- One forced index rebuild on upgrade (beta: acceptable).
- `node.metadata["storage_path"]`, `node.metadata["filename"]`, `node.metadata["archive_serial_number"]` are available on all retrieved nodes after rebuild — unblocks the taxonomy hints feature.

## Testing

All tests use pytest style — grouped under classes, `@pytest.mark.django_db` on the class, `pytest-mock`'s `mocker` fixture, every fixture and test signature type-annotated. Format with `ruff` directly.

### `paperless_ai/tests/test_embedding.py` (modify)

- `class TestBuildLlmIndexText:`
  - Assert `"Filename:"` is **not** in the output.
  - Assert `"Storage Path:"` is **not** in the output.
  - Assert `"Archive Serial Number:"` is **not** in the output.
  - Assert Notes and Custom Fields lines are still present (regression guard).

### `paperless_ai/tests/test_ai_indexing.py` (modify)

- `class TestBuildDocumentNode:`
  - `filename` is in `node.metadata` and in `excluded_embed_metadata_keys`.
  - `storage_path` is in `node.metadata` (name string) and in `excluded_embed_metadata_keys`; `None` when document has no storage path.
  - `archive_serial_number` is in `node.metadata` and in `excluded_embed_metadata_keys`; `None` when unset.
  - None of the three appear in the embedding text produced for the node.

### `paperless_ai/tests/test_vector_store.py` (modify)

- `class TestSchemaMigrations:`
  - `pending_migrations()` returns the v2 migration when stored version is 1.
  - `requires_reembed_migration()` returns `True` when stored version is 1.
  - `apply_structural_migrations()` stops at the v2 migration (skips reembed entries).
