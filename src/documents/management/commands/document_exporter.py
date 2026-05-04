import hashlib
import json
import os
import shutil
import tempfile
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from allauth.mfa.models import Authenticator
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.models import SocialToken
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.core.management.base import CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from filelock import FileLock
from guardian.models import GroupObjectPermission
from guardian.models import UserObjectPermission

if TYPE_CHECKING:
    from collections.abc import Generator

    from django.db.models import QuerySet

if settings.AUDIT_LOG_ENABLED:
    from auditlog.models import LogEntry

from documents.file_handling import delete_empty_directories
from documents.file_handling import generate_filename
from documents.management.commands.base import PaperlessCommand
from documents.management.commands.mixins import CryptMixin
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import SavedView
from documents.models import SavedViewFilterRule
from documents.models import ShareLink
from documents.models import ShareLinkBundle
from documents.models import StoragePath
from documents.models import Tag
from documents.models import UiSettings
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowActionEmail
from documents.models import WorkflowActionWebhook
from documents.models import WorkflowTrigger
from documents.settings import EXPORTER_ARCHIVE_NAME
from documents.settings import EXPORTER_FILE_NAME
from documents.settings import EXPORTER_SHARE_LINK_BUNDLE_NAME
from documents.settings import EXPORTER_THUMBNAIL_NAME
from documents.utils import compute_checksum
from documents.utils import copy_file_with_basic_stats
from paperless import version
from paperless.models import ApplicationConfiguration
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


def serialize_queryset_batched(
    queryset: "QuerySet[Any]",
    *,
    batch_size: int = 500,
) -> "Generator[list[dict], None, None]":
    """Yield batches of serialized records from a QuerySet.

    Each batch is a list of dicts in Django's Python serialization format.
    Uses QuerySet.iterator() to avoid loading the full queryset into memory,
    and islice to collect chunk-sized batches serialized in a single call.
    """
    iterator = queryset.iterator(chunk_size=batch_size)
    while chunk := list(islice(iterator, batch_size)):
        yield serializers.serialize("python", chunk)


class StreamingManifestWriter:
    """Incrementally writes a JSON array to a file, one record at a time.

    Writes to <target>.tmp first; on close(), optionally BLAKE2b-compares
    with the existing file (--compare-json) and renames or discards accordingly.
    On exception, discard() deletes the tmp file and leaves the original intact.
    """

    def __init__(
        self,
        path: Path,
        *,
        compare_json: bool = False,
        files_in_export_dir: "set[Path] | None" = None,
    ) -> None:
        self._path = path.resolve()
        self._tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        self._compare_json = compare_json
        self._files_in_export_dir: set[Path] = (
            files_in_export_dir if files_in_export_dir is not None else set()
        )
        self._file = None
        self._first = True

    def open(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._tmp_path.open("w", encoding="utf-8")
        self._file.write("[")
        self._first = True

    def write_record(self, record: dict) -> None:
        if not self._first:
            self._file.write(",\n")
        else:
            self._first = False
        self._file.write(
            json.dumps(record, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False),
        )

    def write_batch(self, records: list[dict]) -> None:
        for record in records:
            self.write_record(record)

    def close(self) -> None:
        if self._file is None:
            return
        self._file.write("\n]")
        self._file.close()
        self._file = None
        self._finalize()

    def discard(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
        if self._tmp_path.exists():
            self._tmp_path.unlink()

    def _finalize(self) -> None:
        """Compare with existing file (if --compare-json) then rename or discard tmp."""
        if self._path in self._files_in_export_dir:
            self._files_in_export_dir.remove(self._path)
            if self._compare_json:
                existing_hash = hashlib.blake2b(self._path.read_bytes()).hexdigest()
                new_hash = hashlib.blake2b(self._tmp_path.read_bytes()).hexdigest()
                if existing_hash == new_hash:
                    self._tmp_path.unlink()
                    return
        self._tmp_path.rename(self._path)

    def __enter__(self) -> "StreamingManifestWriter":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.discard()
        else:
            self.close()


class Command(CryptMixin, PaperlessCommand):
    help = (
        "Decrypt and rename all files in our collection into a given target "
        "directory.  And include a manifest file containing document data for "
        "easy import."
    )

    supports_progress_bar = True
    supports_multiprocessing = False

    def add_arguments(self, parser) -> None:
        super().add_arguments(parser)
        parser.add_argument("target")

        parser.add_argument(
            "-c",
            "--compare-checksums",
            default=False,
            action="store_true",
            help=(
                "Compare file checksums when determining whether to export "
                "a file or not. If not specified, file size and time "
                "modified is used instead."
            ),
        )

        parser.add_argument(
            "-cj",
            "--compare-json",
            default=False,
            action="store_true",
            help=(
                "Compare json file checksums when determining whether to "
                "export a json file or not (manifest or metadata). "
                "If not specified, the file is always exported."
            ),
        )

        parser.add_argument(
            "-d",
            "--delete",
            default=False,
            action="store_true",
            help=(
                "After exporting, delete files in the export directory that "
                "do not belong to the current export, such as files from "
                "deleted documents."
            ),
        )

        parser.add_argument(
            "-f",
            "--use-filename-format",
            default=False,
            action="store_true",
            help=(
                "Use PAPERLESS_FILENAME_FORMAT for storing files in the "
                "export directory, if configured."
            ),
        )

        parser.add_argument(
            "-na",
            "--no-archive",
            default=False,
            action="store_true",
            help="Avoid exporting archive files",
        )

        parser.add_argument(
            "-nt",
            "--no-thumbnail",
            default=False,
            action="store_true",
            help="Avoid exporting thumbnail files",
        )

        parser.add_argument(
            "-p",
            "--use-folder-prefix",
            default=False,
            action="store_true",
            help=(
                "Export files in dedicated folders according to their nature: "
                "archive, originals or thumbnails"
            ),
        )

        parser.add_argument(
            "-sm",
            "--split-manifest",
            default=False,
            action="store_true",
            help="Export document information in individual manifest json files.",
        )

        parser.add_argument(
            "-z",
            "--zip",
            default=False,
            action="store_true",
            help="Export the documents to a zip file in the given directory",
        )

        parser.add_argument(
            "-zn",
            "--zip-name",
            default=f"export-{timezone.localdate().isoformat()}",
            help="Sets the export zip file name",
        )

        parser.add_argument(
            "--data-only",
            default=False,
            action="store_true",
            help="If set, only the database will be imported, not files",
        )

        parser.add_argument(
            "--passphrase",
            help="If provided, is used to encrypt sensitive data in the export",
        )

        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help=(
                "Number of records to process per batch during serialization. "
                "Lower values reduce peak memory usage; higher values improve "
                "throughput. Default: 500."
            ),
        )

    def handle(self, *args, **options) -> None:
        self.target = Path(options["target"]).resolve()
        self.split_manifest: bool = options["split_manifest"]
        self.compare_checksums: bool = options["compare_checksums"]
        self.compare_json: bool = options["compare_json"]
        self.use_filename_format: bool = options["use_filename_format"]
        self.use_folder_prefix: bool = options["use_folder_prefix"]
        self.delete: bool = options["delete"]
        self.no_archive: bool = options["no_archive"]
        self.no_thumbnail: bool = options["no_thumbnail"]
        self.zip_export: bool = options["zip"]
        self.data_only: bool = options["data_only"]
        self.passphrase: str | None = options.get("passphrase")
        self.batch_size: int = options["batch_size"]

        self.files_in_export_dir: set[Path] = set()
        self.exported_files: set[str] = set()

        # If zipping, save the original target for later and
        # get a temporary directory for the target instead
        temp_dir = None
        self.original_target = self.target
        if self.zip_export:
            settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
            temp_dir = tempfile.TemporaryDirectory(
                dir=settings.SCRATCH_DIR,
                prefix="paperless-export",
            )
            self.target = Path(temp_dir.name).resolve()

        if not self.target.exists():
            raise CommandError("That path doesn't exist")

        if not self.target.is_dir():
            raise CommandError("That path isn't a directory")

        if not os.access(self.target, os.W_OK):
            raise CommandError("That path doesn't appear to be writable")

        try:
            # Prevent any ongoing changes in the documents
            with FileLock(settings.MEDIA_LOCK):
                self.dump()

                # We've written everything to the temporary directory in this case,
                # now make an archive in the original target, with all files stored
                if self.zip_export and temp_dir is not None:
                    shutil.make_archive(
                        self.original_target / options["zip_name"],
                        format="zip",
                        root_dir=temp_dir.name,
                    )

        finally:
            # Always cleanup the temporary directory, if one was created
            if self.zip_export and temp_dir is not None:
                temp_dir.cleanup()

    def dump(self) -> None:
        # 1. Take a snapshot of what files exist in the current export folder
        for x in self.target.glob("**/*"):
            if x.is_file():
                self.files_in_export_dir.add(x.resolve())

        # 2. Create manifest, containing all correspondents, types, tags, storage paths
        # note, documents and ui_settings
        _excluded_usernames = ["consumer", "AnonymousUser"]
        manifest_key_to_object_query: dict[str, QuerySet[Any]] = {
            "correspondents": Correspondent.objects.all(),
            "tags": Tag.objects.all(),
            "document_types": DocumentType.objects.all(),
            "storage_paths": StoragePath.objects.all(),
            "mail_accounts": MailAccount.objects.all(),
            "mail_rules": MailRule.objects.all(),
            "saved_views": SavedView.objects.all(),
            "saved_view_filter_rules": SavedViewFilterRule.objects.all(),
            "groups": Group.objects.all(),
            "users": User.objects.exclude(
                username__in=_excluded_usernames,
            ).all(),
            "ui_settings": UiSettings.objects.exclude(
                user__username__in=_excluded_usernames,
            ),
            "content_types": ContentType.objects.all(),
            "permissions": Permission.objects.all(),
            "user_object_permissions": UserObjectPermission.objects.exclude(
                user__username__in=_excluded_usernames,
            ),
            "group_object_permissions": GroupObjectPermission.objects.all(),
            "workflow_triggers": WorkflowTrigger.objects.all(),
            "workflow_actions": WorkflowAction.objects.all(),
            "workflow_email_actions": WorkflowActionEmail.objects.all(),
            "workflow_webhook_actions": WorkflowActionWebhook.objects.all(),
            "workflows": Workflow.objects.all(),
            "custom_fields": CustomField.objects.all(),
            "custom_field_instances": CustomFieldInstance.global_objects.all(),
            "app_configs": ApplicationConfiguration.objects.all(),
            "notes": Note.global_objects.all(),
            "documents": Document.global_objects.order_by("id").all(),
            "share_links": ShareLink.global_objects.all(),
            "share_link_bundles": ShareLinkBundle.objects.order_by("id").all(),
            "social_accounts": SocialAccount.objects.exclude(
                user__username__in=_excluded_usernames,
            ),
            "social_apps": SocialApp.objects.all(),
            "social_tokens": SocialToken.objects.exclude(
                account__user__username__in=_excluded_usernames,
            ),
            "authenticators": Authenticator.objects.exclude(
                user__username__in=_excluded_usernames,
            ),
        }

        if settings.AUDIT_LOG_ENABLED:
            manifest_key_to_object_query["log_entries"] = LogEntry.objects.all()

        # Crypto setup before streaming begins
        if self.passphrase:
            self.setup_crypto(passphrase=self.passphrase)
        elif MailAccount.objects.count() > 0 or SocialToken.objects.count() > 0:
            self.stdout.write(
                self.style.NOTICE(
                    "No passphrase was given, sensitive fields will be in plaintext",
                ),
            )

        document_manifest: list[dict] = []
        share_link_bundle_manifest: list[dict] = []
        manifest_path = (self.target / "manifest.json").resolve()

        with StreamingManifestWriter(
            manifest_path,
            compare_json=self.compare_json,
            files_in_export_dir=self.files_in_export_dir,
        ) as writer:
            with transaction.atomic():
                for key, qs in manifest_key_to_object_query.items():
                    if key == "documents":
                        # Accumulate for file-copy loop; written to manifest after
                        for batch in serialize_queryset_batched(
                            qs,
                            batch_size=self.batch_size,
                        ):
                            for record in batch:
                                self._encrypt_record_inline(record)
                            document_manifest.extend(batch)
                    elif key == "share_link_bundles":
                        # Accumulate for file-copy loop; written to manifest after
                        for batch in serialize_queryset_batched(
                            qs,
                            batch_size=self.batch_size,
                        ):
                            for record in batch:
                                self._encrypt_record_inline(record)
                            share_link_bundle_manifest.extend(batch)
                    elif self.split_manifest and key in (
                        "notes",
                        "custom_field_instances",
                    ):
                        # Written per-document in _write_split_manifest
                        pass
                    else:
                        for batch in serialize_queryset_batched(
                            qs,
                            batch_size=self.batch_size,
                        ):
                            for record in batch:
                                self._encrypt_record_inline(record)
                            writer.write_batch(batch)

            document_map: dict[int, Document] = {
                d.pk: d for d in Document.global_objects.order_by("id")
            }
            share_link_bundle_map: dict[int, ShareLinkBundle] = {
                b.pk: b
                for b in ShareLinkBundle.objects.order_by("id").prefetch_related(
                    "documents",
                )
            }

            # 3. Export files from each document
            for index, document_dict in enumerate(
                self.track(
                    document_manifest,
                    description="Exporting documents...",
                    total=len(document_manifest),
                ),
            ):
                document = document_map[document_dict["pk"]]

                # 3.1. generate a unique filename
                base_name = self.generate_base_name(document)

                # 3.2. write filenames into manifest
                original_target, thumbnail_target, archive_target = (
                    self.generate_document_targets(document, base_name, document_dict)
                )

                # 3.3. write files to target folder
                if not self.data_only:
                    self.copy_document_files(
                        document,
                        original_target,
                        thumbnail_target,
                        archive_target,
                    )

                if self.split_manifest:
                    self._write_split_manifest(document_dict, document, base_name)
                else:
                    writer.write_record(document_dict)

            for bundle_dict in share_link_bundle_manifest:
                bundle = share_link_bundle_map[bundle_dict["pk"]]

                bundle_target = self.generate_share_link_bundle_target(
                    bundle,
                    bundle_dict,
                )

                if not self.data_only and bundle_target is not None:
                    self.copy_share_link_bundle_file(bundle, bundle_target)

                writer.write_record(bundle_dict)

        # 4.2 write version information to target folder
        extra_metadata_path = (self.target / "metadata.json").resolve()
        metadata: dict[str, str | int | dict[str, str | int]] = {
            "version": version.__full_version_str__,
        }

        # 4.2.1 If needed, write the crypto values into the metadata
        # Django stores most of these in the field itself, we store them once here
        if self.passphrase:
            metadata.update(self.get_crypt_params())

        self.check_and_write_json(
            metadata,
            extra_metadata_path,
        )

        if self.delete:
            # 5. Remove files which we did not explicitly export in this run
            if not self.zip_export:
                for f in self.files_in_export_dir:
                    f.unlink()

                    delete_empty_directories(
                        f.parent,
                        self.target,
                    )
            else:
                # 5. Remove anything in the original location (before moving the zip)
                for item in self.original_target.glob("*"):
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()

    def generate_base_name(self, document: Document) -> Path:
        """
        Generates a unique name for the document, one which hasn't already been exported (or will be)
        """
        filename_counter = 0
        while True:
            if self.use_filename_format:
                base_name = generate_filename(
                    document,
                    counter=filename_counter,
                )
            else:
                base_name = document.get_public_filename(counter=filename_counter)

            if base_name not in self.exported_files:
                self.exported_files.add(base_name)
                break
            else:
                filename_counter += 1
        return Path(base_name)

    def generate_document_targets(
        self,
        document: Document,
        base_name: Path,
        document_dict: dict,
    ) -> tuple[Path, Path | None, Path | None]:
        """
        Generates the targets for a given document, including the original file, archive file and thumbnail (depending on settings).
        """
        original_name = base_name
        if self.use_folder_prefix:
            original_name = Path("originals") / original_name
        original_target = (self.target / original_name).resolve()
        document_dict[EXPORTER_FILE_NAME] = str(original_name)

        if not self.no_thumbnail:
            thumbnail_name = base_name.parent / (base_name.stem + "-thumbnail.webp")
            if self.use_folder_prefix:
                thumbnail_name = Path("thumbnails") / thumbnail_name
            thumbnail_target = (self.target / thumbnail_name).resolve()
            document_dict[EXPORTER_THUMBNAIL_NAME] = str(thumbnail_name)
        else:
            thumbnail_target = None

        if not self.no_archive and document.has_archive_version:
            archive_name = base_name.parent / (base_name.stem + "-archive.pdf")
            if self.use_folder_prefix:
                archive_name = Path("archive") / archive_name
            archive_target = (self.target / archive_name).resolve()
            document_dict[EXPORTER_ARCHIVE_NAME] = str(archive_name)
        else:
            archive_target = None

        return original_target, thumbnail_target, archive_target

    def copy_document_files(
        self,
        document: Document,
        original_target: Path,
        thumbnail_target: Path | None,
        archive_target: Path | None,
    ) -> None:
        """
        Copies files from the document storage location to the specified target location.

        If the document is encrypted, the files are decrypted before copying them to the target location.
        """
        self.check_and_copy(
            document.source_path,
            document.checksum,
            original_target,
        )

        if thumbnail_target:
            self.check_and_copy(document.thumbnail_path, None, thumbnail_target)

        if archive_target:
            if TYPE_CHECKING:
                assert isinstance(document.archive_path, Path)
            self.check_and_copy(
                document.archive_path,
                document.archive_checksum,
                archive_target,
            )

    def generate_share_link_bundle_target(
        self,
        bundle: ShareLinkBundle,
        bundle_dict: dict,
    ) -> Path | None:
        """
        Generates the export target for a share link bundle file, when present.
        """
        if not bundle.file_path:
            return None

        stored_bundle_path = Path(bundle.file_path)
        portable_bundle_path = (
            stored_bundle_path
            if not stored_bundle_path.is_absolute()
            else Path(stored_bundle_path.name)
        )
        export_bundle_path = Path("share_link_bundles") / portable_bundle_path

        bundle_dict["fields"]["file_path"] = portable_bundle_path.as_posix()
        bundle_dict[EXPORTER_SHARE_LINK_BUNDLE_NAME] = export_bundle_path.as_posix()

        return (self.target / export_bundle_path).resolve()

    def copy_share_link_bundle_file(
        self,
        bundle: ShareLinkBundle,
        bundle_target: Path,
    ) -> None:
        """
        Copies a share link bundle ZIP into the export directory.
        """
        bundle_source_path = bundle.absolute_file_path
        if bundle_source_path is None:
            raise FileNotFoundError(f"Share link bundle {bundle.pk} has no file path")

        self.check_and_copy(
            bundle_source_path,
            None,
            bundle_target,
        )

    def _encrypt_record_inline(self, record: dict) -> None:
        """Encrypt sensitive fields in a single record, if passphrase is set."""
        if not self.passphrase:
            return
        fields = self.CRYPT_FIELDS_BY_MODEL.get(record.get("model", ""))
        if fields:
            for field in fields:
                if record["fields"].get(field):
                    record["fields"][field] = self.encrypt_string(
                        value=record["fields"][field],
                    )

    def _write_split_manifest(
        self,
        document_dict: dict,
        document: Document,
        base_name: Path,
    ) -> None:
        """Write per-document manifest file for --split-manifest mode."""
        content = [document_dict]
        content.extend(
            serializers.serialize(
                "python",
                Note.global_objects.filter(document=document),
            ),
        )
        content.extend(
            serializers.serialize(
                "python",
                CustomFieldInstance.global_objects.filter(document=document),
            ),
        )
        manifest_name = base_name.with_name(f"{base_name.stem}-manifest.json")
        if self.use_folder_prefix:
            manifest_name = Path("json") / manifest_name
        manifest_name = (self.target / manifest_name).resolve()
        manifest_name.parent.mkdir(parents=True, exist_ok=True)
        self.check_and_write_json(content, manifest_name)

    def check_and_write_json(
        self,
        content: list[dict] | dict,
        target: Path,
    ) -> None:
        """
        Writes the source content to the target json file.
        If --compare-json arg was used, don't write to target file if
        the file exists and checksum is identical to content checksum.
        This preserves the file timestamps when no changes are made.
        """

        target = target.resolve()
        perform_write = True
        if target in self.files_in_export_dir:
            self.files_in_export_dir.remove(target)
            if self.compare_json:
                target_checksum = hashlib.blake2b(target.read_bytes()).hexdigest()
                src_str = json.dumps(
                    content,
                    cls=DjangoJSONEncoder,
                    indent=2,
                    ensure_ascii=False,
                )
                src_checksum = hashlib.blake2b(src_str.encode("utf-8")).hexdigest()
                if src_checksum == target_checksum:
                    perform_write = False

        if perform_write:
            target.write_text(
                json.dumps(
                    content,
                    cls=DjangoJSONEncoder,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

    def check_and_copy(
        self,
        source: Path,
        source_checksum: str | None,
        target: Path,
    ) -> None:
        """
        Copies the source to the target, if target doesn't exist or the target doesn't seem to match
        the source attributes
        """

        target = target.resolve()
        if target in self.files_in_export_dir:
            self.files_in_export_dir.remove(target)

        perform_copy = False

        if target.exists():
            source_stat = source.stat()
            target_stat = target.stat()
            if self.compare_checksums and source_checksum:
                target_checksum = compute_checksum(target)
                perform_copy = target_checksum != source_checksum
            elif (
                source_stat.st_mtime != target_stat.st_mtime
                or source_stat.st_size != target_stat.st_size
            ):
                perform_copy = True
        else:
            # Copy if it does not exist
            perform_copy = True

        if perform_copy:
            target.parent.mkdir(parents=True, exist_ok=True)
            copy_file_with_basic_stats(source, target)
