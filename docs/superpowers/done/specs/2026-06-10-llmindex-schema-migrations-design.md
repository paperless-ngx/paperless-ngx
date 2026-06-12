# LLM Index Schema Migrations (second spec)

Date: 2026-06-10
Depends on: `docs/superpowers/specs/2026-06-10-sqlite-vec-vector-store-design.md` and its implementation plan (`docs/superpowers/plans/2026-06-10-sqlite-vec-transition.md`). This spec layers on top of the completed sqlite-vec transition; do not start it before that branch lands.
Supersedes: PR #12968 (in-place LanceDB migrations). The machinery design there is carried over nearly verbatim; only the storage backend specifics change. #12968 should be closed with a pointer here once this ships.

Scope update (user decision, 2026-06-10): the `embedding.py:115` metadata restructure originally drafted as Part 2 of this spec was folded into the transition plan instead (its Task 5), because the transition forces a full rebuild anyway, so the embedded-text change rides along with no extra re-embed cost. This spec is now machinery-only: it ships with an EMPTY migration registry, ready for whatever schema change comes next. Part 2 below is retained as the worked example of how a re-embed migration would be registered, since the next one will not have a free rebuild to piggyback on.

## Part 1: Schema migration machinery (ported from PR #12968)

### What carries over unchanged

The PR's design survives the store swap intact and is adopted as-is:

- `Migration` frozen dataclass: `version: int`, `description: str`, `requires_reembed: bool`, `apply: Callable` (compare/hash-excluded field).
- `MIGRATIONS: list[Migration]` ordered registry + `CURRENT_SCHEMA_VERSION: Final[int]` in `vector_store.py`. To add a migration: bump the constant, append an entry.
- Store surface: `stored_schema_version() -> int` (0 when unrecorded, so pre-versioning tables treat every migration as pending), `pending_migrations()`, `requires_reembed_migration()`, `apply_structural_migrations() -> list[Migration]`.
- The stop-at-first-reembed-boundary rule in `apply_structural_migrations()`: structural migrations are applied in version order only up to the first pending `requires_reembed=True` entry, so the version counter can never jump past a re-embed boundary and silently skip the rebuild. (This was the subtle correctness insight of #12968; preserve the comment.)
- The `update_llm_index()` hook, verbatim from the PR:

```python
    with write_store(embed_model_name=model_name) as store:
        if not rebuild and store.table_exists():
            store.apply_structural_migrations()
            if store.requires_reembed_migration():
                logger.warning(
                    "Schema migration requires re-embedding; forcing LLM index rebuild.",
                )
                rebuild = True
```

- Test approach from the PR: mock `MIGRATIONS`/`CURRENT_SCHEMA_VERSION` with `mocker.patch`, spy on `drop_table` to distinguish in-place from rebuild, one test per path (structural applied without rebuild; pending re-embed forces rebuild).

### What changes for sqlite-vec

**1. Version storage: `index_meta['schema_version']` instead of `schema_version.json`.**
The Lance store needed a sidecar JSON file because Lance had no convenient mutable metadata. The sqlite-vec store already has the `index_meta` key/value table, which is transactional with the data itself (a migration and its version bump commit atomically, which the file never could). Concretely:

- `_create_table(dim)` additionally writes `schema_version = str(CURRENT_SCHEMA_VERSION)` (fresh tables are always current).
- `stored_schema_version()` reads the meta key, returns 0 on absence/garbage.
- `drop_table()` already does `DELETE FROM index_meta`, which clears the version with it. No sidecar file, no unlink bookkeeping.
- `apply_structural_migrations()` writes the new version inside the same transaction as the last applied migration.

**2. `apply` receives the store, not a table handle.**
Lance migrations got the raw table for `add_columns`/`alter_columns`. vec0 virtual tables do not support arbitrary `ALTER TABLE`, so structural migrations are SQL against the store's connection. Signature: `apply: Callable[[PaperlessSqliteVecVectorStore], None]`. The store exposes what migrations need: `.client` (connection), `._table_name`, `.vector_dim()`, and the rebuild helper below.

**3. Structural migrations are create+copy+rename, sharing the compact() machinery.**
The sqlite-vec `compact()` already implements the only structural mutation vec0 supports: build a new table, `INSERT INTO ... SELECT` (vectors copied bit-for-bit, no re-embedding), drop old, rename. Factor it into a shared helper on the store:

```python
def rebuild_table(
    self,
    *,
    create_sql: str | None = None,
    copy_select: str | None = None,
) -> None:
    """Copy live rows into a freshly created table and swap it in.

    Defaults reproduce the current schema (compaction). Structural
    migrations pass a modified CREATE statement and a matching SELECT
    (e.g. adding a column with a literal default). Runs in one
    transaction; VACUUM afterwards.
    """
```

`compact()` becomes a thin caller (threshold check + `rebuild_table()`), and a structural migration like "add a `+page_count` aux column" is:

```python
Migration(
    version=2,
    description="add page_count auxiliary column",
    requires_reembed=False,
    apply=lambda store: store.rebuild_table(
        create_sql=...,        # CREATE VIRTUAL TABLE ... with the new column
        copy_select="SELECT id, document_id, modified, node_content, embedding, '' FROM {old}",
    ),
)
```

A pleasant consequence: every structural migration is also a compaction (the copy drops dead rows), and the file-format risk surface is one helper with one test suite instead of two code paths.

**4. Bootstrap version for the sqlite-vec store is 1.**
The transition plan ships the new store without machinery; tables it creates carry no `schema_version` key and therefore read as 0. This release lands with `CURRENT_SCHEMA_VERSION = 1` and `MIGRATIONS = []`, so the bootstrap is unconditionally safe: a 0-version table has no pending migrations and `apply_structural_migrations()` simply stamps it to 1. (The metadata restructure having moved into the transition itself is what makes this clean; the registry's first real entry will be v2, written against tables that are all stamped.)

## Part 2 (worked example, IMPLEMENTED IN THE TRANSITION): the metadata TODO as a re-embed migration

This section was implemented as Task 5 of the transition plan and ships with the store swap, not with this spec. It is kept as the reference example of how to register the next re-embed migration.

### The change

`build_llm_index_text()` currently embeds three short structured values in the body text:

```python
        f"Filename: {doc.filename}",
        f"Storage Path: {doc.storage_path.name if doc.storage_path else ''}",
        f"Archive Serial Number: {doc.archive_serial_number or ''}",
```

Per the TODO, move them to `node.metadata` (excluded from embeddings, visible to the LLM via llama-index's metadata prepend), the same treatment title/tags/correspondent/document_type got in PR #12944. Notes and Custom Fields stay in the body (long free text / dynamic count, as the TODO says).

1. `embedding.py build_llm_index_text()`: delete the three lines above (the `lines` list keeps Notes, Custom Fields, and Content). Update the TODO comment to describe only what remains intentional (Notes/Custom Fields stay embedded), or delete it.
2. `indexing.py build_document_node()` metadata dict gains:

```python
        "filename": doc.filename,
        "storage_path": document.storage_path.name if document.storage_path else None,
        "archive_serial_number": document.archive_serial_number,
```

(`None`/int values are fine here: this dict lives in the node-content JSON, not in vec0 metadata columns; only `document_id`/`modified` are columns with the NULL restriction. Matches the existing convention of `correspondent: None`.) 3. `excluded_embed_metadata_keys=list(metadata.keys())` already covers the new keys; `excluded_llm_metadata_keys` stays `["document_id"]` so the LLM sees the new fields.

### Why this class of change needs a migration

Removing the three lines changes the embedded text of every document, so stored vectors no longer match what the current code would embed. Incremental updates only re-embed documents whose `modified` changed, so without a forced rebuild the index would be a mixed old/new-text population indefinitely. This particular change escaped that fate only because the transition's forced rebuild covers it. The next embedded-text change will not have that luxury and gets registered like this:

```python
CURRENT_SCHEMA_VERSION: Final[int] = 2

MIGRATIONS: list[Migration] = [
    Migration(
        version=2,
        description="<what changed about the embedded text>",
        requires_reembed=True,
        apply=lambda store: None,
    ),
]
```

On the first `update_llm_index` after upgrade, the hook sees the pending re-embed migration, logs, and rebuilds.

### Test plan

Machinery only (the metadata change is tested in the transition plan's Task 5). Port of the #12968 tests, dedicated file `test_vector_store_migrations.py`: structural migration applies in-place without `drop_table`; pending re-embed forces rebuild; version stamping on create/drop; bootstrap stamping of a pre-machinery 0-version table to 1; stop-at-boundary with a mixed [structural v2, reembed v3, structural v4] registry asserting v4 is NOT applied and the stored version stays at 2; `rebuild_table()` round-trips rows byte-for-byte (shared with compact tests).

### Open questions

- PR #12968 disposition: close with a comment pointing at this spec once the machinery lands (the Lance-specific `add_columns` path has no successor; vec0 cannot do in-place column adds).
- `created`/`added` fields are also candidates for future structural metadata work, but nothing needs them now (YAGNI; noted only so the next reader does not re-derive it).
