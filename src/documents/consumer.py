import datetime
import hashlib
import os
import tempfile
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final

import magic
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from filelock import FileLock
from rest_framework.reverse import reverse

from documents.classifier import load_classifier
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.file_handling import create_source_path_directory
from documents.file_handling import generate_unique_filename
from documents.loggers import LoggingMixin
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.models import WorkflowTrigger
from documents.parsers import DocumentParser
from documents.parsers import ParseError
from documents.parsers import get_parser_class_for_mime_type
from documents.permissions import set_permissions_for_object
from documents.plugins.base import AlwaysRunPluginMixin
from documents.plugins.base import ConsumeTaskPlugin
from documents.plugins.base import NoCleanupPluginMixin
from documents.plugins.base import NoSetupPluginMixin
from documents.plugins.date_parsing import get_date_parser
from documents.plugins.helpers import ProgressManager
from documents.plugins.helpers import ProgressStatusOptions
from documents.signals import document_consumption_finished
from documents.signals import document_consumption_started
from documents.signals.handlers import run_workflows
from documents.templating.workflows import parse_w_workflow_placeholders
from documents.utils import copy_basic_file_stats
from documents.utils import copy_file_with_basic_stats
from documents.utils import run_subprocess
from paperless_mail.parsers import MailDocumentParser

LOGGING_NAME: Final[str] = "paperless.consumer"


class WorkflowTriggerPlugin(
    NoCleanupPluginMixin,
    NoSetupPluginMixin,
    AlwaysRunPluginMixin,
    ConsumeTaskPlugin,
):
    NAME: str = "WorkflowTriggerPlugin"

    def run(self) -> str | None:
        """
        Get overrides from matching workflows
        """
        overrides, msg = run_workflows(
            trigger_type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            document=self.input_doc,
            logging_group=None,
            overrides=DocumentMetadataOverrides(),
        )
        if overrides:
            self.metadata.update(overrides)
        return msg


class ConsumerError(Exception):
    pass


class ConsumerStatusShortMessage(str, Enum):
    DOCUMENT_ALREADY_EXISTS = "document_already_exists"
    DOCUMENT_ALREADY_EXISTS_IN_TRASH = "document_already_exists_in_trash"
    ASN_ALREADY_EXISTS = "asn_already_exists"
    ASN_ALREADY_EXISTS_IN_TRASH = "asn_already_exists_in_trash"
    ASN_RANGE = "asn_value_out_of_range"
    FILE_NOT_FOUND = "file_not_found"
    PRE_CONSUME_SCRIPT_NOT_FOUND = "pre_consume_script_not_found"
    PRE_CONSUME_SCRIPT_ERROR = "pre_consume_script_error"
    POST_CONSUME_SCRIPT_NOT_FOUND = "post_consume_script_not_found"
    POST_CONSUME_SCRIPT_ERROR = "post_consume_script_error"
    NEW_FILE = "new_file"
    UNSUPPORTED_TYPE = "unsupported_type"
    PARSING_DOCUMENT = "parsing_document"
    GENERATING_THUMBNAIL = "generating_thumbnail"
    PARSE_DATE = "parse_date"
    SAVE_DOCUMENT = "save_document"
    FINISHED = "finished"
    FAILED = "failed"


class ConsumerPluginMixin:
    def __init__(
        self,
        input_doc: ConsumableDocument,
        metadata: DocumentMetadataOverrides,
        status_mgr: ProgressManager,
        base_tmp_dir: Path,
        task_id: str,
    ) -> None:
        super().__init__(input_doc, metadata, status_mgr, base_tmp_dir, task_id)

        self.renew_logging_group()

        self.filename = self.metadata.filename or self.input_doc.original_file.name

    def _send_progress(
        self,
        current_progress: int,
        max_progress: int,
        status: ProgressStatusOptions,
        message: ConsumerStatusShortMessage | str | None = None,
        document_id=None,
    ) -> None:  # pragma: no cover
        self.status_mgr.send_progress(
            status,
            message,
            current_progress,
            max_progress,
            extra_args={
                "document_id": document_id,
                "owner_id": self.metadata.owner_id if self.metadata.owner_id else None,
                "users_can_view": (self.metadata.view_users or [])
                + (self.metadata.change_users or []),
                "groups_can_view": (self.metadata.view_groups or [])
                + (self.metadata.change_groups or []),
            },
        )

    def _fail(
        self,
        message: ConsumerStatusShortMessage | str,
        log_message: str | None = None,
        exc_info=None,
        exception: Exception | None = None,
    ):
        self._send_progress(100, 100, ProgressStatusOptions.FAILED, message)
        self.log.error(log_message or message, exc_info=exc_info)
        raise ConsumerError(f"{self.filename}: {log_message or message}") from exception


class ConsumerPlugin(
    AlwaysRunPluginMixin,
    NoSetupPluginMixin,
    NoCleanupPluginMixin,
    LoggingMixin,
    ConsumerPluginMixin,
    ConsumeTaskPlugin,
):
    logging_name = LOGGING_NAME

    def run_pre_consume_script(self) -> None:
        """
        If one is configured and exists, run the pre-consume script and
        handle its output and/or errors
        """
        if not settings.PRE_CONSUME_SCRIPT:
            return

        if not Path(settings.PRE_CONSUME_SCRIPT).is_file():
            self._fail(
                ConsumerStatusShortMessage.PRE_CONSUME_SCRIPT_NOT_FOUND,
                f"Configured pre-consume script "
                f"{settings.PRE_CONSUME_SCRIPT} does not exist.",
            )

        self.log.info(f"Executing pre-consume script {settings.PRE_CONSUME_SCRIPT}")

        working_file_path = str(self.working_copy)
        original_file_path = str(self.input_doc.original_file)

        script_env = os.environ.copy()
        script_env["DOCUMENT_SOURCE_PATH"] = original_file_path
        script_env["DOCUMENT_WORKING_PATH"] = working_file_path
        script_env["TASK_ID"] = self.task_id or ""

        try:
            run_subprocess(
                [
                    settings.PRE_CONSUME_SCRIPT,
                    original_file_path,
                ],
                script_env,
                self.log,
            )

        except Exception as e:
            self._fail(
                ConsumerStatusShortMessage.PRE_CONSUME_SCRIPT_ERROR,
                f"Error while executing pre-consume script: {e}",
                exc_info=True,
                exception=e,
            )

    def run_post_consume_script(self, document: Document) -> None:
        """
        If one is configured and exists, run the pre-consume script and
        handle its output and/or errors
        """
        if not settings.POST_CONSUME_SCRIPT:
            return

        if not Path(settings.POST_CONSUME_SCRIPT).is_file():
            self._fail(
                ConsumerStatusShortMessage.POST_CONSUME_SCRIPT_NOT_FOUND,
                f"Configured post-consume script "
                f"{settings.POST_CONSUME_SCRIPT} does not exist.",
            )

        self.log.info(
            f"Executing post-consume script {settings.POST_CONSUME_SCRIPT}",
        )

        script_env = os.environ.copy()

        script_env["DOCUMENT_ID"] = str(document.pk)
        script_env["DOCUMENT_TYPE"] = str(document.document_type)
        script_env["DOCUMENT_CREATED"] = str(document.created)
        script_env["DOCUMENT_MODIFIED"] = str(document.modified)
        script_env["DOCUMENT_ADDED"] = str(document.added)
        script_env["DOCUMENT_FILE_NAME"] = document.get_public_filename()
        script_env["DOCUMENT_SOURCE_PATH"] = os.path.normpath(document.source_path)
        script_env["DOCUMENT_ARCHIVE_PATH"] = os.path.normpath(
            str(document.archive_path),
        )
        script_env["DOCUMENT_THUMBNAIL_PATH"] = os.path.normpath(
            document.thumbnail_path,
        )
        script_env["DOCUMENT_DOWNLOAD_URL"] = reverse(
            "document-download",
            kwargs={"pk": document.pk},
        )
        script_env["DOCUMENT_THUMBNAIL_URL"] = reverse(
            "document-thumb",
            kwargs={"pk": document.pk},
        )
        script_env["DOCUMENT_OWNER"] = (
            document.owner.get_username() if document.owner else ""
        )
        script_env["DOCUMENT_CORRESPONDENT"] = str(document.correspondent)
        script_env["DOCUMENT_TAGS"] = str(
            ",".join(document.tags.all().values_list("name", flat=True)),
        )
        script_env["DOCUMENT_ORIGINAL_FILENAME"] = str(document.original_filename)
        script_env["TASK_ID"] = self.task_id or ""

        try:
            run_subprocess(
                [
                    settings.POST_CONSUME_SCRIPT,
                    str(document.pk),
                    document.get_public_filename(),
                    os.path.normpath(document.source_path),
                    os.path.normpath(document.thumbnail_path),
                    reverse("document-download", kwargs={"pk": document.pk}),
                    reverse("document-thumb", kwargs={"pk": document.pk}),
                    str(document.correspondent),
                    str(",".join(document.tags.all().values_list("name", flat=True))),
                ],
                script_env,
                self.log,
            )

        except Exception as e:
            self._fail(
                ConsumerStatusShortMessage.POST_CONSUME_SCRIPT_ERROR,
                f"Error while executing post-consume script: {e}",
                exc_info=True,
                exception=e,
            )

    def run(self) -> str:
        """
        Return the document object if it was successfully created.
        """

        tempdir = None

        try:
            # Preflight has already run including progress update to 0%
            self.log.info(f"Consuming {self.filename}")

            # For the actual work, copy the file into a tempdir
            tempdir = tempfile.TemporaryDirectory(
                prefix="paperless-ngx",
                dir=settings.SCRATCH_DIR,
            )
            self.working_copy = Path(tempdir.name) / Path(self.filename)
            copy_file_with_basic_stats(self.input_doc.original_file, self.working_copy)
            self.unmodified_original = None

            # Determine the parser class.

            mime_type = magic.from_file(self.working_copy, mime=True)

            self.log.debug(f"Detected mime type: {mime_type}")

            if (
                Path(self.filename).suffix.lower() == ".pdf"
                and mime_type in settings.CONSUMER_PDF_RECOVERABLE_MIME_TYPES
            ):
                try:
                    # The file might be a pdf, but the mime type is wrong.
                    # Try to clean with qpdf
                    self.log.debug(
                        "Detected possible PDF with wrong mime type, trying to clean with qpdf",
                    )
                    run_subprocess(
                        [
                            "qpdf",
                            "--replace-input",
                            self.working_copy,
                        ],
                        logger=self.log,
                    )
                    mime_type = magic.from_file(self.working_copy, mime=True)
                    self.log.debug(f"Detected mime type after qpdf: {mime_type}")
                    # Save the original file for later
                    self.unmodified_original = (
                        Path(tempdir.name) / Path("uo") / Path(self.filename)
                    )
                    self.unmodified_original.parent.mkdir(exist_ok=True)
                    copy_file_with_basic_stats(
                        self.input_doc.original_file,
                        self.unmodified_original,
                    )
                except Exception as e:
                    self.log.error(f"Error attempting to clean PDF: {e}")

            # Based on the mime type, get the parser for that type
            parser_class: type[DocumentParser] | None = get_parser_class_for_mime_type(
                mime_type,
            )
            if not parser_class:
                tempdir.cleanup()
                self._fail(
                    ConsumerStatusShortMessage.UNSUPPORTED_TYPE,
                    f"Unsupported mime type {mime_type}",
                )

            # Notify all listeners that we're going to do some work.

            document_consumption_started.send(
                sender=self.__class__,
                filename=self.working_copy,
                logging_group=self.logging_group,
            )

            self.run_pre_consume_script()
        except:
            if tempdir:
                tempdir.cleanup()
            raise

        def progress_callback(
            current_progress,
            max_progress,
        ) -> None:  # pragma: no cover
            # recalculate progress to be within 20 and 80
            p = int((current_progress / max_progress) * 50 + 20)
            self._send_progress(p, 100, ProgressStatusOptions.WORKING)

        # This doesn't parse the document yet, but gives us a parser.

        document_parser: DocumentParser = parser_class(
            self.logging_group,
            progress_callback=progress_callback,
        )

        self.log.debug(f"Parser: {type(document_parser).__name__}")

        # Parse the document. This may take some time.

        text = None
        date = None
        thumbnail = None
        archive_path = None
        page_count = None

        try:
            self._send_progress(
                20,
                100,
                ProgressStatusOptions.WORKING,
                ConsumerStatusShortMessage.PARSING_DOCUMENT,
            )
            self.log.debug(f"Parsing {self.filename}...")
            if (
                isinstance(document_parser, MailDocumentParser)
                and self.input_doc.mailrule_id
            ):
                document_parser.parse(
                    self.working_copy,
                    mime_type,
                    self.filename,
                    self.input_doc.mailrule_id,
                )
            else:
                document_parser.parse(self.working_copy, mime_type, self.filename)

            self.log.debug(f"Generating thumbnail for {self.filename}...")
            self._send_progress(
                70,
                100,
                ProgressStatusOptions.WORKING,
                ConsumerStatusShortMessage.GENERATING_THUMBNAIL,
            )
            thumbnail = document_parser.get_thumbnail(
                self.working_copy,
                mime_type,
                self.filename,
            )

            text = document_parser.get_text()
            date = document_parser.get_date()
            if date is None:
                self._send_progress(
                    90,
                    100,
                    ProgressStatusOptions.WORKING,
                    ConsumerStatusShortMessage.PARSE_DATE,
                )
                with get_date_parser() as date_parser:
                    date = next(date_parser.parse(self.filename, text), None)
            archive_path = document_parser.get_archive_path()
            page_count = document_parser.get_page_count(self.working_copy, mime_type)

        except ParseError as e:
            document_parser.cleanup()
            if tempdir:
                tempdir.cleanup()
            self._fail(
                str(e),
                f"Error occurred while consuming document {self.filename}: {e}",
                exc_info=True,
                exception=e,
            )
        except Exception as e:
            document_parser.cleanup()
            if tempdir:
                tempdir.cleanup()
            self._fail(
                str(e),
                f"Unexpected error while consuming document {self.filename}: {e}",
                exc_info=True,
                exception=e,
            )

        # Prepare the document classifier.

        # TODO: I don't really like to do this here, but this way we avoid
        #   reloading the classifier multiple times, since there are multiple
        #   post-consume hooks that all require the classifier.

        classifier = load_classifier()

        self._send_progress(
            95,
            100,
            ProgressStatusOptions.WORKING,
            ConsumerStatusShortMessage.SAVE_DOCUMENT,
        )
        # now that everything is done, we can start to store the document
        # in the system. This will be a transaction and reasonably fast.
        try:
            with transaction.atomic():
                # store the document.
                document = self._store(
                    text=text,
                    date=date,
                    page_count=page_count,
                    mime_type=mime_type,
                )

                # If we get here, it was successful. Proceed with post-consume
                # hooks. If they fail, nothing will get changed.

                document_consumption_finished.send(
                    sender=self.__class__,
                    document=document,
                    logging_group=self.logging_group,
                    classifier=classifier,
                    original_file=self.unmodified_original
                    if self.unmodified_original
                    else self.working_copy,
                )

                # After everything is in the database, copy the files into
                # place. If this fails, we'll also rollback the transaction.
                with FileLock(settings.MEDIA_LOCK):
                    document.filename = generate_unique_filename(document)
                    create_source_path_directory(document.source_path)

                    self._write(
                        self.unmodified_original
                        if self.unmodified_original is not None
                        else self.working_copy,
                        document.source_path,
                    )

                    self._write(
                        thumbnail,
                        document.thumbnail_path,
                    )

                    if archive_path and Path(archive_path).is_file():
                        document.archive_filename = generate_unique_filename(
                            document,
                            archive_filename=True,
                        )
                        create_source_path_directory(document.archive_path)
                        self._write(
                            archive_path,
                            document.archive_path,
                        )

                        with Path(archive_path).open("rb") as f:
                            document.archive_checksum = hashlib.md5(
                                f.read(),
                            ).hexdigest()

                # Don't save with the lock active. Saving will cause the file
                # renaming logic to acquire the lock as well.
                # This triggers things like file renaming
                document.save()

                # Delete the file only if it was successfully consumed
                self.log.debug(f"Deleting original file {self.input_doc.original_file}")
                self.input_doc.original_file.unlink()
                self.log.debug(f"Deleting working copy {self.working_copy}")
                self.working_copy.unlink()
                if self.unmodified_original is not None:  # pragma: no cover
                    self.log.debug(
                        f"Deleting unmodified original file {self.unmodified_original}",
                    )
                    self.unmodified_original.unlink()

                # https://github.com/jonaswinkler/paperless-ng/discussions/1037
                shadow_file = (
                    Path(self.input_doc.original_file).parent
                    / f"._{Path(self.input_doc.original_file).name}"
                )

                if Path(shadow_file).is_file():
                    self.log.debug(f"Deleting shadow file {shadow_file}")
                    Path(shadow_file).unlink()

        except Exception as e:
            self._fail(
                str(e),
                f"The following error occurred while storing document "
                f"{self.filename} after parsing: {e}",
                exc_info=True,
                exception=e,
            )
        finally:
            document_parser.cleanup()
            tempdir.cleanup()

        self.run_post_consume_script(document)

        self.log.info(f"Document {document} consumption finished")

        self._send_progress(
            100,
            100,
            ProgressStatusOptions.SUCCESS,
            ConsumerStatusShortMessage.FINISHED,
            document.id,
        )

        # Return the most up to date fields
        document.refresh_from_db()

        return f"Success. New document id {document.pk} created"

    def _parse_title_placeholders(self, title: str) -> str:
        local_added = timezone.localtime(timezone.now())

        correspondent_name = (
            Correspondent.objects.get(pk=self.metadata.correspondent_id).name
            if self.metadata.correspondent_id is not None
            else None
        )
        doc_type_name = (
            DocumentType.objects.get(pk=self.metadata.document_type_id).name
            if self.metadata.document_type_id is not None
            else None
        )
        owner_username = (
            User.objects.get(pk=self.metadata.owner_id).username
            if self.metadata.owner_id is not None
            else None
        )

        return parse_w_workflow_placeholders(
            title,
            correspondent_name,
            doc_type_name,
            owner_username,
            local_added,
            self.filename,
            self.filename,
        )

    def _store(
        self,
        text: str,
        date: datetime.datetime | None,
        page_count: int | None,
        mime_type: str,
    ) -> Document:
        # If someone gave us the original filename, use it instead of doc.

        self.log.debug("Saving record to database")

        if self.metadata.created is not None:
            create_date = self.metadata.created
            self.log.debug(
                f"Creation date from post_documents parameter: {create_date}",
            )
        elif date is not None:
            create_date = date
            self.log.debug(f"Creation date from parse_date: {create_date}")
        else:
            stats = Path(self.input_doc.original_file).stat()
            create_date = timezone.make_aware(
                datetime.datetime.fromtimestamp(stats.st_mtime),
            )
            self.log.debug(f"Creation date from st_mtime: {create_date}")

        if self.metadata.filename:
            title = Path(self.metadata.filename).stem
        else:
            title = self.input_doc.original_file.stem

        if self.metadata.title is not None:
            try:
                title = self._parse_title_placeholders(self.metadata.title)
            except Exception as e:
                self.log.error(
                    f"Error occurred parsing title override '{self.metadata.title}', falling back to original. Exception: {e}",
                )

        file_for_checksum = (
            self.unmodified_original
            if self.unmodified_original is not None
            else self.working_copy
        )

        document = Document.objects.create(
            title=title[:127],
            content=text,
            mime_type=mime_type,
            checksum=hashlib.md5(file_for_checksum.read_bytes()).hexdigest(),
            created=create_date,
            modified=create_date,
            page_count=page_count,
            original_filename=self.filename,
        )

        self.apply_overrides(document)

        document.save()

        return document

    def apply_overrides(self, document) -> None:
        if self.metadata.correspondent_id:
            document.correspondent = Correspondent.objects.get(
                pk=self.metadata.correspondent_id,
            )

        if self.metadata.document_type_id:
            document.document_type = DocumentType.objects.get(
                pk=self.metadata.document_type_id,
            )

        if self.metadata.tag_ids:
            for tag_id in self.metadata.tag_ids:
                document.add_nested_tags([Tag.objects.get(pk=tag_id)])

        if self.metadata.storage_path_id:
            document.storage_path = StoragePath.objects.get(
                pk=self.metadata.storage_path_id,
            )

        if self.metadata.asn is not None:
            document.archive_serial_number = self.metadata.asn

        if self.metadata.owner_id:
            document.owner = User.objects.get(
                pk=self.metadata.owner_id,
            )

        if (
            self.metadata.view_users is not None
            or self.metadata.view_groups is not None
            or self.metadata.change_users is not None
            or self.metadata.change_users is not None
        ):
            permissions = {
                "view": {
                    "users": self.metadata.view_users or [],
                    "groups": self.metadata.view_groups or [],
                },
                "change": {
                    "users": self.metadata.change_users or [],
                    "groups": self.metadata.change_groups or [],
                },
            }
            set_permissions_for_object(permissions=permissions, object=document)

        if self.metadata.custom_fields:
            for field in CustomField.objects.filter(
                id__in=self.metadata.custom_fields.keys(),
            ).distinct():
                value_field_name = CustomFieldInstance.get_value_field_name(
                    data_type=field.data_type,
                )
                args = {
                    "field": field,
                    "document": document,
                    value_field_name: self.metadata.custom_fields.get(field.id, None),
                }
                CustomFieldInstance.objects.create(**args)  # adds to document

    def _write(self, source, target) -> None:
        with (
            Path(source).open("rb") as read_file,
            Path(target).open("wb") as write_file,
        ):
            write_file.write(read_file.read())

        # Attempt to copy file's original stats, but it's ok if we can't
        try:
            copy_basic_file_stats(source, target)
        except Exception:  # pragma: no cover
            pass


class ConsumerPreflightPlugin(
    NoCleanupPluginMixin,
    NoSetupPluginMixin,
    AlwaysRunPluginMixin,
    LoggingMixin,
    ConsumerPluginMixin,
    ConsumeTaskPlugin,
):
    NAME: str = "ConsumerPreflightPlugin"
    logging_name = LOGGING_NAME

    def pre_check_file_exists(self) -> None:
        """
        Confirm the input file still exists where it should
        """
        if TYPE_CHECKING:
            assert isinstance(self.input_doc.original_file, Path), (
                self.input_doc.original_file
            )
        if not self.input_doc.original_file.is_file():
            self._fail(
                ConsumerStatusShortMessage.FILE_NOT_FOUND,
                f"Cannot consume {self.input_doc.original_file}: File not found.",
            )

    def pre_check_duplicate(self) -> None:
        """
        Using the MD5 of the file, check this exact file doesn't already exist
        """
        with Path(self.input_doc.original_file).open("rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        existing_doc = Document.global_objects.filter(
            Q(checksum=checksum) | Q(archive_checksum=checksum),
        )
        if existing_doc.exists():
            existing_doc = existing_doc.order_by("-created")
            duplicates_in_trash = existing_doc.filter(deleted_at__isnull=False)
            log_msg = (
                f"Consuming duplicate {self.filename}: "
                f"{existing_doc.count()} existing document(s) share the same content."
            )

            if duplicates_in_trash.exists():
                log_msg += " Note: at least one existing document is in the trash."

            self.log.warning(log_msg)

            if settings.CONSUMER_DELETE_DUPLICATES:
                duplicate = existing_doc.first()
                duplicate_label = (
                    duplicate.title
                    or duplicate.original_filename
                    or (Path(duplicate.filename).name if duplicate.filename else None)
                    or str(duplicate.pk)
                )

                Path(self.input_doc.original_file).unlink()

                failure_msg = (
                    f"Not consuming {self.filename}: "
                    f"It is a duplicate of {duplicate_label} (#{duplicate.pk})"
                )
                status_msg = ConsumerStatusShortMessage.DOCUMENT_ALREADY_EXISTS

                if duplicates_in_trash.exists():
                    status_msg = (
                        ConsumerStatusShortMessage.DOCUMENT_ALREADY_EXISTS_IN_TRASH
                    )
                    failure_msg += " Note: existing document is in the trash."

                self._fail(
                    status_msg,
                    failure_msg,
                )

    def pre_check_directories(self) -> None:
        """
        Ensure all required directories exist before attempting to use them
        """
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        settings.THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
        settings.ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
        settings.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    def run(self) -> None:
        self._send_progress(
            0,
            100,
            ProgressStatusOptions.STARTED,
            ConsumerStatusShortMessage.NEW_FILE,
        )

        # Make sure that preconditions for consuming the file are met.

        self.pre_check_file_exists()
        self.pre_check_duplicate()
        self.pre_check_directories()


class AsnCheckPlugin(
    NoCleanupPluginMixin,
    NoSetupPluginMixin,
    AlwaysRunPluginMixin,
    LoggingMixin,
    ConsumerPluginMixin,
    ConsumeTaskPlugin,
):
    NAME: str = "AsnCheckPlugin"
    logging_name = LOGGING_NAME

    def pre_check_asn_value(self) -> None:
        """
        Check that if override_asn is given, it is unique and within a valid range
        """
        if self.metadata.asn is None:
            # if ASN is None
            return
        # Validate the range is above zero and less than uint32_t max
        # otherwise, Whoosh can't handle it in the index
        if (
            self.metadata.asn < Document.ARCHIVE_SERIAL_NUMBER_MIN
            or self.metadata.asn > Document.ARCHIVE_SERIAL_NUMBER_MAX
        ):
            self._fail(
                ConsumerStatusShortMessage.ASN_RANGE,
                f"Not consuming {self.filename}: "
                f"Given ASN {self.metadata.asn} is out of range "
                f"[{Document.ARCHIVE_SERIAL_NUMBER_MIN:,}, "
                f"{Document.ARCHIVE_SERIAL_NUMBER_MAX:,}]",
            )
        existing_asn_doc = Document.global_objects.filter(
            archive_serial_number=self.metadata.asn,
        )
        if existing_asn_doc.exists():
            msg = ConsumerStatusShortMessage.ASN_ALREADY_EXISTS
            log_msg = f"Not consuming {self.filename}: Given ASN {self.metadata.asn} already exists!"

            if existing_asn_doc.first().deleted_at is not None:
                msg = ConsumerStatusShortMessage.ASN_ALREADY_EXISTS_IN_TRASH
                log_msg += " Note: existing document is in the trash."

            self._fail(
                msg,
                log_msg,
            )

    def run(self) -> None:
        self.pre_check_asn_value()
