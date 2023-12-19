import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import tqdm
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone
from filelock import FileLock
from guardian.models import GroupObjectPermission
from guardian.models import UserObjectPermission

from documents.file_handling import delete_empty_directories
from documents.file_handling import generate_filename
from documents.models import ConsumptionTemplate
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import SavedView
from documents.models import SavedViewFilterRule
from documents.models import StoragePath
from documents.models import Tag
from documents.models import UiSettings
from documents.settings import EXPORTER_ARCHIVE_NAME
from documents.settings import EXPORTER_FILE_NAME
from documents.settings import EXPORTER_THUMBNAIL_NAME
from documents.utils import copy_file_with_basic_stats
from paperless import version
from paperless.db import GnuPG
from paperless.models import ApplicationConfiguration
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


class Command(BaseCommand):
    help = (
        "Decrypt and rename all files in our collection into a given target "
        "directory.  And include a manifest file containing document data for "
        "easy import."
    )

    def add_arguments(self, parser):
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
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown",
        )

    def __init__(self, *args, **kwargs):
        BaseCommand.__init__(self, *args, **kwargs)
        self.target: Path = None
        self.split_manifest = False
        self.files_in_export_dir: set[Path] = set()
        self.exported_files: list[Path] = []
        self.compare_checksums = False
        self.use_filename_format = False
        self.use_folder_prefix = False
        self.delete = False
        self.no_archive = False
        self.no_thumbnail = False

    def handle(self, *args, **options):
        self.target = Path(options["target"]).resolve()
        self.split_manifest: bool = options["split_manifest"]
        self.compare_checksums: bool = options["compare_checksums"]
        self.use_filename_format: bool = options["use_filename_format"]
        self.use_folder_prefix: bool = options["use_folder_prefix"]
        self.delete: bool = options["delete"]
        self.no_archive: bool = options["no_archive"]
        self.no_thumbnail: bool = options["no_thumbnail"]
        zip_export: bool = options["zip"]

        # If zipping, save the original target for later and
        # get a temporary directory for the target instead
        temp_dir = None
        original_target = None
        if zip_export:
            original_target = self.target

            os.makedirs(settings.SCRATCH_DIR, exist_ok=True)
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
            with FileLock(settings.MEDIA_LOCK):
                self.dump(options["no_progress_bar"])

                # We've written everything to the temporary directory in this case,
                # now make an archive in the original target, with all files stored
                if zip_export:
                    shutil.make_archive(
                        os.path.join(
                            original_target,
                            options["zip_name"],
                        ),
                        format="zip",
                        root_dir=temp_dir.name,
                    )

        finally:
            # Always cleanup the temporary directory, if one was created
            if zip_export and temp_dir is not None:
                temp_dir.cleanup()

    def dump(self, progress_bar_disable=False):
        # 1. Take a snapshot of what files exist in the current export folder
        for x in self.target.glob("**/*"):
            if x.is_file():
                self.files_in_export_dir.add(x.resolve())

        # 2. Create manifest, containing all correspondents, types, tags, storage paths
        # note, documents and ui_settings
        with transaction.atomic():
            manifest = json.loads(
                serializers.serialize("json", Correspondent.objects.all()),
            )

            manifest += json.loads(serializers.serialize("json", Tag.objects.all()))

            manifest += json.loads(
                serializers.serialize("json", DocumentType.objects.all()),
            )

            manifest += json.loads(
                serializers.serialize("json", StoragePath.objects.all()),
            )

            manifest += json.loads(
                serializers.serialize("json", MailAccount.objects.all()),
            )

            manifest += json.loads(
                serializers.serialize("json", MailRule.objects.all()),
            )

            manifest += json.loads(
                serializers.serialize("json", SavedView.objects.all()),
            )

            manifest += json.loads(
                serializers.serialize("json", SavedViewFilterRule.objects.all()),
            )

            manifest += json.loads(serializers.serialize("json", Group.objects.all()))

            manifest += json.loads(
                serializers.serialize(
                    "json",
                    User.objects.exclude(username__in=["consumer", "AnonymousUser"]),
                ),
            )

            manifest += json.loads(
                serializers.serialize("json", UiSettings.objects.all()),
            )

            manifest += json.loads(
                serializers.serialize("json", ContentType.objects.all()),
            )

            manifest += json.loads(
                serializers.serialize("json", Permission.objects.all()),
            )

            manifest += json.loads(
                serializers.serialize("json", UserObjectPermission.objects.all()),
            )

            manifest += json.loads(
                serializers.serialize("json", GroupObjectPermission.objects.all()),
            )

            manifest += json.loads(
                serializers.serialize("json", ConsumptionTemplate.objects.all()),
            )

            manifest += json.loads(
                serializers.serialize("json", CustomField.objects.all()),
            )

            manifest += json.loads(
                serializers.serialize("json", ApplicationConfiguration.objects.all()),
            )

            # These are treated specially and included in the per-document manifest
            # if that setting is enabled.  Otherwise, they are just exported to the bulk
            # manifest
            documents = Document.objects.order_by("id")
            document_map: dict[int, Document] = {d.pk: d for d in documents}
            document_manifest = json.loads(serializers.serialize("json", documents))

            notes = json.loads(
                serializers.serialize("json", Note.objects.all()),
            )

            custom_field_instances = json.loads(
                serializers.serialize("json", CustomFieldInstance.objects.all()),
            )
            if not self.split_manifest:
                manifest += document_manifest
                manifest += notes
                manifest += custom_field_instances

        # 3. Export files from each document
        for index, document_dict in tqdm.tqdm(
            enumerate(document_manifest),
            total=len(document_manifest),
            disable=progress_bar_disable,
        ):
            # 3.1. store files unencrypted
            document_dict["fields"]["storage_type"] = Document.STORAGE_TYPE_UNENCRYPTED

            document = document_map[document_dict["pk"]]

            # 3.2. generate a unique filename
            filename_counter = 0
            while True:
                if self.use_filename_format:
                    base_name = generate_filename(
                        document,
                        counter=filename_counter,
                        append_gpg=False,
                    )
                else:
                    base_name = document.get_public_filename(counter=filename_counter)

                if base_name not in self.exported_files:
                    self.exported_files.append(base_name)
                    break
                else:
                    filename_counter += 1

            # 3.3. write filenames into manifest
            original_name = base_name
            if self.use_folder_prefix:
                original_name = os.path.join("originals", original_name)
            original_target = (self.target / Path(original_name)).resolve()
            document_dict[EXPORTER_FILE_NAME] = original_name

            if not self.no_thumbnail:
                thumbnail_name = base_name + "-thumbnail.webp"
                if self.use_folder_prefix:
                    thumbnail_name = os.path.join("thumbnails", thumbnail_name)
                thumbnail_target = (self.target / Path(thumbnail_name)).resolve()
                document_dict[EXPORTER_THUMBNAIL_NAME] = thumbnail_name
            else:
                thumbnail_target = None

            if not self.no_archive and document.has_archive_version:
                archive_name = base_name + "-archive.pdf"
                if self.use_folder_prefix:
                    archive_name = os.path.join("archive", archive_name)
                archive_target = (self.target / Path(archive_name)).resolve()
                document_dict[EXPORTER_ARCHIVE_NAME] = archive_name
            else:
                archive_target = None

            # 3.4. write files to target folder
            if document.storage_type == Document.STORAGE_TYPE_GPG:
                t = int(time.mktime(document.created.timetuple()))

                original_target.parent.mkdir(parents=True, exist_ok=True)
                with document.source_file as out_file:
                    original_target.write_bytes(GnuPG.decrypted(out_file))
                    os.utime(original_target, times=(t, t))

                if thumbnail_target:
                    thumbnail_target.parent.mkdir(parents=True, exist_ok=True)
                    with document.thumbnail_file as out_file:
                        thumbnail_target.write_bytes(GnuPG.decrypted(out_file))
                        os.utime(thumbnail_target, times=(t, t))

                if archive_target:
                    archive_target.parent.mkdir(parents=True, exist_ok=True)
                    with document.archive_path as out_file:
                        archive_target.write_bytes(GnuPG.decrypted(out_file))
                        os.utime(archive_target, times=(t, t))
            else:
                self.check_and_copy(
                    document.source_path,
                    document.checksum,
                    original_target,
                )

                if thumbnail_target:
                    self.check_and_copy(document.thumbnail_path, None, thumbnail_target)

                if archive_target:
                    self.check_and_copy(
                        document.archive_path,
                        document.archive_checksum,
                        archive_target,
                    )

            if self.split_manifest:
                manifest_name = base_name + "-manifest.json"
                if self.use_folder_prefix:
                    manifest_name = os.path.join("json", manifest_name)
                manifest_name = (self.target / Path(manifest_name)).resolve()
                manifest_name.parent.mkdir(parents=True, exist_ok=True)
                content = [document_manifest[index]]
                content += list(
                    filter(
                        lambda d: d["fields"]["document"] == document_dict["pk"],
                        notes,
                    ),
                )
                content += list(
                    filter(
                        lambda d: d["fields"]["document"] == document_dict["pk"],
                        custom_field_instances,
                    ),
                )
                manifest_name.write_text(
                    json.dumps(content, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                if manifest_name in self.files_in_export_dir:
                    self.files_in_export_dir.remove(manifest_name)

        # 4.1 write manifest to target folder
        manifest_path = (self.target / Path("manifest.json")).resolve()
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if manifest_path in self.files_in_export_dir:
            self.files_in_export_dir.remove(manifest_path)

        # 4.2 write version information to target folder
        version_path = (self.target / Path("version.json")).resolve()
        version_path.write_text(
            json.dumps(
                {"version": version.__full_version_str__},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        if version_path in self.files_in_export_dir:
            self.files_in_export_dir.remove(version_path)

        if self.delete:
            # 5. Remove files which we did not explicitly export in this run

            for f in self.files_in_export_dir:
                f.unlink()

                delete_empty_directories(
                    f.parent,
                    self.target,
                )

    def check_and_copy(self, source, source_checksum, target: Path):
        if target in self.files_in_export_dir:
            self.files_in_export_dir.remove(target)

        perform_copy = False

        if target.exists():
            source_stat = os.stat(source)
            target_stat = target.stat()
            if self.compare_checksums and source_checksum:
                target_checksum = hashlib.md5(target.read_bytes()).hexdigest()
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
