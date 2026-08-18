# Pluggable Document Storage Design

**Date:** 2026-04-23
**Status:** Approved

## Overview

Replace the hardcoded local filesystem storage in paperless-ngx with a pluggable `DocumentStorage` Protocol. Ship two built-in backends — `LocalFilesystemBackend` (default, zero config change) and `S3CompatibleBackend` (supports AWS S3 and any S3-compatible endpoint). Third parties can implement the Protocol to provide their own backends.

## Scope

- **In scope:** original documents, PDF/A archives
- **Out of scope:** thumbnails (stay on local filesystem, regenerable), consumption directory (stays local)
- **Frontend impact:** none — S3 is invisible; Django proxies all file access

## Protocol

Defined in `src/paperless/storage.py`:

```python
class DocumentStorage(Protocol):
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...
    def open(self, name: str) -> IO[bytes]: ...
    def save(self, name: str, content: IO[bytes]) -> str: ...  # returns actual name used
    def delete(self, name: str) -> None: ...
    def exists(self, name: str) -> bool: ...
    def move(self, old_name: str, new_name: str) -> None: ...
    def list_files(self, prefix: str = "") -> Iterable[str]: ...
    def size(self, name: str) -> int: ...
```

`name` is always the relative key as stored in the DB (e.g. `2024/my-invoice.pdf`). All operations including `open()` must be called within a `with storage:` block — the context manager handles connection lifecycle and backend-specific cleanup.

## Storage Instances

Two module-level singletons in `src/paperless/storage.py`, each an instance of the configured backend class:

```python
original_storage: DocumentStorage = _build("originals")
archive_storage: DocumentStorage  = _build("archive")
```

`_build(prefix)` reads `PAPERLESS_DOCUMENT_STORAGE_BACKEND` and `PAPERLESS_DOCUMENT_STORAGE_OPTIONS` from settings, instantiates the backend class with the configured options plus the paperless-controlled prefix. The prefix distinguishes originals from archives within the same bucket or directory root — it is not stored in the DB key.

## Configuration

Two new settings, using the existing key-value dict mechanism:

| Setting                              | Default                                    | Description                                                  |
| ------------------------------------ | ------------------------------------------ | ------------------------------------------------------------ |
| `PAPERLESS_DOCUMENT_STORAGE_BACKEND` | `paperless.storage.LocalFilesystemBackend` | Dotted Python path to any class satisfying `DocumentStorage` |
| `PAPERLESS_DOCUMENT_STORAGE_OPTIONS` | `{}`                                       | Dict of kwargs passed to the backend constructor             |

**Example — S3-compatible:**

```
PAPERLESS_DOCUMENT_STORAGE_BACKEND=paperless.storage.S3CompatibleBackend
PAPERLESS_DOCUMENT_STORAGE_OPTIONS={"bucket_name": "my-docs", "endpoint_url": "https://s3.wasabi.com", "region_name": "us-east-1", "access_key": "...", "secret_key": "..."}
```

Existing users set nothing — `LocalFilesystemBackend` with no options is the default.

## Built-in Backends

### `LocalFilesystemBackend`

- `__enter__`: initialises tracking of directories affected during the context
- `__exit__`: calls `delete_empty_directories()` for all tracked dirs; no-op on exception
- `open/save/delete/exists/move`: direct `Path` + `shutil` operations rooted at `settings.ORIGINALS_DIR` / `settings.ARCHIVE_DIR` (via the prefix passed by `_build`)
- `move()`: `shutil.move()` — atomic on same filesystem
- `list_files()`: `Path.rglob("*")`

### `S3CompatibleBackend`

- Wraps `django-storages` S3 backend (`storages.backends.s3boto3.S3Boto3Storage`) for `open`, `save`, `delete`, `exists`
- `__enter__`: initialises boto3 client/session
- `__exit__`: no cleanup required (no empty directory concept on S3)
- `move()`: boto3 `copy_object` (server-side, no data transfer) + `delete_object`
- `open()`: returns streaming S3 response body; caller's `with` block closes the HTTP connection
- `list_files()`: S3 `list_objects_v2` with prefix
- Works with any S3-compatible endpoint via `endpoint_url` option

## Data Migration

One Django migration strips the stored prefix from existing rows:

- `document.filename`: `documents/originals/2024/invoice.pdf` → `2024/invoice.pdf`
- `document.archive_filename`: `documents/archive/2024/invoice.pdf` → `2024/invoice.pdf`

The prefix is now owned by the storage instance, not the DB key.

## `migrate_storage` Management Command

```
manage.py migrate_storage [--dry-run] [--no-delete]
    [--source-backend=<dotted.path>] [--source-options=<json>]
```

Transfers all document files from one storage backend to another. The user updates `PAPERLESS_DOCUMENT_STORAGE_BACKEND` in their config first, then runs this command to move existing files.

The destination is always the currently configured backend (from settings). The source is specified via `--source-backend` / `--source-options`, defaulting to `LocalFilesystemBackend` with no options if omitted (covering the most common migration path: local → S3).

**Flow:**

1. Instantiate source backend (from CLI args or default) and destination backend (from current settings)
2. Iterate `Document.objects.only("filename", "archive_filename")`
3. For each file (original + archive):
   - Skip with warning if missing from source
   - Skip silently if already present on destination (idempotent — safe to re-run)
   - Copy: `destination.save(name, source.open(name))`
   - Unless `--no-delete`: `source.delete(name)`
4. Report counts: moved / skipped / failed
5. `--dry-run`: prints actions without touching files

Individual failures are logged and counted but do not abort the run. Bidirectional: local → S3, S3 → local, S3 → S3.

## Files to Create

| File                                                    | Purpose                                                                        |
| ------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `src/paperless/storage.py`                              | Protocol, built-in backends, `original_storage` / `archive_storage` singletons |
| `src/documents/management/commands/migrate_storage.py`  | Migration command                                                              |
| `src/documents/migrations/XXXX_strip_storage_prefix.py` | Strip prefix from existing filename rows                                       |

## Files to Modify

| File                                                     | Change                                                                                                           |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `src/paperless/settings/__init__.py`                     | Add `PAPERLESS_DOCUMENT_STORAGE_BACKEND`, `PAPERLESS_DOCUMENT_STORAGE_OPTIONS`                                   |
| `src/documents/models.py`                                | `source_file`, `archive_file` use storage instances; `source_path` returns temp file for subprocess callers      |
| `src/documents/consumer.py`                              | `_write()` → `storage.save()`; remove `mkdir` calls                                                              |
| `src/documents/signals/handlers.py`                      | `shutil.move()` → `storage.move()`; remove `create_source_path_directory` / `delete_empty_directories` callsites |
| `src/documents/tasks.py`                                 | Same as signals                                                                                                  |
| `src/documents/file_handling.py`                         | `exists()` checks and directory references use storage API                                                       |
| `src/documents/views.py`                                 | File-serving views use `storage.open()` within context; wrap for `FileResponse` lifecycle                        |
| `src/documents/management/commands/document_importer.py` | Replace `Path.glob()` and direct copies with storage API                                                         |
| `src/documents/management/commands/document_exporter.py` | Replace direct file copies and `FileLock`-guarded writes with storage API                                        |

## Locking & Concurrency

The codebase serialises all document file write/move operations with `FileLock(settings.MEDIA_LOCK)`, where `MEDIA_LOCK = MEDIA_ROOT / "media.lock"`. This is used in `consumer.py`, `signals/handlers.py`, `tasks.py`, `mail.py`, `document_importer.py`, and `document_exporter.py`.

**The lock file stays on the local filesystem regardless of backend.** `MEDIA_LOCK` lives under `MEDIA_ROOT`, which is the local path even when documents are stored on S3. This means:

- **Single-host deployments** (the common case — Docker Compose, single server): the `FileLock` continues to work correctly. All Celery workers and the Django process share the same lock file. No change required.
- **Multi-host deployments**: the `FileLock` is already broken for these today — each host has its own lock file. This is a pre-existing limitation and is out of scope for this feature.

**Callsite structure** — the storage context manager nests inside the existing lock, preserving current behaviour:

```python
with FileLock(settings.MEDIA_LOCK):
    with original_storage as storage:
        storage.move(old_name, new_name)
```

**`generate_unique_filename` race:** this function checks `storage.exists()` then saves, which is not atomic on S3. The `FileLock` already serialises this on a single host. For multi-host this is a pre-existing gap — not introduced by this feature.

**Future path for multi-host:** replace `FileLock` with a database-level advisory lock or Redis lock. Out of scope here.

## Key Invariants

- The context manager is required for all storage operations, including reads
- `name` is always the relative key — never an absolute path or URL
- The backend prefix (`originals` / `archive`) is paperless-controlled and never stored in the DB
- `LocalFilesystemBackend` is the default — existing deployments require no config change
- The migrate command is idempotent and can be re-run after partial failure
