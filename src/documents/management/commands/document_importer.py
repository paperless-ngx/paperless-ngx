import json
import logging
import os
import tempfile
from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeAlias
from zipfile import ZipFile
from zipfile import is_zipfile

import ijson
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.management.color import no_style
from django.core.serializers.base import DeserializationError
from django.db import IntegrityError
from django.db import connection
from django.db import models as django_models
from django.db import transaction
from django.db.models import GeneratedField
from django.db.models import Model
from django.db.models.signals import m2m_changed
from django.db.models.signals import post_save
from filelock import FileLock

from documents.file_handling import create_source_path_directory
from documents.management.commands.base import PaperlessCommand
from documents.management.commands.mixins import CryptMixin
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import ShareLinkBundle
from documents.models import Tag
from documents.settings import EXPORTER_ARCHIVE_NAME
from documents.settings import EXPORTER_CRYPTO_SETTINGS_NAME
from documents.settings import EXPORTER_FILE_NAME
from documents.settings import EXPORTER_SHARE_LINK_BUNDLE_NAME
from documents.settings import EXPORTER_THUMBNAIL_NAME
from documents.signals.handlers import check_paths_and_prune_custom_fields
from documents.signals.handlers import update_filename_and_move_files
from documents.utils import copy_file_with_basic_stats
from paperless import version

if settings.AUDIT_LOG_ENABLED:
    from auditlog.registry import auditlog

# Maps M2M field names to the list of related PKs to apply after bulk_create.
M2MData: TypeAlias = dict[str, list[int]]


def iter_manifest_records(path: Path) -> Generator[dict, None, None]:
    """Yield records one at a time from a manifest JSON array via ijson."""
    try:
        with path.open("rb") as f:
            yield from ijson.items(f, "item")
    except ijson.JSONError as e:
        raise CommandError(f"Failed to parse manifest file {path}: {e}") from e


def _deserialize_record(
    record: dict,
) -> tuple[type[Model], Model, M2MData]:
    """
    Convert a single manifest record dict into a model instance and M2M data.

    Returns (Model class, unsaved instance, m2m_data) where m2m_data maps
    M2M field names to lists of integer PKs to be applied after the instance
    is saved via bulk_create.

    Raises DeserializationError for unknown models or bad field values.
    Raises FieldDoesNotExist for fields not present on the model.

    Note: CommandError from iter_manifest_records (malformed JSON mid-stream)
    propagates through the caller unchanged, it is not caught here.
    """
    model_label = record["model"]
    pk_value = record.get("pk")

    try:
        Model = apps.get_model(model_label)
    except (LookupError, TypeError) as e:
        raise DeserializationError(
            f"Invalid model identifier: {model_label}",
        ) from e

    data: dict = {}
    m2m_data: M2MData = {}

    try:
        data[Model._meta.pk.attname] = Model._meta.pk.to_python(pk_value)
    except Exception as e:
        raise DeserializationError(
            f"Could not coerce pk={pk_value} for {model_label}: {e}",
        ) from e

    for field_name, field_value in record.get("fields", {}).items():
        field = Model._meta.get_field(field_name)
        remote = field.remote_field

        if isinstance(remote, django_models.ManyToManyRel):
            # Collect M2M PKs; .set() is called after bulk_create in flush_model.
            target_pk = field.related_model._meta.pk
            m2m_data[field.name] = [
                target_pk.to_python(pk) for pk in (field_value or [])
            ]

        elif isinstance(remote, django_models.ManyToOneRel):
            # FK: store the integer PK on field.attname (e.g. correspondent_id)
            # to avoid triggering the descriptor and avoid an extra DB lookup.
            if field_value is None:
                data[field.attname] = None
            else:
                data[field.attname] = field.related_model._meta.pk.to_python(
                    field_value,
                )

        else:
            try:
                data[field.name] = field.to_python(field_value)
            except Exception as e:
                raise DeserializationError(
                    f"Could not coerce {field_name}={field_value!r} "
                    f"for {model_label}(pk={pk_value}): {e}",
                ) from e

    return Model, Model(**data), m2m_data


def _iter_document_copy_records(
    manifest_paths: list[Path],
) -> Generator[dict, None, None]:
    """Yield one lightweight dict per Document record without buffering all records."""
    for manifest_path in manifest_paths:
        for record in iter_manifest_records(manifest_path):
            if record["model"] == "documents.document":
                yield {
                    "pk": record["pk"],
                    EXPORTER_FILE_NAME: record[EXPORTER_FILE_NAME],
                    EXPORTER_THUMBNAIL_NAME: record.get(EXPORTER_THUMBNAIL_NAME),
                    EXPORTER_ARCHIVE_NAME: record.get(EXPORTER_ARCHIVE_NAME),
                }


def _iter_share_link_bundle_copy_records(
    manifest_paths: list[Path],
) -> Generator[dict, None, None]:
    """Yield one dict per ShareLinkBundle record that has a bundle file."""
    for manifest_path in manifest_paths:
        for record in iter_manifest_records(manifest_path):
            if record["model"] == "documents.sharelinkbundle" and record.get(
                EXPORTER_SHARE_LINK_BUNDLE_NAME,
            ):
                yield {
                    "pk": record["pk"],
                    EXPORTER_SHARE_LINK_BUNDLE_NAME: record[
                        EXPORTER_SHARE_LINK_BUNDLE_NAME
                    ],
                }


@contextmanager
def disable_signal(sig, receiver, sender, *, weak: bool | None = None) -> Generator:
    try:
        sig.disconnect(receiver=receiver, sender=sender)
        yield
    finally:
        kwargs = {"weak": weak} if weak is not None else {}
        sig.connect(receiver=receiver, sender=sender, **kwargs)


class Command(CryptMixin, PaperlessCommand):
    help = (
        "Using a manifest.json file, load the data from there, and import the "
        "documents it refers to."
    )

    supports_progress_bar = True
    supports_multiprocessing = False

    def add_arguments(self, parser) -> None:
        super().add_arguments(parser)
        parser.add_argument("source")

        parser.add_argument(
            "--data-only",
            default=False,
            action="store_true",
            help="If set, only the database will be exported, not files",
        )

        parser.add_argument(
            "--passphrase",
            help="If provided, is used to sensitive fields in the export",
        )

        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of records to insert per batch during database load. "
            "Lower values reduce peak memory usage.",
        )

    def pre_check(self) -> None:
        """
        Runs some initial checks against the state of the install and source, including:
        - Does the target exist?
        - Can we access the target?
        - Does the target have a manifest file?
        - Are there existing files in the document folders?
        - Are there existing users or documents in the database?
        """

        def pre_check_maybe_not_empty() -> None:
            # Skip this check if operating only on the database
            # We can expect data to exist in that case
            if not self.data_only:
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
            # But existing users or other data still matters in a data only
            if (
                User.objects.exclude(username__in=["consumer", "AnonymousUser"]).count()
                != 0
            ):
                self.stdout.write(
                    self.style.WARNING(
                        "Found existing user(s), this might indicate a non-empty installation",
                    ),
                )
            if Document.global_objects.count() != 0:
                self.stdout.write(
                    self.style.WARNING(
                        "Found existing documents(s), this might indicate a non-empty installation",
                    ),
                )

        def pre_check_manifest_exists() -> None:
            if not (self.source / "manifest.json").exists():
                raise CommandError(
                    "That directory doesn't appear to contain a manifest.json file.",
                )

        if not self.source.exists():
            raise CommandError("That path doesn't exist")

        if not os.access(self.source, os.R_OK):
            raise CommandError("That path doesn't appear to be readable")

        pre_check_maybe_not_empty()
        pre_check_manifest_exists()

    def load_manifest_files(self) -> None:
        """
        Loads manifest data from the various JSON files for parsing and loading the database
        """
        main_manifest_path: Path = self.source / "manifest.json"
        self.manifest_paths.append(main_manifest_path)

        for file in Path(self.source).glob("**/*-manifest.json"):
            self.manifest_paths.append(file)

    def load_metadata(self) -> None:
        """
        Loads either just the version information or the version information and extra data

        Must account for the old style of export as well, with just version.json
        """
        version_path: Path = self.source / "version.json"
        metadata_path: Path = self.source / "metadata.json"
        if not version_path.exists() and not metadata_path.exists():
            self.stdout.write(
                self.style.NOTICE("No version.json or metadata.json file located"),
            )
            return

        if metadata_path.exists():
            with metadata_path.open() as infile:
                data = json.load(infile)
                self.version = data["version"]
                if not self.passphrase and EXPORTER_CRYPTO_SETTINGS_NAME in data:
                    raise CommandError(
                        "No passphrase was given, but this export contains encrypted fields",
                    )
                elif EXPORTER_CRYPTO_SETTINGS_NAME in data:
                    self.load_crypt_params(data)
        elif version_path.exists():
            with version_path.open() as infile:
                self.version = json.load(infile)["version"]

        if self.version and self.version != version.__full_version_str__:
            self.stdout.write(
                self.style.WARNING(
                    "Version mismatch: "
                    f"Currently {version.__full_version_str__},"
                    f" importing {self.version}."
                    " Continuing, but import may fail.",
                ),
            )

    def _finalize_db_load(self, loaded_models: set[type[Model]]) -> None:
        """Verify referential integrity and reset auto-increment sequences."""
        through_tables = {
            field.remote_field.through._meta.db_table
            for model in loaded_models
            for field in model._meta.many_to_many
            if field.remote_field.through is not None
            and field.remote_field.through._meta.auto_created
        }
        table_names = [m._meta.db_table for m in loaded_models] + list(through_tables)
        if table_names:
            connection.check_constraints(table_names=table_names)

        if loaded_models:
            sequence_sql = connection.ops.sequence_reset_sql(
                no_style(),
                list(loaded_models),
            )
            with connection.cursor() as cursor:
                for sql in sequence_sql:
                    cursor.execute(sql)  # pragma: no cover

    def _import_error_context_message(self) -> str:
        """Return a diagnostic string explaining a DB import failure."""
        if (  # pragma: no cover
            self.version is not None and self.version != version.__full_version_str__
        ):
            return (  # pragma: no cover
                "Version mismatch: "
                f"Currently {version.__full_version_str__},"
                f" importing {self.version}"
            )
        return "No version information present"

    def load_data_to_database(self) -> None:
        """
        Streams records from each manifest path and loads them into the database
        using bulk_create with bounded batch sizes, avoiding holding the entire
        manifest in memory at once.

        Memory bound: at most batch_size * (number of distinct model types
        present simultaneously in the manifest) instances at any time.
        For the standard non-split manifest, records are grouped by model, so
        in practice only one model's batch accumulates at a time.
        """
        # Maps model class -> list of (instance, m2m_data) waiting to be flushed
        pending: defaultdict[type[Model], list[tuple[Model, M2MData]]] = defaultdict(
            list,
        )
        # All model classes inserted (needed for sequence reset after the load)
        loaded_models: set[type[Model]] = set()

        def flush_model(model: type[Model]) -> None:
            """bulk_create the pending batch for model, then apply M2M."""
            batch = pending.pop(model, [])
            if not batch:  # pragma: no cover
                return
            instances = [inst for inst, _ in batch]
            # GeneratedField is excluded because it is generated and trying to insert it will fail
            update_fields = [
                f.attname
                for f in model._meta.concrete_fields
                if not f.primary_key and not isinstance(f, GeneratedField)
            ]
            if not update_fields:  # pragma: no cover
                raise DeserializationError(
                    f"{model.__name__} has no updatable fields; PK-only models are not supported by the importer",
                )
            model.objects.bulk_create(  # type: ignore[attr-defined]
                instances,
                update_conflicts=True,
                unique_fields=[model._meta.pk.attname],
                update_fields=update_fields,
            )
            loaded_models.add(model)
            for instance, m2m_data in batch:
                for field_name, pk_list in m2m_data.items():
                    getattr(instance, field_name).set(pk_list)

        def flush_all() -> None:
            for model in list(pending):
                flush_model(model)

        try:
            with transaction.atomic():
                # ContentType and Permission have auto-assigned PKs on a fresh
                # install that conflict with exported PKs. Delete and re-import.
                ContentType.objects.all().delete()
                Permission.objects.all().delete()

                # Constraint checks are disabled so FK/M2M inserts succeed
                # regardless of record order within the manifest.
                # Note: on SQLite inside a transaction this context manager is a
                # no-op; the constraint-deferral path is only exercised on
                # PostgreSQL in production.
                with connection.constraint_checks_disabled():
                    for manifest_path in self.manifest_paths:
                        for record in iter_manifest_records(manifest_path):
                            model, instance, m2m_data = _deserialize_record(record)
                            pending[model].append((instance, m2m_data))
                            if len(pending[model]) >= self.batch_size:
                                flush_model(model)

                    flush_all()

                self._finalize_db_load(loaded_models)

        except (FieldDoesNotExist, DeserializationError, IntegrityError):
            self.stdout.write(self.style.ERROR("Database import failed"))
            self.stdout.write(self.style.ERROR(self._import_error_context_message()))
            raise

    def handle(self, *args, **options) -> None:
        logging.getLogger().handlers[0].level = logging.ERROR

        self.source = Path(options["source"]).resolve()
        self.data_only: bool = options["data_only"]
        self.passphrase: str | None = options.get("passphrase")
        self.batch_size: int = options["batch_size"]
        self.version: str | None = None
        self.salt: str | None = None
        self.manifest_paths = []

        # Create a temporary directory for extracting a zip file into it, even if supplied source is no zip file to keep code cleaner.
        with tempfile.TemporaryDirectory() as tmp_dir:
            if is_zipfile(self.source):
                with ZipFile(self.source) as zf:
                    zf.extractall(tmp_dir)
                self.source = Path(tmp_dir)
            self._run_import()

    def _run_import(self) -> None:
        self.pre_check()
        self.load_metadata()
        self.load_manifest_files()
        self.check_manifest_validity()
        self.decrypt_secret_fields()

        # see /src/documents/signals/handlers.py
        with (
            disable_signal(
                post_save,
                receiver=update_filename_and_move_files,
                sender=Document,
                weak=False,
            ),
            disable_signal(
                m2m_changed,
                receiver=update_filename_and_move_files,
                sender=Document.tags.through,
                weak=False,
            ),
            disable_signal(
                post_save,
                receiver=update_filename_and_move_files,
                sender=CustomFieldInstance,
                weak=False,
            ),
            disable_signal(
                post_save,
                receiver=check_paths_and_prune_custom_fields,
                sender=CustomField,
            ),
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
            self.load_data_to_database()

            if not self.data_only:
                self._import_files_from_manifest()
            else:
                self.stdout.write(self.style.NOTICE("Data only import completed"))

            for tmp in getattr(self, "_decrypted_tmp_paths", []):
                tmp.unlink(missing_ok=True)

        self.stdout.write("Updating search index...")
        call_command(
            "document_index",
            "reindex",
            no_progress_bar=self.no_progress_bar,
        )

    def check_manifest_validity(self) -> None:
        """
        Attempts to verify the manifest is valid.  Namely checking the files
        referred to exist and the files can be read from
        """

        def check_document_validity(document_record: dict) -> None:
            if EXPORTER_FILE_NAME not in document_record:
                raise CommandError(
                    "The manifest file contains a record which does not "
                    "refer to an actual document file.",
                )

            doc_file = document_record[EXPORTER_FILE_NAME]
            doc_path: Path = self.source / doc_file
            if not doc_path.exists():
                raise CommandError(
                    f'The manifest file refers to "{doc_file}" which does not '
                    "appear to be in the source directory.",
                )
            try:
                with doc_path.open(mode="rb"):
                    pass
            except Exception as e:
                raise CommandError(
                    f"Failed to read from original file {doc_path}",
                ) from e

            if EXPORTER_ARCHIVE_NAME in document_record:
                archive_file = document_record[EXPORTER_ARCHIVE_NAME]
                doc_archive_path: Path = self.source / archive_file
                if not doc_archive_path.exists():
                    raise CommandError(
                        f"The manifest file refers to {archive_file} which "
                        f"does not appear to be in the source directory.",
                    )
                try:
                    with doc_archive_path.open(mode="rb"):
                        pass
                except Exception as e:
                    raise CommandError(
                        f"Failed to read from archive file {doc_archive_path}",
                    ) from e

        def check_share_link_bundle_validity(bundle_record: dict) -> None:
            if EXPORTER_SHARE_LINK_BUNDLE_NAME not in bundle_record:
                return

            bundle_file = bundle_record[EXPORTER_SHARE_LINK_BUNDLE_NAME]
            bundle_path: Path = self.source / bundle_file
            if not bundle_path.exists():
                raise CommandError(
                    f'The manifest file refers to "{bundle_file}" which does not '
                    "appear to be in the source directory.",
                )
            try:
                with bundle_path.open(mode="rb"):
                    pass
            except Exception as e:
                raise CommandError(
                    f"Failed to read from share link bundle file {bundle_path}",
                ) from e

        self.stdout.write("Checking the manifest")
        for manifest_path in self.manifest_paths:
            for record in iter_manifest_records(manifest_path):
                # Only check if the document files exist if this is not data only
                # We don't care about documents for a data only import
                if self.data_only:
                    continue
                if record["model"] == "documents.document":
                    check_document_validity(record)
                elif record["model"] == "documents.sharelinkbundle":
                    check_share_link_bundle_validity(record)

    def _import_files_from_manifest(self) -> None:
        settings.ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
        settings.THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
        settings.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        settings.SHARE_LINK_BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

        self.stdout.write("Copy files into paperless...")

        for record in self.track(
            _iter_document_copy_records(self.manifest_paths),
            description="Copying files...",
        ):
            document = Document.global_objects.get(pk=record["pk"])

            doc_file = record[EXPORTER_FILE_NAME]
            document_path = self.source / doc_file

            if record[EXPORTER_THUMBNAIL_NAME]:
                thumb_file = record[EXPORTER_THUMBNAIL_NAME]
                thumbnail_path = (self.source / thumb_file).resolve()
            else:
                thumbnail_path = None

            if record[EXPORTER_ARCHIVE_NAME]:
                archive_file = record[EXPORTER_ARCHIVE_NAME]
                archive_path = self.source / archive_file
            else:
                archive_path = None

            with FileLock(settings.MEDIA_LOCK):
                if Path(document.source_path).is_file():
                    raise FileExistsError(document.source_path)

                create_source_path_directory(document.source_path)

                copy_file_with_basic_stats(document_path, document.source_path)

                if thumbnail_path:
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

        for record in self.track(
            _iter_share_link_bundle_copy_records(self.manifest_paths),
            description="Copying share link bundles...",
        ):
            bundle = ShareLinkBundle.objects.get(pk=record["pk"])
            bundle_file = record[EXPORTER_SHARE_LINK_BUNDLE_NAME]
            bundle_source_path = (self.source / bundle_file).resolve()
            bundle_target_path = bundle.absolute_file_path
            if bundle_target_path is None:
                raise CommandError(
                    f"Share link bundle {bundle.pk} does not have a valid file path.",
                )

            with FileLock(settings.MEDIA_LOCK):
                bundle_target_path.parent.mkdir(parents=True, exist_ok=True)
                copy_file_with_basic_stats(
                    bundle_source_path,
                    bundle_target_path,
                )

    def _decrypt_record_if_needed(self, record: dict) -> dict:
        fields = self.CRYPT_FIELDS_BY_MODEL.get(record.get("model", ""))
        if fields:
            for field in fields:
                if record["fields"].get(field):
                    record["fields"][field] = self.decrypt_string(
                        value=record["fields"][field],
                    )
        return record

    def decrypt_secret_fields(self) -> None:
        """
        The converse decryption of some fields out of the export before importing to database.
        Streams records from each manifest path and writes decrypted content to a temp file.
        """
        if not self.passphrase:
            return
        # Salt has been loaded from metadata.json at this point, so it cannot be None
        self.setup_crypto(passphrase=self.passphrase, salt=self.salt)
        self._decrypted_tmp_paths: list[Path] = []
        new_paths: list[Path] = []
        for manifest_path in self.manifest_paths:
            tmp = manifest_path.with_name(manifest_path.stem + ".decrypted.json")
            with tmp.open("w", encoding="utf-8") as out:
                out.write("[\n")
                first = True
                for record in iter_manifest_records(manifest_path):
                    if not first:
                        out.write(",\n")
                    json.dump(
                        self._decrypt_record_if_needed(record),
                        out,
                        indent=2,
                        ensure_ascii=False,
                    )
                    first = False
                out.write("\n]\n")
            self._decrypted_tmp_paths.append(tmp)
            new_paths.append(tmp)
        self.manifest_paths = new_paths
