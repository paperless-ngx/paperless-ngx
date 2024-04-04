import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path

import tqdm
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.core.serializers.base import DeserializationError
from django.db import IntegrityError
from django.db import transaction
from django.db.models.signals import m2m_changed
from django.db.models.signals import post_save
from filelock import FileLock

from documents.file_handling import create_source_path_directory
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import Tag
from documents.parsers import run_convert
from documents.settings import EXPORTER_ARCHIVE_NAME
from documents.settings import EXPORTER_FILE_NAME
from documents.settings import EXPORTER_THUMBNAIL_NAME
from documents.signals.handlers import update_filename_and_move_files
from documents.utils import copy_file_with_basic_stats
from paperless import version

if settings.AUDIT_LOG_ENABLED:
    from auditlog.registry import auditlog


@contextmanager
def disable_signal(sig, receiver, sender):
    try:
        sig.disconnect(receiver=receiver, sender=sender)
        yield
    finally:
        sig.connect(receiver=receiver, sender=sender)


class Command(BaseCommand):
    help = (
        "Using a manifest.json file, load the data from there, and import the "
        "documents it refers to."
    )

    def add_arguments(self, parser):
        parser.add_argument("source")
        parser.add_argument(
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown",
        )

    def __init__(self, *args, **kwargs):
        BaseCommand.__init__(self, *args, **kwargs)
        self.source = None
        self.manifest = None
        self.version = None

    def pre_check(self) -> None:
        """
        Runs some initial checks against the source directory, including looking for
        common mistakes like having files still and users other than expected
        """

        if not self.source.exists():
            raise CommandError("That path doesn't exist")

        if not os.access(self.source, os.R_OK):
            raise CommandError("That path doesn't appear to be readable")

        for document_dir in [settings.ORIGINALS_DIR, settings.ARCHIVE_DIR]:
            if document_dir.exists() and document_dir.is_dir():
                for entry in document_dir.glob("**/*"):
                    if entry.is_dir():
                        continue
                    self.stdout.write(
                        self.style.WARNING(
                            f"Found file {entry.relative_to(document_dir)}, this might indicate a non-empty installation",
                        ),
                    )
                    break
        if (
            User.objects.exclude(username__in=["consumer", "AnonymousUser"]).count()
            != 0
        ):
            self.stdout.write(
                self.style.WARNING(
                    "Found existing user(s), this might indicate a non-empty installation",
                ),
            )
        if Document.objects.count() != 0:
            self.stdout.write(
                self.style.WARNING(
                    "Found existing documents(s), this might indicate a non-empty installation",
                ),
            )

    def handle(self, *args, **options):
        logging.getLogger().handlers[0].level = logging.ERROR

        self.source = Path(options["source"]).resolve()

        self.pre_check()

        manifest_paths = []

        main_manifest_path = self.source / "manifest.json"

        self._check_manifest_exists(main_manifest_path)

        with main_manifest_path.open() as infile:
            self.manifest = json.load(infile)
        manifest_paths.append(main_manifest_path)

        for file in Path(self.source).glob("**/*-manifest.json"):
            with file.open() as infile:
                self.manifest += json.load(infile)
            manifest_paths.append(file)

        version_path = self.source / "version.json"
        if version_path.exists():
            with version_path.open() as infile:
                self.version = json.load(infile)["version"]
            # Provide an initial warning if needed to the user
            if self.version != version.__full_version_str__:
                self.stdout.write(
                    self.style.WARNING(
                        "Version mismatch: "
                        f"Currently {version.__full_version_str__},"
                        f" importing {self.version}."
                        " Continuing, but import may fail.",
                    ),
                )

        else:
            self.stdout.write(self.style.NOTICE("No version.json file located"))

        self._check_manifest_valid()

        with disable_signal(
            post_save,
            receiver=update_filename_and_move_files,
            sender=Document,
        ), disable_signal(
            m2m_changed,
            receiver=update_filename_and_move_files,
            sender=Document.tags.through,
        ):
            if settings.AUDIT_LOG_ENABLED:
                auditlog.unregister(Document)
                auditlog.unregister(Correspondent)
                auditlog.unregister(Tag)
                auditlog.unregister(DocumentType)
                auditlog.unregister(Note)
                auditlog.unregister(CustomField)
                auditlog.unregister(CustomFieldInstance)

            # Fill up the database with whatever is in the manifest
            try:
                with transaction.atomic():
                    # delete these since pk can change, re-created from import
                    ContentType.objects.all().delete()
                    Permission.objects.all().delete()
                    for manifest_path in manifest_paths:
                        call_command("loaddata", manifest_path)
            except (FieldDoesNotExist, DeserializationError, IntegrityError) as e:
                self.stdout.write(self.style.ERROR("Database import failed"))
                if (
                    self.version is not None
                    and self.version != version.__full_version_str__
                ):
                    self.stdout.write(
                        self.style.ERROR(
                            "Version mismatch: "
                            f"Currently {version.__full_version_str__},"
                            f" importing {self.version}",
                        ),
                    )
                    raise e
                else:
                    self.stdout.write(
                        self.style.ERROR("No version information present"),
                    )
                    raise e

            self._import_files_from_manifest(options["no_progress_bar"])

        self.stdout.write("Updating search index...")
        call_command(
            "document_index",
            "reindex",
            no_progress_bar=options["no_progress_bar"],
        )

    @staticmethod
    def _check_manifest_exists(path: Path):
        if not path.exists():
            raise CommandError(
                "That directory doesn't appear to contain a manifest.json file.",
            )

    def _check_manifest_valid(self):
        """
        Attempts to verify the manifest is valid.  Namely checking the files
        referred to exist and the files can be read from
        """
        self.stdout.write("Checking the manifest")
        for record in self.manifest:
            if record["model"] != "documents.document":
                continue

            if EXPORTER_FILE_NAME not in record:
                raise CommandError(
                    "The manifest file contains a record which does not "
                    "refer to an actual document file.",
                )

            doc_file = record[EXPORTER_FILE_NAME]
            doc_path = self.source / doc_file
            if not doc_path.exists():
                raise CommandError(
                    f'The manifest file refers to "{doc_file}" which does not '
                    "appear to be in the source directory.",
                )
            try:
                with doc_path.open(mode="rb") as infile:
                    infile.read(1)
            except Exception as e:
                raise CommandError(
                    f"Failed to read from original file {doc_path}",
                ) from e

            if EXPORTER_ARCHIVE_NAME in record:
                archive_file = record[EXPORTER_ARCHIVE_NAME]
                doc_archive_path = self.source / archive_file
                if not doc_archive_path.exists():
                    raise CommandError(
                        f"The manifest file refers to {archive_file} which "
                        f"does not appear to be in the source directory.",
                    )
                try:
                    with doc_archive_path.open(mode="rb") as infile:
                        infile.read(1)
                except Exception as e:
                    raise CommandError(
                        f"Failed to read from archive file {doc_archive_path}",
                    ) from e

    def _import_files_from_manifest(self, progress_bar_disable):
        settings.ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
        settings.THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
        settings.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

        self.stdout.write("Copy files into paperless...")

        manifest_documents = list(
            filter(lambda r: r["model"] == "documents.document", self.manifest),
        )

        for record in tqdm.tqdm(manifest_documents, disable=progress_bar_disable):
            document = Document.objects.get(pk=record["pk"])

            doc_file = record[EXPORTER_FILE_NAME]
            document_path = os.path.join(self.source, doc_file)

            if EXPORTER_THUMBNAIL_NAME in record:
                thumb_file = record[EXPORTER_THUMBNAIL_NAME]
                thumbnail_path = Path(os.path.join(self.source, thumb_file)).resolve()
            else:
                thumbnail_path = None

            if EXPORTER_ARCHIVE_NAME in record:
                archive_file = record[EXPORTER_ARCHIVE_NAME]
                archive_path = os.path.join(self.source, archive_file)
            else:
                archive_path = None

            document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED

            with FileLock(settings.MEDIA_LOCK):
                if os.path.isfile(document.source_path):
                    raise FileExistsError(document.source_path)

                create_source_path_directory(document.source_path)

                copy_file_with_basic_stats(document_path, document.source_path)

                if thumbnail_path:
                    if thumbnail_path.suffix in {".png", ".PNG"}:
                        run_convert(
                            density=300,
                            scale="500x5000>",
                            alpha="remove",
                            strip=True,
                            trim=False,
                            auto_orient=True,
                            input_file=f"{thumbnail_path}[0]",
                            output_file=str(document.thumbnail_path),
                        )
                    else:
                        copy_file_with_basic_stats(
                            thumbnail_path,
                            document.thumbnail_path,
                        )

                if archive_path:
                    create_source_path_directory(document.archive_path)
                    # TODO: this assumes that the export is valid and
                    #  archive_filename is present on all documents with
                    #  archived files
                    copy_file_with_basic_stats(archive_path, document.archive_path)

            document.save()
