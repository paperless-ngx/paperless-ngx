"""
Event-triggered delivery of single documents to export targets.

This is the export feature's engine: it turns an ``ExportTarget`` into a
sink, names the objects, writes file plus optional metadata sidecar and
completes the ``ExportRecord``. It is deliberately separate from the
backup machinery in ``document_exporter`` — an export is a portable copy
for humans and other systems, not a restorable snapshot.
"""

from __future__ import annotations

import logging
from pathlib import Path
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from django.utils import timezone

from documents.export.sinks import DirectoryExportSink
from documents.export.sinks import ExportSinkError
from documents.export.sinks import S3ExportSink
from documents.export.sinks import SFTPExportSink
from documents.file_handling import format_filename
from documents.file_handling import generate_filename
from documents.models import ExportRecord
from documents.models import ExportTarget
from documents.models import WorkflowActionExport

if TYPE_CHECKING:
    from documents.export.sinks import ExportSink
    from documents.models import Document

logger = logging.getLogger("paperless.export")


def build_sink(target: ExportTarget) -> ExportSink:
    config = target.config or {}
    if target.kind == ExportTarget.Kind.S3:
        return S3ExportSink(
            bucket=config.get("bucket", ""),
            prefix=config.get("prefix", ""),
            endpoint_url=config.get("endpoint") or None,
            region=config.get("region") or None,
            storage_class=config.get("storage_class") or None,
            access_key=target.access_key,
            secret_key=target.secret_key,
            retention_days=target.retention_days,
        )
    elif target.kind == ExportTarget.Kind.SFTP:
        return SFTPExportSink(
            host=config.get("host", ""),
            port=config.get("port") or None,
            base_path=config.get("path", ""),
            username=target.access_key,
            secret=target.secret_key,
            private_key=target.private_key,
            host_key=config.get("host_key") or None,
        )
    elif target.kind == ExportTarget.Kind.LOCAL:
        return DirectoryExportSink(
            Path(config.get("path", "")),
            compare_checksums=False,
            compare_json=False,
            delete=False,
        )
    raise ExportSinkError(f"Unknown export target kind: {target.kind}")


def probe_target(target: ExportTarget) -> None:
    """
    Write a small object to the target, read it back and delete it.

    Raises ExportSinkError with a user-readable message on failure. For SFTP
    targets the seen host key is pinned into ``target.config`` on first
    success — the caller owns saving the target.
    """
    sink = build_sink(target)
    with sink:
        sink.probe()
    if (
        target.kind == ExportTarget.Kind.SFTP
        and isinstance(sink, SFTPExportSink)
        and sink.server_host_key
        and not (target.config or {}).get("host_key")
    ):
        config = dict(target.config or {})
        config["host_key"] = sink.server_host_key
        target.config = config


def build_metadata_sidecar(document: Document) -> dict:
    return {
        "id": document.pk,
        "title": document.title,
        "created": document.created,
        "added": document.added,
        "modified": document.modified,
        "correspondent": document.correspondent.name
        if document.correspondent
        else None,
        "document_type": document.document_type.name
        if document.document_type
        else None,
        "storage_path": document.storage_path.name if document.storage_path else None,
        "tags": [tag.name for tag in document.tags.all()],
        "custom_fields": {
            instance.field.name: instance.value
            for instance in document.custom_fields.all()
        },
        "original_filename": document.original_filename,
        "original_checksum": document.checksum,
        "archive_checksum": document.archive_checksum,
        "exported_at": timezone.now(),
    }


def _base_name(document: Document, template: str) -> PurePosixPath:
    """
    The object name for this document, relative to the target's root.

    An action's path template works exactly like a storage path: the rendered
    result is the full path and filename, with the extension appended
    automatically. Without a template — or when it fails to render, which
    loses the template rather than failing the export — the document keeps
    the name it has in the media directory. Either way the name is stable
    per document, so a re-export addresses its own previous copy. Rendering
    safety (absolute paths, traversal) is enforced by the template engine.
    """
    if template:
        rendered = format_filename(document, template)
        if rendered:
            return PurePosixPath(
                Path(rendered).as_posix() + document.file_type,
            )
        logger.warning(
            "Export path template %r did not render for document %s, "
            "falling back to the media filename",
            template,
            document.pk,
        )
    return PurePosixPath(generate_filename(document).as_posix())


def _version_suffixed(arcname: str, stamp: str) -> str:
    path = PurePosixPath(arcname)
    return str(path.with_name(f"{path.stem}.v{stamp}{path.suffix}"))


def _exists(sink: ExportSink, arcname: str) -> bool:
    try:
        return sink.exists(arcname)
    except Exception:
        return False


def _put_file(
    sink: ExportSink,
    source: Path,
    arcname: str,
    checksum: str | None,
    on_conflict: str,
) -> str:
    """
    Deliver one file, returning the key actually written (which may be a key
    that already existed and was skipped).

    Even when the action allows overwriting, a destination that refuses to
    replace an existing object — an Object-Lock-retained S3 object — gets a
    second, version-suffixed copy instead of a failure. The fallback is
    deliberately narrow: only an error the sink recognises as a refusal to
    replace, and only when the object really is already there. A transient
    failure stays a failure so the task retries it, rather than quietly
    accumulating a duplicate on every hiccup.
    """
    if on_conflict == WorkflowActionExport.ConflictPolicy.SKIP and _exists(
        sink,
        arcname,
    ):
        logger.info("Destination already has %s, skipping", arcname)
        return arcname
    try:
        sink.add_file(source, arcname, checksum=checksum)
    except Exception as e:
        if not sink.refuses_overwrite(e):
            raise
        if not _exists(sink, arcname):
            raise
        alternate = _version_suffixed(
            arcname,
            timezone.now().strftime("%Y%m%d%H%M%S"),
        )
        logger.info(
            "Destination refused overwrite of %s, writing %s instead",
            arcname,
            alternate,
        )
        sink.add_file(source, alternate, checksum=checksum)
        return alternate
    return arcname


def deliver_export_record(record: ExportRecord) -> None:
    """
    Deliver the record's document to its target and mark the record complete.

    Raises on failure — retry and failure bookkeeping belong to the caller
    (the celery task).
    """
    document = record.document
    if document is None:
        raise ExportSinkError("Document no longer exists")
    target = record.target
    if target is None:
        raise ExportSinkError("Export target no longer exists")

    action = record.action
    include_original = action.include_original if action else True
    include_archive = action.include_archive if action else False
    write_sidecar = action.write_metadata_sidecar if action else True
    path_template = action.path if action else ""
    on_conflict = (
        action.on_conflict if action else WorkflowActionExport.ConflictPolicy.OVERWRITE
    )

    include_archive = include_archive and document.has_archive_version
    if not include_original and not include_archive:
        raise ExportSinkError(
            "Nothing to deliver: the action exports only the archive "
            "version and this document has none",
        )

    base = _base_name(document, path_template)
    stem = base.with_suffix("") if base.suffix else base
    original_key = str(base)
    archive_key = f"{stem}.pdf"
    if include_original and archive_key == original_key:
        archive_key = f"{stem}-archive.pdf"
    sidecar_key = f"{stem}.metadata.json"

    delivered_key: str | None = None
    checksum: str | None = None
    size: int | None = None

    sink = build_sink(target)
    with sink:
        if on_conflict == WorkflowActionExport.ConflictPolicy.SUFFIX:
            # Never overwrite: if anything of this delivery is already
            # there, the whole delivery moves to one shared version suffix
            # so file, archive and sidecar stay a matching set.
            wanted = [
                key
                for key, included in (
                    (original_key, include_original),
                    (archive_key, include_archive),
                    (sidecar_key, write_sidecar),
                )
                if included
            ]
            if any(_exists(sink, key) for key in wanted):
                stamp = timezone.now().strftime("%Y%m%d%H%M%S")
                original_key = _version_suffixed(original_key, stamp)
                archive_key = _version_suffixed(archive_key, stamp)
                sidecar_key = f"{stem}.v{stamp}.metadata.json"
        if include_original:
            delivered_key = _put_file(
                sink,
                document.source_path,
                original_key,
                document.checksum,
                on_conflict,
            )
            checksum = document.checksum
            size = document.source_path.stat().st_size
        if include_archive:
            key = _put_file(
                sink,
                document.archive_path,
                archive_key,
                document.archive_checksum,
                on_conflict,
            )
            if delivered_key is None:
                delivered_key = key
                checksum = document.archive_checksum
                size = document.archive_path.stat().st_size
        if write_sidecar and not (
            on_conflict == WorkflowActionExport.ConflictPolicy.SKIP
            and _exists(sink, sidecar_key)
        ):
            sink.add_json(build_metadata_sidecar(document), sidecar_key)

    record.status = ExportRecord.Status.COMPLETE
    record.object_key = delivered_key or ""
    record.checksum = checksum or ""
    record.size_bytes = size
    record.finished_at = timezone.now()
    record.last_error = None
    record.save(
        update_fields=[
            "status",
            "object_key",
            "checksum",
            "size_bytes",
            "finished_at",
            "last_error",
        ],
    )
    logger.info(
        "Exported document %s to %s as %s",
        record.document_pk,
        target,
        record.object_key,
    )
