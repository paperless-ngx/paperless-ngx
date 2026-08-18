# Scheduled Backup Design

**Date**: 2026-05-15
**Status**: Approved

## Overview

Add a scheduled backup system to paperless-ngx that exports documents as zip files on a user-configurable schedule, retaining the last N backups. The schedule timing is configured via an env var (consistent with all other scheduled tasks), while the backup-specific configuration (output directory, keep count) lives in a new database model editable through the API and UI.

## Goals

- Automated periodic exports without manual intervention
- Zip-based output for simple, unambiguous rotation
- Opt-in: no backup runs unless explicitly configured
- Strongly typed export contract usable by both the CLI and the scheduled task
- UI-editable backup config, no additional env vars beyond the cron schedule

## Non-Goals

- Encrypted backups (future enhancement)
- Age-based or size-based rotation (count-only for now)
- Remote/cloud backup destinations
- Import automation

---

## Section 1: Data Model and API

### `BackupConfiguration` model

New singleton model in `src/paperless/models.py`, following the same `AbstractSingletonModel` pattern as `ApplicationConfiguration`.

```python
class BackupConfiguration(AbstractSingletonModel):
    output_dir = models.CharField(
        verbose_name=_("Backup output directory"),
        max_length=1024,
        blank=True,
        default="",
    )
    keep_count = models.PositiveIntegerField(
        verbose_name=_("Number of backups to keep"),
        default=5,
        help_text=_("Set to 0 to keep all backups."),
    )

    class Meta:
        verbose_name = _("Backup configuration")
```

- `output_dir` blank/empty means backup is disabled (the task treats it as a no-op).
- `output_dir` must be an absolute path. The serializer validates this via a custom validator; `ExportRunner.run()` also calls `.resolve()` on the path unconditionally.
- `keep_count = 0` means keep all backups; no rotation is performed.

### Migration

The migration is created in `src/paperless/migrations/` (not `src/documents/migrations/`), since `BackupConfiguration` lives in the `paperless` app.

### API

- **Serializer**: `BackupConfigurationSerializer` in `src/paperless/serialisers.py`
- **ViewSet**: `BackupConfigurationViewSet` in `src/paperless/views.py` — singleton GET/PATCH, same pattern as `ApplicationConfiguration`
- **Route**: `/api/backup_config/` registered in `src/paperless/urls.py`

---

## Section 2: Export Module

**Revised 2026-08-18** against the export refactor that has landed since this spec was written (PRs #13490 and #13661): `document_exporter`'s logic is no longer a flat `Command.handle()` body. There is now a `src/documents/export/` **package** (`compression.py`: `COMPRESSION_CHOICES`/`COMPRESSION_METHODS`/`compression_available`/`level_error`; `sinks.py`: `ExportSink`/`DirectoryExportSink`/`ZipExportSink`/`StreamingManifestWriter`), and `document_exporter.Command` (`CryptMixin`, `PaperlessCommand`) builds a `sink: ExportSink` in `handle()` and calls `self.dump(sink)`, followed by 7 more helper methods (`generate_base_name`, `generate_document_targets`, `copy_document_files`, `generate_share_link_bundle_target`, `copy_share_link_bundle_file`, `_encrypt_record_inline`, `_write_split_manifest`) that `dump()` calls into — all still `self.`-based methods on the `Command` class, not free functions. This is a materially bigger extraction than "move `handle()`'s body," because `dump()` and its helpers also depend on three CLI-specific things: `self.track(...)` (a `PaperlessCommand`/rich-progress-bar wrapper, `document_exporter.py:442`), one `self.stdout.write(self.style.NOTICE(...))` call (`document_exporter.py:380-384`, the no-passphrase warning), and mixing in `CryptMixin` for `setup_crypto`/`_encrypt_record_inline`. A scheduled Celery task has none of `self.track`/`self.stdout`/`self.style` available, so the extraction has to account for that rather than being a verbatim cut-paste.

New module `src/documents/export/service.py` (inside the existing package — **not** a bare `src/documents/export.py`, since that name is already taken by the package).

### `ExportOptions` dataclass

```python
@dataclass
class ExportOptions:
    target: Path
    compare_checksums: bool = False
    compare_json: bool = False
    delete: bool = False
    use_filename_format: bool = False
    no_archive: bool = False
    no_thumbnail: bool = False
    use_folder_prefix: bool = False
    split_manifest: bool = False
    zip_export: bool = False
    zip_name: str | None = None   # None -> default date-based name
    zip_compression: str | None = None        # None -> "deflated" default
    zip_compression_level: int | None = None
    data_only: bool = False
    passphrase: str | None = None
    batch_size: int = 500
```

Same shape as originally designed, plus `zip_compression`/`zip_compression_level` — both exist on the current CLI (`document_exporter.py:200-220`, added by #13661) and were missing from the original dataclass sketch. `zip_name = None` means the caller wants the default date-based name; resolved internally to `f"export-{timezone.localdate().isoformat()}"` before use. The scheduled task always passes an explicit timestamped name.

### `ExportError` exception

```python
class ExportError(Exception):
    """Raised for export-time validation failures (bad target path, unavailable
    compression method/level, incompatible option combinations)."""
```

Replaces the current `CommandError` raises inside `handle()`/`dump()` (`document_exporter.py:263-300`) for the logic that moves into the service layer — `CommandError` is Django-management-command-specific and isn't appropriate to raise from a Celery task. `document_exporter.Command` catches `ExportError` at its call site and re-raises as `CommandError` for CLI-appropriate display; `scheduled_backup` lets it propagate (Celery/the signal handlers mark the task failed).

### `ExportRunner` class

Owns the state `dump()` and its 7 helper methods currently keep on `self` (`exported_files`, and the option fields), decoupled from `BaseCommand`:

```python
class ExportRunner(CryptMixin):
    def __init__(
        self,
        options: ExportOptions,
        *,
        progress: Callable[[Iterable, ...], Iterable] | None = None,
    ) -> None:
        self.options = options
        self._track = progress or (lambda iterable, **_: iterable)  # no-op when not run interactively
        self.exported_files: set[str] = set()

    def run(self) -> None:
        # 1. Validate target (exists/is_dir/writable) -> ExportError, not CommandError
        # 2. Validate zip compression method/level -> ExportError
        # 3. Build sink (ZipExportSink / DirectoryExportSink), same logic as
        #    today's handle() lines 302-317
        # 4. with FileLock(settings.MEDIA_LOCK), sink:
        #        self.dump(sink)
        ...

    def dump(self, sink: ExportSink) -> None:
        # Same body as today's Command.dump() (document_exporter.py:323-499),
        # with self.X -> self.options.X for option fields, self.track(...) ->
        # self._track(...), and the self.stdout.write(self.style.NOTICE(...))
        # no-passphrase warning -> logger.warning(...) (module logger
        # "documents.export").
        ...

    # generate_base_name / generate_document_targets / copy_document_files /
    # generate_share_link_bundle_target / copy_share_link_bundle_file /
    # _encrypt_record_inline / _write_split_manifest move here unchanged
    # (document_exporter.py:500-657) - no self.X reference in them needs
    # anything Command-specific beyond what's already covered above.
```

`CryptMixin` (`documents/management/commands/mixins.py`) has no `BaseCommand`/`self.stdout` coupling of its own — it's a plain mixin (`setup_crypto`/`encrypt_string`/`decrypt_string`), safe to use outside a management command.

### `run_export()` convenience function

```python
def run_export(options: ExportOptions, *, progress: Callable[..., Iterable] | None = None) -> None:
    ExportRunner(options, progress=progress).run()
```

The single public entry point both callers use — `scheduled_backup` calls it with no `progress`; `document_exporter.Command` passes `progress=self.track` so the CLI keeps its rich progress bar.

### Refactored `document_exporter` management command

`add_arguments` is unchanged. `handle()` becomes a thin adapter:

1. Parse arguments (unchanged)
2. Construct `ExportOptions` from parsed args (including the now-present `zip_compression`/`zip_compression_level`)
3. Call `run_export(options, progress=self.track)`, catching `ExportError` and re-raising as `CommandError(str(e))`

---

## Section 3: Scheduled Task and Rotation

### `scheduled_backup` task in `src/documents/tasks.py`

Imports `ExportOptions`, `ExportError`, `run_export` from `documents.export.service`.

```
1. Load BackupConfiguration (singleton)
2. If output_dir is blank, log a debug message and return (no-op, no PaperlessTask created)
3. Create a PaperlessTask record (TriggerSource.SCHEDULED) to track this run
4. Build zip_name as local-time timestamp: "export-YYYY-MM-DD-HHMMSS"
   using Django's timezone.localtime()
5. Construct ExportOptions(
       target=Path(config.output_dir),
       zip_export=True,
       zip_name=zip_name,
   )
6. Call run_export(options)
7. If keep_count > 0:
       zips = sorted(Path(config.output_dir).glob("export-*.zip"), key=lambda p: p.stat().st_mtime)
       for old_zip in zips[:-keep_count]:
           old_zip.unlink()
8. Mark PaperlessTask as complete (handled by signal handlers)
```

Key design notes:

- Rotation uses `export-*.zip` glob, not `*.zip`, to avoid matching zip files in the directory that paperless did not create.
- Rotation occurs only after a successful export, so a failed run does not consume a rotation slot.
- The timestamp format `YYYY-MM-DD-HHMMSS` in local time ensures multiple runs per day produce distinct filenames without collision.
- `run_export()` raising `ExportError` (bad `output_dir`, unavailable compression) is not caught in the task — it propagates, Celery marks the task failed, and `task_failure_handler` (Section 3, PaperlessTask integration below) updates the `PaperlessTask` record accordingly. No separate error handling needed here.

### PaperlessTask integration

`PaperlessTask` lifecycle is managed entirely by the Celery signal handlers in `src/documents/signals/handlers.py`, not manually inside the task body.

**Changes to `TRACKED_TASKS` and `PaperlessTask.TaskType`:**

- Add `PaperlessTask.TaskType.BACKUP` to the `TaskType` enum in `src/documents/models.py`
- Add `"documents.tasks.scheduled_backup": PaperlessTask.TaskType.BACKUP` to `TRACKED_TASKS`

**Conditional tracking — the no-op case:**

When `BackupConfiguration.output_dir` is blank the task returns immediately, so no record should appear in the Tasks panel. This requires explicit handling in all five signal handlers. Relying on incidental safety (filters that match 0 rows, `DoesNotExist` guards) is fragile and unclear to future maintainers.

The approach for each handler when the task type is `BACKUP`:

| Handler                       | Current behaviour when no record exists                                | Required change                                                                                   |
| ----------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `before_task_publish_handler` | Creates the record                                                     | Check `BackupConfiguration.get_solo().output_dir`; skip `PaperlessTask.objects.create()` if blank |
| `task_prerun_handler`         | `.filter().update()` — silent no-op                                    | Add explicit early return if `BACKUP` task type and no record exists for `task_id`                |
| `task_postrun_handler`        | `DoesNotExist: return` — incidentally safe                             | Add explicit early return if `BACKUP` task type and no record exists for `task_id`                |
| `task_failure_handler`        | `.filter().first()` returns `None`, update skipped — incidentally safe | Add explicit early return if `BACKUP` task type and no record exists for `task_id`                |
| `task_revoked_handler`        | `.filter().update()` — silent no-op                                    | Add explicit early return if `BACKUP` task type and no record exists for `task_id`                |

Extract a helper `_backup_task_is_tracked(task_id: str) -> bool` that returns `PaperlessTask.objects.filter(task_id=task_id).exists()`. The four downstream handlers call this after the `TRACKED_TASKS` check and return early if it returns `False` for a `BACKUP` task. This makes the intent explicit: "this task was intentionally not tracked for this invocation."

---

## Section 4: Beat Schedule

Add to the task list in `parse_beat_schedule()` in `src/paperless/settings/custom.py`:

```python
{
    "name": "Scheduled document backup",
    "env_key": "PAPERLESS_EXPORT_TASK_CRON",
    "env_default": "disable",
    "task": "documents.tasks.scheduled_backup",
    "options": {
        "expires": 1.0 * 60.0 * 60.0,  # 1 hour
    },
},
```

- Default is `"disable"` — the task is not added to the beat schedule unless the env var is explicitly set.
- Setting `PAPERLESS_EXPORT_TASK_CRON=disable` (or simply not setting it) produces no scheduled task and no noise.
- Typical user value: `"0 2 * * *"` (daily at 02:00 local server time).
- `expires` is set to 1 hour: if a scheduled backup has not started within 1 hour of its trigger time (e.g., the Celery worker was down), it is discarded rather than running late. Unlike other tasks whose expiry is tied to a known default interval, this task has a user-defined schedule. 1 hour is a conservative value that prevents stale backup tasks from piling up without being so short that it causes problems on a normally-running worker.

---

## Section 5: Frontend

Location to be decided by co-maintainer (dedicated "Backup" page vs. section within Application Settings). The API contract is independent of this decision.

The UI requires two fields:

- **Output directory** — text input for `output_dir` (absolute path on the server)
- **Keep count** — number input for `keep_count`, with a note that 0 means keep all

The component performs a GET to `/api/backup_config/` on load and a PATCH on save, identical to how the Application Settings component works.

---

## File Change Summary

| File                                                     | Change                                                                                              |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `src/paperless/models.py`                                | Add `BackupConfiguration` model                                                                     |
| `src/paperless/serialisers.py`                           | Add `BackupConfigurationSerializer`                                                                 |
| `src/paperless/views.py`                                 | Add `BackupConfigurationViewSet`                                                                    |
| `src/paperless/urls.py`                                  | Register `/api/backup_config/` route                                                                |
| `src/paperless/settings/custom.py`                       | Add `PAPERLESS_EXPORT_TASK_CRON` beat entry                                                         |
| `src/documents/export/service.py`                        | New module: `ExportOptions`, `ExportError`, `ExportRunner`, `run_export()`                          |
| `src/documents/management/commands/document_exporter.py` | `Command.handle()` becomes a thin adapter; `dump()` and its 7 helper methods move to `ExportRunner` |
| `src/documents/models.py`                                | Add `PaperlessTask.TaskType.BACKUP`                                                                 |
| `src/documents/signals/handlers.py`                      | Add `BACKUP` to `TRACKED_TASKS`; add `_backup_task_is_tracked()`; update all 5 signal handlers      |
| `src/documents/tasks.py`                                 | Add `scheduled_backup` task                                                                         |
| `src-ui/`                                                | New or extended settings component (location TBD)                                                   |
| `src/paperless/migrations/`                              | New migration for `BackupConfiguration`                                                             |

---

## Testing

- **`src/paperless/tests/test_backup_config.py`** — model, serializer, API (GET/PATCH)
- **`src/documents/tests/export/test_service.py`** — new unit tests for `ExportRunner`/`run_export()` directly, alongside the existing `src/documents/tests/export/test_compression.py` and `test_sinks.py` (the `export/` test package already exists and mirrors the `documents/export/` package structure — follow that convention rather than a flat `test_export.py`). `test_management_exporter.py` retains its existing CLI wiring tests and gains tests for the thin-adapter behaviour (arg parsing → `ExportOptions` → `run_export`, `ExportError` → `CommandError` translation)
- **`src/documents/tests/test_tasks_backup.py`** — `scheduled_backup` task: no-op when `output_dir` blank, export called with correct options, rotation deletes correct files, rotation skipped when `keep_count=0`
- **`src/documents/tests/test_task_signals.py`** — signal handler behaviour for `BACKUP` task type: no record created when `output_dir` blank, all downstream handlers skip cleanly when no record exists, normal lifecycle when `output_dir` is set
- Frontend unit tests for the settings component
