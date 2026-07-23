import os
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

from documents.export.sinks import DirectoryExportSink
from documents.export.sinks import StreamingManifestWriter
from documents.export.sinks import ZipExportSink
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

        self.exported_files: set[str] = set()

        if self.zip_export and (self.compare_checksums or self.compare_json):
            raise CommandError(
                "--compare-checksums and --compare-json have no effect when "
                "used with --zip",
            )

        if not self.target.exists():
            raise CommandError("That path doesn't exist")

        if not self.target.is_dir():
            raise CommandError("That path isn't a directory")

        if not os.access(self.target, os.W_OK):
            raise CommandError("That path doesn't appear to be writable")

        sink: DirectoryExportSink | ZipExportSink
        if self.zip_export:
            sink = ZipExportSink(
                self.target,
                options["zip_name"],
                delete=self.delete,
            )
        else:
            sink = DirectoryExportSink(
                self.target,
                compare_checksums=self.compare_checksums,
                compare_json=self.compare_json,
                delete=self.delete,
            )

        # Prevent any ongoing changes in the documents while exporting
        with FileLock(settings.MEDIA_LOCK), sink:
            self.dump(sink)

    def dump(self, sink: DirectoryExportSink | ZipExportSink) -> None:
        # 1. Create manifest, containing all correspondents, types, tags, storage
        #    paths, note, documents and ui_settings
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

        with sink.stream("manifest.json") as handle:
            writer = StreamingManifestWriter(handle)
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

            # 2. Export files from each document
            for document_dict in self.track(
                document_manifest,
                description="Exporting documents...",
                total=len(document_manifest),
            ):
                document = document_map[document_dict["pk"]]

                # generate a unique filename, then the arcnames for its files
                base_name = self.generate_base_name(document)
                original_arc, thumbnail_arc, archive_arc = (
                    self.generate_document_targets(document, base_name, document_dict)
                )

                if not self.data_only:
                    self.copy_document_files(
                        document,
                        sink,
                        original_arc,
                        thumbnail_arc,
                        archive_arc,
                    )

                if self.split_manifest:
                    self._write_split_manifest(sink, document_dict, document, base_name)
                else:
                    writer.write_record(document_dict)

            for bundle_dict in share_link_bundle_manifest:
                bundle = share_link_bundle_map[bundle_dict["pk"]]
                bundle_arc = self.generate_share_link_bundle_target(
                    bundle,
                    bundle_dict,
                )
                if not self.data_only and bundle_arc is not None:
                    self.copy_share_link_bundle_file(bundle, sink, bundle_arc)
                writer.write_record(bundle_dict)

            writer.close()

        # 3. Write version (and crypto params) to metadata.json
        # Django stores most crypto values in the field itself; we store
        # them once here for the whole export
        metadata: dict[str, str | int | dict[str, str | int]] = {
            "version": version.__full_version_str__,
        }
        if self.passphrase:
            metadata.update(self.get_crypt_params())
        sink.add_json(metadata, "metadata.json")

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
    ) -> tuple[str, str | None, str | None]:
        """
        Generates the relative POSIX arcnames for a document's original, thumbnail
        and archive files (depending on settings), and records them in the manifest.
        """
        original_name = base_name
        if self.use_folder_prefix:
            original_name = Path("originals") / original_name
        original_arc = original_name.as_posix()
        document_dict[EXPORTER_FILE_NAME] = original_arc

        if not self.no_thumbnail:
            thumbnail_name = base_name.parent / (base_name.stem + "-thumbnail.webp")
            if self.use_folder_prefix:
                thumbnail_name = Path("thumbnails") / thumbnail_name
            thumbnail_arc = thumbnail_name.as_posix()
            document_dict[EXPORTER_THUMBNAIL_NAME] = thumbnail_arc
        else:
            thumbnail_arc = None

        if not self.no_archive and document.has_archive_version:
            archive_name = base_name.parent / (base_name.stem + "-archive.pdf")
            if self.use_folder_prefix:
                archive_name = Path("archive") / archive_name
            archive_arc = archive_name.as_posix()
            document_dict[EXPORTER_ARCHIVE_NAME] = archive_arc
        else:
            archive_arc = None

        return original_arc, thumbnail_arc, archive_arc

    def copy_document_files(
        self,
        document: Document,
        sink: DirectoryExportSink | ZipExportSink,
        original_arc: str,
        thumbnail_arc: str | None,
        archive_arc: str | None,
    ) -> None:
        """
        Hands the document's files to the sink (original, thumbnail, archive).
        """
        sink.add_file(document.source_path, original_arc, checksum=document.checksum)

        if thumbnail_arc:
            sink.add_file(document.thumbnail_path, thumbnail_arc)

        if archive_arc:
            if TYPE_CHECKING:
                assert isinstance(document.archive_path, Path)
            sink.add_file(
                document.archive_path,
                archive_arc,
                checksum=document.archive_checksum,
            )

    def generate_share_link_bundle_target(
        self,
        bundle: ShareLinkBundle,
        bundle_dict: dict,
    ) -> str | None:
        """
        Generates the relative POSIX arcname for a share link bundle file, if any.
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

        return export_bundle_path.as_posix()

    def copy_share_link_bundle_file(
        self,
        bundle: ShareLinkBundle,
        sink: DirectoryExportSink | ZipExportSink,
        bundle_arc: str,
    ) -> None:
        """
        Hands a share link bundle ZIP to the sink.
        """
        bundle_source_path = bundle.absolute_file_path
        if bundle_source_path is None:
            raise FileNotFoundError(f"Share link bundle {bundle.pk} has no file path")

        sink.add_file(bundle_source_path, bundle_arc)

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
        sink: DirectoryExportSink | ZipExportSink,
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
        sink.add_json(content, manifest_name.as_posix())
