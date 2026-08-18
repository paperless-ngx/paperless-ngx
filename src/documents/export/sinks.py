from __future__ import annotations

import abc
import errno
import hashlib
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from contextlib import AbstractContextManager
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from documents.file_handling import delete_empty_directories
from documents.utils import compute_checksum
from documents.utils import copy_file_with_basic_stats

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import TextIO


def _dumps(content: list | dict) -> str:
    """Serialize export JSON consistently across all sinks."""
    return json.dumps(content, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)


class StreamingManifestWriter:
    """Incrementally writes a JSON array to a text handle, one record at a time.

    Knows nothing about folders or zips: it writes the array framing and records
    to whatever handle the sink's ``stream()`` yields. The sink owns the handle's
    lifecycle (atomic rename, compare, spooling).
    """

    def __init__(self, handle: TextIO) -> None:
        self._file = handle
        self._first = True
        self._file.write("[")

    def write_record(self, record: dict) -> None:
        if not self._first:
            self._file.write(",\n")
        else:
            self._first = False
        self._file.write(_dumps(record))

    def write_batch(self, records: list[dict]) -> None:
        for record in records:
            self.write_record(record)

    def close(self) -> None:
        """Write the closing bracket. Does NOT close the handle (the sink owns it)."""
        self._file.write("\n]")


class ExportSinkError(Exception):
    """A destination-side failure the sink can describe to the user."""


class ExportSink(AbstractContextManager, abc.ABC):
    """Destination for a document export.

    The command declares export contents via three verbs; the sink decides how to
    persist each. ``arcname`` is always a relative POSIX path
    (e.g. ``"manifest.json"``, ``"originals/foo.pdf"``).

    Contract:
      * At most one ``stream()`` open at a time (it is the manifest);
        ``add_file``/``add_json`` may be called while it is open.
      * Context-manager: normal exit finalizes, an exception aborts. No partial or
        failed run leaves a complete-looking artifact.
    """

    @abc.abstractmethod
    def add_file(
        self,
        source: Path,
        arcname: str,
        *,
        checksum: str | None = None,
    ) -> None: ...

    @abc.abstractmethod
    def add_json(self, content: list | dict, arcname: str) -> None: ...

    def exists(self, arcname: str) -> bool:
        """Best-effort check whether ``arcname`` already exists at the destination."""
        return False

    def refuses_overwrite(self, exc: Exception) -> bool:
        """Whether ``exc`` means the destination refused to replace an object.

        Distinguishes a retention hold — which the caller answers by writing a
        second, version-suffixed copy — from a transient failure, which must
        stay a failure so it is retried rather than silently duplicated.
        """
        return False

    def probe(self) -> None:
        """Write a small object, read it back, delete it.

        Validates credentials and path permissions before the first real
        document depends on the destination. Must be called inside the sink's
        context. The probe object is the only thing a sink ever deletes.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def stream(self, arcname: str) -> AbstractContextManager[TextIO]: ...

    def _open(self) -> None:
        """Hook called on context entry. Override as needed."""

    @abc.abstractmethod
    def _finalize(self) -> None:
        """Commit on clean exit."""

    @abc.abstractmethod
    def _abort(self) -> None:
        """Roll back on exception."""

    def __enter__(self) -> ExportSink:
        self._open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self._abort()
        else:
            self._finalize()


class DirectoryExportSink(ExportSink):
    """Writes loose files into a target directory, with incremental sync.

    Owns the snapshot/skip/compare/prune machinery that used to live in the
    command (``files_in_export_dir``, ``check_and_copy``, ``check_and_write_json``,
    and the ``--delete`` pass).
    """

    def __init__(
        self,
        target: Path,
        *,
        compare_checksums: bool,
        compare_json: bool,
        delete: bool,
    ) -> None:
        self._target = target.resolve()
        self._compare_checksums = compare_checksums
        self._compare_json = compare_json
        self._delete = delete
        self._snapshot: set[Path] = set()
        self._stream_open = False

    def _open(self) -> None:
        if not (self._delete or self._compare_json):
            # The snapshot only feeds JSON comparison and orphan pruning;
            # skip the full tree walk when neither is requested.
            return
        for x in self._target.glob("**/*"):
            if x.is_file():
                self._snapshot.add(x.resolve())

    def add_file(
        self,
        source: Path,
        arcname: str,
        *,
        checksum: str | None = None,
    ) -> None:
        target = (self._target / arcname).resolve()
        self._snapshot.discard(target)
        perform_copy = False
        if target.exists():
            source_stat = source.stat()
            target_stat = target.stat()
            if self._compare_checksums and checksum:
                perform_copy = compute_checksum(target) != checksum
            elif (
                source_stat.st_mtime != target_stat.st_mtime
                or source_stat.st_size != target_stat.st_size
            ):
                perform_copy = True
        else:
            perform_copy = True
        if perform_copy:
            target.parent.mkdir(parents=True, exist_ok=True)
            copy_file_with_basic_stats(source, target)

    @staticmethod
    def _content_unchanged(target: Path, new_bytes: bytes) -> bool:
        """True if ``target`` already holds byte-identical content (BLAKE2b)."""
        return (
            hashlib.blake2b(target.read_bytes()).hexdigest()
            == hashlib.blake2b(new_bytes).hexdigest()
        )

    def add_json(self, content: list | dict, arcname: str) -> None:
        target = (self._target / arcname).resolve()
        json_str = _dumps(content)
        perform_write = True
        if target in self._snapshot:
            self._snapshot.discard(target)
            if self._compare_json and self._content_unchanged(
                target,
                json_str.encode("utf-8"),
            ):
                perform_write = False
        if perform_write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json_str, encoding="utf-8")

    def exists(self, arcname: str) -> bool:
        return (self._target / arcname).exists()

    def refuses_overwrite(self, exc: Exception) -> bool:
        return isinstance(exc, PermissionError) or (
            isinstance(exc, OSError) and exc.errno in (errno.EACCES, errno.EPERM)
        )

    def probe(self) -> None:
        probe_path = self._target / f".paperless-probe-{uuid.uuid4().hex}"
        try:
            self._target.mkdir(parents=True, exist_ok=True)
            probe_path.write_bytes(PROBE_BODY)
            if probe_path.read_bytes() != PROBE_BODY:
                raise ExportSinkError("Probe file read back with unexpected content")
            probe_path.unlink()
        except OSError as e:
            raise ExportSinkError(f"Directory not writable: {e}") from e

    @contextmanager
    def stream(self, arcname: str) -> Iterator[TextIO]:
        if self._stream_open:
            raise RuntimeError("A stream is already open on this sink")
        target = (self._target / arcname).resolve()
        tmp = target.with_suffix(target.suffix + ".tmp")
        target.parent.mkdir(parents=True, exist_ok=True)
        handle = tmp.open("w", encoding="utf-8")
        self._stream_open = True
        try:
            yield handle
        except BaseException:
            handle.close()
            tmp.unlink(missing_ok=True)
            raise
        else:
            handle.close()
            self._commit_streamed_file(target, tmp)
        finally:
            self._stream_open = False

    def _commit_streamed_file(self, target: Path, tmp: Path) -> None:
        if target in self._snapshot:
            self._snapshot.discard(target)
            if self._compare_json and self._content_unchanged(
                target,
                tmp.read_bytes(),
            ):
                tmp.unlink()
                return
        tmp.rename(target)

    def _finalize(self) -> None:
        if self._delete:
            for f in self._snapshot:
                if not f.is_relative_to(self._target):  # pragma: no cover
                    # Defense in depth: a symlink inside the export dir can
                    # resolve outside of it; never delete outside the target.
                    continue
                f.unlink()
                delete_empty_directories(f.parent, self._target)

    def _abort(self) -> None:
        # Folder mode is in-place/incremental: streamed .tmp files are already
        # cleaned in stream(); leave everything else intact and skip the prune.
        return None


class ZipExportSink(ExportSink):
    """Writes a single zip archive, produced atomically only on success.

    Builds into ``<target>/<zip_name>.zip.tmp`` and renames to ``.zip`` on clean
    finalize. The manifest stream is spooled to a temp file in SCRATCH_DIR and
    added as an entry at finalize (a zip entry cannot be interleaved with others).
    """

    def __init__(
        self,
        target: Path,
        zip_name: str,
        *,
        delete: bool = False,
        compression: int = zipfile.ZIP_DEFLATED,
        compresslevel: int | None = None,
    ) -> None:
        self._target = target.resolve()
        self._zip_path = (self._target / zip_name).with_suffix(".zip")
        self._tmp_path = self._zip_path.with_name(self._zip_path.name + ".tmp")
        self._delete = delete
        self._compression = compression
        self._compresslevel = compresslevel
        self._zip: zipfile.ZipFile | None = None
        self._dirs: set[str] = set()
        self._pending_manifest: tuple[Path, str] | None = None
        self._stream_open = False

    def _open(self) -> None:
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        self._zip = zipfile.ZipFile(
            self._tmp_path,
            "w",
            compression=self._compression,
            compresslevel=self._compresslevel,
            allowZip64=True,
        )

    def _ensure_dirs(self, arcname: str) -> None:
        assert self._zip is not None
        dir_arc = ""
        for part in PurePosixPath(arcname).parts[:-1]:
            dir_arc += f"{part}/"
            if dir_arc not in self._dirs:
                self._dirs.add(dir_arc)
                self._zip.mkdir(dir_arc)

    def add_file(
        self,
        source: Path,
        arcname: str,
        *,
        checksum: str | None = None,
    ) -> None:
        assert self._zip is not None
        self._ensure_dirs(arcname)
        self._zip.write(source, arcname=arcname)

    def add_json(self, content: list | dict, arcname: str) -> None:
        assert self._zip is not None
        self._ensure_dirs(arcname)
        self._zip.writestr(arcname, _dumps(content))

    @contextmanager
    def stream(self, arcname: str) -> Iterator[TextIO]:
        if self._stream_open:
            raise RuntimeError("A stream is already open on this sink")
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=settings.SCRATCH_DIR,
            prefix="export-manifest-",
            suffix=".json",
        )
        tmp = Path(tmp_name)
        handle = os.fdopen(fd, "w", encoding="utf-8")
        self._stream_open = True
        try:
            yield handle
        except BaseException:
            handle.close()
            tmp.unlink(missing_ok=True)
            raise
        else:
            handle.close()
            self._pending_manifest = (tmp, arcname)
        finally:
            self._stream_open = False

    def _finalize(self) -> None:
        assert self._zip is not None
        if self._pending_manifest is not None:
            tmp, arcname = self._pending_manifest
            self._ensure_dirs(arcname)
            self._zip.write(tmp, arcname=arcname)
            tmp.unlink(missing_ok=True)
            self._pending_manifest = None
        self._zip.close()
        self._zip = None
        if self._delete:
            self._wipe_destination()
        self._tmp_path.replace(self._zip_path)

    def _wipe_destination(self) -> None:
        skip = {self._zip_path.resolve(), self._tmp_path.resolve()}
        for item in self._target.glob("*"):
            if item.resolve() in skip:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    def _abort(self) -> None:
        if self._zip is not None:
            self._zip.close()
            self._zip = None
        self._tmp_path.unlink(missing_ok=True)
        if self._pending_manifest is not None:
            self._pending_manifest[0].unlink(missing_ok=True)
            self._pending_manifest = None


PROBE_BODY = b"paperless-ngx export probe"


class _SpooledStreamMixin:
    """``stream()`` for remote sinks: spool locally, upload on clean close."""

    _stream_open = False

    @contextmanager
    def stream(self, arcname: str) -> Iterator[TextIO]:
        if self._stream_open:
            raise RuntimeError("A stream is already open on this sink")
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=settings.SCRATCH_DIR,
            prefix="export-stream-",
            suffix=".json",
        )
        tmp = Path(tmp_name)
        handle = os.fdopen(fd, "w", encoding="utf-8")
        self._stream_open = True
        try:
            yield handle
        except BaseException:
            handle.close()
            tmp.unlink(missing_ok=True)
            raise
        else:
            handle.close()
            try:
                self.add_file(tmp, arcname)
            finally:
                tmp.unlink(missing_ok=True)
        finally:
            self._stream_open = False


class S3ExportSink(_SpooledStreamMixin, ExportSink):
    """Uploads loose objects to an S3 bucket under a key prefix (boto3).

    Deliveries are pure push: objects are uploaded as soon as they are added
    and nothing at the destination is ever deleted (except the probe object).
    A failed run may leave already-delivered objects behind; the caller's
    record of the run is the source of truth.
    """

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "",
        endpoint_url: str | None = None,
        region: str | None = None,
        storage_class: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        retention_days: int | None = None,
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix.strip("/") if prefix else ""
        self._endpoint_url = endpoint_url
        self._region = region
        self._storage_class = storage_class
        self._access_key = access_key
        self._secret_key = secret_key
        self._retention_days = retention_days
        self._client = None
        self._lock_mode: str | None = None

    def _key(self, arcname: str) -> str:
        return f"{self._prefix}/{arcname}" if self._prefix else arcname

    def _open(self) -> None:
        try:
            import boto3
            from botocore.config import Config
            from botocore.exceptions import BotoCoreError
        except ImportError as e:  # pragma: no cover - depends on the install
            raise ExportSinkError(
                "S3 export targets require the 'boto3' package, which is not "
                "installed.",
            ) from e

        try:
            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint_url or None,
                region_name=self._region or None,
                aws_access_key_id=self._access_key or None,
                aws_secret_access_key=self._secret_key or None,
                config=Config(retries={"max_attempts": 3, "mode": "standard"}),
            )
        except (BotoCoreError, ValueError) as e:
            raise ExportSinkError(f"Could not create S3 client: {e}") from e
        if self._retention_days:
            self._lock_mode = self._bucket_lock_mode()

    def _bucket_lock_mode(self) -> str:
        """The Object Lock *mode* is bucket configuration; read it, don't store it."""
        from botocore.exceptions import BotoCoreError
        from botocore.exceptions import ClientError

        try:
            lock_config = self._client.get_object_lock_configuration(
                Bucket=self._bucket,
            )
        except (ClientError, BotoCoreError) as e:
            raise ExportSinkError(
                "Retention is configured on this target but the bucket's "
                f"Object Lock configuration could not be read: {e}",
            ) from e
        mode = (
            lock_config.get("ObjectLockConfiguration", {})
            .get("Rule", {})
            .get("DefaultRetention", {})
            .get("Mode")
        )
        return mode or "GOVERNANCE"

    def _extra_args(self) -> dict:
        extra = {}
        if self._storage_class:
            extra["StorageClass"] = self._storage_class
        if self._retention_days:
            extra["ObjectLockMode"] = self._lock_mode
            extra["ObjectLockRetainUntilDate"] = timezone.now() + timedelta(
                days=self._retention_days,
            )
        return extra

    def add_file(
        self,
        source: Path,
        arcname: str,
        *,
        checksum: str | None = None,
    ) -> None:
        self._client.upload_file(
            str(source),
            self._bucket,
            self._key(arcname),
            ExtraArgs=self._extra_args(),
        )

    def add_json(self, content: list | dict, arcname: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=self._key(arcname),
            Body=_dumps(content).encode("utf-8"),
            ContentType="application/json",
            **self._extra_args(),
        )

    def exists(self, arcname: str) -> bool:
        from botocore.exceptions import BotoCoreError
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self._bucket, Key=self._key(arcname))
        except (ClientError, BotoCoreError):
            return False
        return True

    # A retained object under Object Lock answers a replacing PUT with one of
    # these; anything else (throttling, connection resets, a wrong bucket) is a
    # transient or configuration failure and must not be papered over.
    OVERWRITE_REFUSED_CODES = frozenset(
        {"AccessDenied", "InvalidRequest", "InvalidWriteOffset", "OperationAborted"},
    )

    def refuses_overwrite(self, exc: Exception) -> bool:
        from botocore.exceptions import ClientError

        return (
            isinstance(exc, ClientError)
            and exc.response.get("Error", {}).get("Code")
            in self.OVERWRITE_REFUSED_CODES
        )

    def probe(self) -> None:
        # The probe deliberately skips storage class and retention: an archive
        # storage class cannot be read back immediately, and a retained probe
        # object could never be fully removed.
        from botocore.exceptions import BotoCoreError
        from botocore.exceptions import ClientError

        key = self._key(f".paperless-probe-{uuid.uuid4().hex}")
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=PROBE_BODY)
            body = self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
            if body != PROBE_BODY:
                raise ExportSinkError("Probe object read back with unexpected content")
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError) as e:
            raise ExportSinkError(f"S3 connection test failed: {e}") from e
        if self._retention_days:
            # Validates the bucket actually supports Object Lock.
            self._bucket_lock_mode()

    def _finalize(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _abort(self) -> None:
        # Pure push: never delete already-uploaded objects.
        self._finalize()


class SFTPExportSink(_SpooledStreamMixin, ExportSink):
    """Uploads loose files over SFTP under a base path (paramiko).

    The remote host key is pinned: on first successful connection the seen key
    is exposed via ``server_host_key`` so the caller can record it; once a
    pinned key is supplied, a silently changed key refuses to connect.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int | None = None,
        base_path: str = "",
        username: str | None = None,
        secret: str | None = None,
        private_key: str | None = None,
        host_key: str | None = None,
    ) -> None:
        self._host = host
        self._port = port or 22
        self._base = PurePosixPath(base_path) if base_path else PurePosixPath(".")
        self._username = username
        self._secret = secret
        self._private_key = private_key
        self._pinned_host_key = host_key
        self.server_host_key: str | None = None
        self._client = None
        self._sftp = None

    def _load_pkey(self, paramiko):
        from io import StringIO

        errors = []
        for cls in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
            try:
                return cls.from_private_key(
                    StringIO(self._private_key),
                    password=self._secret or None,
                )
            except paramiko.SSHException as e:
                errors.append(f"{cls.__name__}: {e}")
        raise ExportSinkError(
            "Could not load SFTP private key: " + "; ".join(errors),
        )

    def _open(self) -> None:
        try:
            import paramiko
        except ImportError as e:  # pragma: no cover - depends on the install
            raise ExportSinkError(
                "SFTP export targets require the 'paramiko' package, which is "
                "not installed.",
            ) from e

        sink = self

        class _PinOrRecordPolicy(paramiko.MissingHostKeyPolicy):
            def missing_host_key(self, client, hostname, key):
                seen = f"{key.get_name()} {key.get_base64()}"
                sink.server_host_key = seen
                if sink._pinned_host_key and seen != sink._pinned_host_key:
                    raise ExportSinkError(
                        f"SFTP host key for {hostname} has changed; refusing to "
                        "connect. Re-save the export target to trust the new key.",
                    )

        pkey = self._load_pkey(paramiko) if self._private_key else None
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(_PinOrRecordPolicy())
        try:
            client.connect(
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=None if pkey else (self._secret or None),
                pkey=pkey,
                allow_agent=False,
                look_for_keys=False,
                timeout=30,
            )
            self._sftp = client.open_sftp()
        except ExportSinkError:
            client.close()
            raise
        except (paramiko.SSHException, OSError) as e:
            client.close()
            raise ExportSinkError(f"SFTP connection failed: {e}") from e
        self._client = client

    def _remote_path(self, arcname: str) -> PurePosixPath:
        return self._base / arcname

    def _makedirs(self, directory: PurePosixPath) -> None:
        try:
            self._sftp.stat(str(directory))
        except OSError:
            if directory.parent != directory:
                self._makedirs(directory.parent)
            try:
                self._sftp.mkdir(str(directory))
            except OSError:
                # Already exists or was created concurrently; a real permission
                # problem surfaces on the subsequent write.
                pass

    def _replace(self, tmp: PurePosixPath, dest: PurePosixPath) -> None:
        try:
            self._sftp.posix_rename(str(tmp), str(dest))
        except OSError:
            # Server without posix-rename@openssh.com: replace non-atomically.
            # This removal is overwrite semantics, not cleanup.
            try:
                self._sftp.remove(str(dest))
            except OSError:
                pass
            self._sftp.rename(str(tmp), str(dest))

    def add_file(
        self,
        source: Path,
        arcname: str,
        *,
        checksum: str | None = None,
    ) -> None:
        dest = self._remote_path(arcname)
        self._makedirs(dest.parent)
        tmp = dest.with_name(dest.name + ".part")
        self._sftp.put(str(source), str(tmp), confirm=True)
        self._replace(tmp, dest)

    def add_json(self, content: list | dict, arcname: str) -> None:
        dest = self._remote_path(arcname)
        self._makedirs(dest.parent)
        tmp = dest.with_name(dest.name + ".part")
        with self._sftp.open(str(tmp), "wb") as handle:
            handle.write(_dumps(content).encode("utf-8"))
        self._replace(tmp, dest)

    def exists(self, arcname: str) -> bool:
        try:
            self._sftp.stat(str(self._remote_path(arcname)))
        except OSError:
            return False
        return True

    def refuses_overwrite(self, exc: Exception) -> bool:
        return isinstance(exc, PermissionError) or (
            isinstance(exc, OSError) and exc.errno in (errno.EACCES, errno.EPERM)
        )

    def probe(self) -> None:
        dest = self._remote_path(f".paperless-probe-{uuid.uuid4().hex}")
        try:
            self._makedirs(dest.parent)
            with self._sftp.open(str(dest), "wb") as handle:
                handle.write(PROBE_BODY)
            with self._sftp.open(str(dest), "rb") as handle:
                body = handle.read()
            if body != PROBE_BODY:
                raise ExportSinkError("Probe file read back with unexpected content")
            self._sftp.remove(str(dest))
        except OSError as e:
            raise ExportSinkError(f"SFTP connection test failed: {e}") from e

    def _close(self) -> None:
        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None
        if self._client is not None:
            self._client.close()
            self._client = None

    def _finalize(self) -> None:
        self._close()

    def _abort(self) -> None:
        # Pure push: never delete already-uploaded files.
        self._close()
