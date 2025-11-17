import datetime
import hashlib
import os
import tempfile
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

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
from documents.parsers import parse_date
from documents.permissions import set_permissions_for_object
from documents.plugins.base import AlwaysRunPluginMixin
from documents.plugins.base import ConsumeTaskPlugin
from documents.plugins.base import NoCleanupPluginMixin
from documents.plugins.base import NoSetupPluginMixin
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
    ):  # pragma: no cover
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
    logging_name = "paperless.consumer"

    def run_pre_consume_script(self):
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

    def run_post_consume_script(self, document: Document):
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
        Main entry point for document consumption.

        Orchestrates the entire document processing pipeline from setup
        through parsing, storage, and post-processing.

        Returns:
            str: Success message with document ID
        """
        tempdir = None
        document_parser = None

        try:
            # Setup phase
            tempdir = self._setup_working_copy()
            mime_type = self._determine_mime_type(tempdir)
            parser_class = self._get_parser_class(mime_type, tempdir)

            # Signal document consumption start
            document_consumption_started.send(
                sender=self.__class__,
                filename=self.working_copy,
                logging_group=self.logging_group,
            )

            # Pre-processing
            self.run_pre_consume_script()

            # Parsing phase
            document_parser = self._create_parser_instance(parser_class)
            text, date, thumbnail, archive_path, page_count = self._parse_document(
                document_parser, mime_type,
            )

            # Storage phase
            classifier = load_classifier()
            document = self._store_document_in_transaction(
                text=text,
                date=date,
                page_count=page_count,
                mime_type=mime_type,
                thumbnail=thumbnail,
                archive_path=archive_path,
                classifier=classifier,
            )

            # Cleanup files
            self._cleanup_consumed_files()

            # Post-processing
            self.run_post_consume_script(document)

            # Finalize
            return self._finalize_consumption(document)

        except:
            if tempdir:
                tempdir.cleanup()
            raise
        finally:
            if document_parser:
                document_parser.cleanup()
            if tempdir:
                tempdir.cleanup()

    def _setup_working_copy(self) -> tempfile.TemporaryDirectory:
        """
        Setup temporary working directory and copy source file.

        Creates a temporary directory and copies the original file into it
        for processing. Initializes working_copy and unmodified_original attributes.

        Returns:
            tempfile.TemporaryDirectory: The temporary directory instance
        """
        self.log.info(f"Consuming {self.filename}")

        tempdir = tempfile.TemporaryDirectory(
            prefix="paperless-ngx",
            dir=settings.SCRATCH_DIR,
        )
        self.working_copy = Path(tempdir.name) / Path(self.filename)
        copy_file_with_basic_stats(self.input_doc.original_file, self.working_copy)
        self.unmodified_original = None

        return tempdir

    def _determine_mime_type(self, tempdir: tempfile.TemporaryDirectory) -> str:
        """
        Determine MIME type of the document and attempt PDF recovery if needed.

        Detects the MIME type using python-magic. For PDF files with incorrect
        MIME types, attempts recovery using qpdf and preserves the original file.

        Args:
            tempdir: Temporary directory for storing recovered files

        Returns:
            str: The detected MIME type
        """
        mime_type = magic.from_file(self.working_copy, mime=True)
        self.log.debug(f"Detected mime type: {mime_type}")

        # Attempt PDF recovery if needed
        if (
            Path(self.filename).suffix.lower() == ".pdf"
            and mime_type in settings.CONSUMER_PDF_RECOVERABLE_MIME_TYPES
        ):
            mime_type = self._attempt_pdf_recovery(tempdir, mime_type)

        return mime_type

    def _attempt_pdf_recovery(
        self,
        tempdir: tempfile.TemporaryDirectory,
        original_mime_type: str,
    ) -> str:
        """
        Attempt to recover a PDF file with incorrect MIME type using qpdf.

        Args:
            tempdir: Temporary directory for storing recovered files
            original_mime_type: The original detected MIME type

        Returns:
            str: The MIME type after recovery attempt
        """
        try:
            self.log.debug(
                "Detected possible PDF with wrong mime type, trying to clean with qpdf",
            )
            run_subprocess(
                ["qpdf", "--replace-input", self.working_copy],
                logger=self.log,
            )

            # Re-detect MIME type after qpdf
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

            return mime_type

        except Exception as e:
            self.log.error(f"Error attempting to clean PDF: {e}")
            return original_mime_type

    def _get_parser_class(
        self,
        mime_type: str,
        tempdir: tempfile.TemporaryDirectory,
    ) -> type[DocumentParser]:
        """
        Determine which parser to use based on MIME type.

        Args:
            mime_type: The detected MIME type
            tempdir: Temporary directory to cleanup on failure

        Returns:
            type[DocumentParser]: The parser class to use

        Raises:
            ConsumerError: If MIME type is not supported
        """
        parser_class: type[DocumentParser] | None = get_parser_class_for_mime_type(
            mime_type,
        )

        if not parser_class:
            tempdir.cleanup()
            self._fail(
                ConsumerStatusShortMessage.UNSUPPORTED_TYPE,
                f"Unsupported mime type {mime_type}",
            )

        return parser_class

    def _create_parser_instance(
        self,
        parser_class: type[DocumentParser],
    ) -> DocumentParser:
        """
        Create a parser instance with progress callback.

        Args:
            parser_class: The parser class to instantiate

        Returns:
            DocumentParser: Configured parser instance
        """
        def progress_callback(current_progress, max_progress):  # pragma: no cover
            # Recalculate progress to be within 20 and 80
            p = int((current_progress / max_progress) * 50 + 20)
            self._send_progress(p, 100, ProgressStatusOptions.WORKING)

        document_parser = parser_class(
            self.logging_group,
            progress_callback=progress_callback,
        )

        self.log.debug(f"Parser: {type(document_parser).__name__}")

        return document_parser

    def _parse_document(
        self,
        document_parser: DocumentParser,
        mime_type: str,
    ) -> tuple[str, datetime.datetime | None, Path, Path | None, int | None]:
        """
        Parse the document and extract metadata.

        Performs document parsing, thumbnail generation, date detection,
        and page counting. Handles both regular documents and mail documents.

        Args:
            document_parser: The parser instance to use
            mime_type: The document MIME type

        Returns:
            tuple: (text, date, thumbnail, archive_path, page_count)

        Raises:
            ConsumerError: If parsing fails
        """
        try:
            # Parse document content
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

            # Generate thumbnail
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

            # Extract metadata
            text = document_parser.get_text()
            date = document_parser.get_date()

            # Parse date if not found by parser
            if date is None:
                self._send_progress(
                    90,
                    100,
                    ProgressStatusOptions.WORKING,
                    ConsumerStatusShortMessage.PARSE_DATE,
                )
                date = parse_date(self.filename, text)

            archive_path = document_parser.get_archive_path()
            page_count = document_parser.get_page_count(self.working_copy, mime_type)

            return text, date, thumbnail, archive_path, page_count

        except ParseError as e:
            self._fail(
                str(e),
                f"Error occurred while consuming document {self.filename}: {e}",
                exc_info=True,
                exception=e,
            )
        except Exception as e:
            self._fail(
                str(e),
                f"Unexpected error while consuming document {self.filename}: {e}",
                exc_info=True,
                exception=e,
            )

    def _store_document_in_transaction(
        self,
        text: str,
        date: datetime.datetime | None,
        page_count: int | None,
        mime_type: str,
        thumbnail: Path,
        archive_path: Path | None,
        classifier,
    ) -> Document:
        """
        Store document and files in database within a transaction.

        Creates the document record, runs AI scanner, triggers signals,
        and stores all associated files (source, thumbnail, archive).

        Args:
            text: Extracted document text
            date: Document date
            page_count: Number of pages
            mime_type: Document MIME type
            thumbnail: Path to thumbnail file
            archive_path: Path to archive file (if any)
            classifier: Document classifier instance

        Returns:
            Document: The created document instance

        Raises:
            ConsumerError: If storage fails
        """
        self._send_progress(
            95,
            100,
            ProgressStatusOptions.WORKING,
            ConsumerStatusShortMessage.SAVE_DOCUMENT,
        )

        try:
            with transaction.atomic():
                # Create document record
                document = self._store(
                    text=text,
                    date=date,
                    page_count=page_count,
                    mime_type=mime_type,
                )

                # Run AI scanner for automatic metadata detection
                self._run_ai_scanner(document, text)

                # Notify listeners
                document_consumption_finished.send(
                    sender=self.__class__,
                    document=document,
                    logging_group=self.logging_group,
                    classifier=classifier,
                    original_file=(
                        self.unmodified_original
                        if self.unmodified_original
                        else self.working_copy
                    ),
                )

                # Store files
                self._store_document_files(document, thumbnail, archive_path)

                # Save document (triggers file renaming)
                document.save()

                return document

        except Exception as e:
            self._fail(
                str(e),
                f"The following error occurred while storing document "
                f"{self.filename} after parsing: {e}",
                exc_info=True,
                exception=e,
            )

    def _store_document_files(
        self,
        document: Document,
        thumbnail: Path,
        archive_path: Path | None,
    ) -> None:
        """
        Store document files (source, thumbnail, archive) to disk.

        Acquires a file lock and stores all document files in their
        final locations. Generates unique filenames and creates directories.

        Args:
            document: The document instance
            thumbnail: Path to thumbnail file
            archive_path: Path to archive file (if any)
        """
        with FileLock(settings.MEDIA_LOCK):
            # Generate filename and create directory
            document.filename = generate_unique_filename(document)
            create_source_path_directory(document.source_path)

            # Store source file
            source_file = (
                self.unmodified_original
                if self.unmodified_original is not None
                else self.working_copy
            )
            self._write(document.storage_type, source_file, document.source_path)

            # Store thumbnail
            self._write(document.storage_type, thumbnail, document.thumbnail_path)

            # Store archive file if exists
            if archive_path and Path(archive_path).is_file():
                document.archive_filename = generate_unique_filename(
                    document,
                    archive_filename=True,
                )
                create_source_path_directory(document.archive_path)
                self._write(document.storage_type, archive_path, document.archive_path)

                # Calculate archive checksum
                with Path(archive_path).open("rb") as f:
                    document.archive_checksum = hashlib.md5(f.read()).hexdigest()

    def _cleanup_consumed_files(self) -> None:
        """
        Delete consumed files after successful processing.

        Removes the original file, working copy, unmodified original (if any),
        and shadow files created by macOS.
        """
        self.log.debug(f"Deleting original file {self.input_doc.original_file}")
        self.input_doc.original_file.unlink()

        self.log.debug(f"Deleting working copy {self.working_copy}")
        self.working_copy.unlink()

        if self.unmodified_original is not None:  # pragma: no cover
            self.log.debug(
                f"Deleting unmodified original file {self.unmodified_original}",
            )
            self.unmodified_original.unlink()

        # Delete macOS shadow file if it exists
        # https://github.com/jonaswinkler/paperless-ng/discussions/1037
        shadow_file = (
            Path(self.input_doc.original_file).parent
            / f"._{Path(self.input_doc.original_file).name}"
        )

        if Path(shadow_file).is_file():
            self.log.debug(f"Deleting shadow file {shadow_file}")
            Path(shadow_file).unlink()

    def _finalize_consumption(self, document: Document) -> str:
        """
        Finalize document consumption and send completion notification.

        Logs completion, sends success progress update, refreshes document
        from database, and returns success message.

        Args:
            document: The consumed document

        Returns:
            str: Success message with document ID
        """
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

        storage_type = Document.STORAGE_TYPE_UNENCRYPTED

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
            storage_type=storage_type,
            page_count=page_count,
            original_filename=self.filename,
        )

        self.apply_overrides(document)

        document.save()

        return document

    def apply_overrides(self, document):
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
            or self.metadata.change_groups is not None
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

    def _write(self, storage_type, source, target):
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

    def _run_ai_scanner(self, document, text):
        """
        Run AI scanner on the document to automatically detect and apply metadata.

        This is called during document consumption to leverage AI/ML capabilities
        for automatic metadata management as specified in agents.md.

        Args:
            document: The Document model instance
            text: The extracted document text
        """
        # Check if AI scanner is enabled
        if not getattr(settings, "PAPERLESS_ENABLE_AI_SCANNER", True):
            self.log.debug("AI scanner is disabled, skipping AI analysis")
            return

        try:
            from documents.ai_scanner import get_ai_scanner

            scanner = get_ai_scanner()

            # Get the original file path if available
            original_file_path = str(self.working_copy) if self.working_copy else None

            # Perform comprehensive AI scan
            self.log.info(f"Running AI scanner on document: {document.title}")
            scan_result = scanner.scan_document(
                document=document,
                document_text=text,
                original_file_path=original_file_path,
            )

            # Apply scan results (auto-apply high confidence, suggest medium confidence)
            results = scanner.apply_scan_results(
                document=document,
                scan_result=scan_result,
                auto_apply=True,  # Auto-apply high confidence suggestions
            )

            # Log what was applied and suggested
            if results["applied"]["tags"]:
                self.log.info(
                    f"AI auto-applied tags: {[t['name'] for t in results['applied']['tags']]}",
                )

            if results["applied"]["correspondent"]:
                self.log.info(
                    f"AI auto-applied correspondent: {results['applied']['correspondent']['name']}",
                )

            if results["applied"]["document_type"]:
                self.log.info(
                    f"AI auto-applied document type: {results['applied']['document_type']['name']}",
                )

            if results["applied"]["storage_path"]:
                self.log.info(
                    f"AI auto-applied storage path: {results['applied']['storage_path']['name']}",
                )

            # Log suggestions for user review
            if results["suggestions"]["tags"]:
                self.log.info(
                    f"AI suggested tags (require review): "
                    f"{[t['name'] for t in results['suggestions']['tags']]}",
                )

            if results["suggestions"]["correspondent"]:
                self.log.info(
                    f"AI suggested correspondent (requires review): "
                    f"{results['suggestions']['correspondent']['name']}",
                )

            if results["suggestions"]["document_type"]:
                self.log.info(
                    f"AI suggested document type (requires review): "
                    f"{results['suggestions']['document_type']['name']}",
                )

            if results["suggestions"]["storage_path"]:
                self.log.info(
                    f"AI suggested storage path (requires review): "
                    f"{results['suggestions']['storage_path']['name']}",
                )

            # Store suggestions in document metadata for UI to display
            # This allows the frontend to show AI suggestions to users
            if not hasattr(document, "_ai_suggestions"):
                document._ai_suggestions = results["suggestions"]

        except ImportError:
            # AI scanner not available, skip
            self.log.debug("AI scanner not available, skipping AI analysis")
        except Exception as e:
            # Don't fail the entire consumption if AI scanner fails
            self.log.warning(
                f"AI scanner failed for document {document.title}: {e}",
                exc_info=True,
            )


class ConsumerPreflightPlugin(
    NoCleanupPluginMixin,
    NoSetupPluginMixin,
    AlwaysRunPluginMixin,
    LoggingMixin,
    ConsumerPluginMixin,
    ConsumeTaskPlugin,
):
    NAME: str = "ConsumerPreflightPlugin"
    logging_name = "paperless.consumer"

    def pre_check_file_exists(self):
        """
        Confirm the input file still exists where it should
        """
        if TYPE_CHECKING:
            assert isinstance(
                self.input_doc.original_file, Path,
            ), self.input_doc.original_file
        if not self.input_doc.original_file.is_file():
            self._fail(
                ConsumerStatusShortMessage.FILE_NOT_FOUND,
                f"Cannot consume {self.input_doc.original_file}: File not found.",
            )

    def pre_check_duplicate(self):
        """
        Using the MD5 of the file, check this exact file doesn't already exist
        """
        with Path(self.input_doc.original_file).open("rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        existing_doc = Document.global_objects.filter(
            Q(checksum=checksum) | Q(archive_checksum=checksum),
        )
        if existing_doc.exists():
            msg = ConsumerStatusShortMessage.DOCUMENT_ALREADY_EXISTS
            log_msg = f"Not consuming {self.filename}: It is a duplicate of {existing_doc.get().title} (#{existing_doc.get().pk})."

            if existing_doc.first().deleted_at is not None:
                msg = ConsumerStatusShortMessage.DOCUMENT_ALREADY_EXISTS_IN_TRASH
                log_msg += " Note: existing document is in the trash."

            if settings.CONSUMER_DELETE_DUPLICATES:
                Path(self.input_doc.original_file).unlink()
            self._fail(
                msg,
                log_msg,
            )

    def pre_check_directories(self):
        """
        Ensure all required directories exist before attempting to use them
        """
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        settings.THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
        settings.ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
        settings.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    def pre_check_asn_value(self):
        """
        Check that if override_asn is given, it is unique and within a valid range
        """
        if self.metadata.asn is None:
            # check not necessary in case no ASN gets set
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
        self.pre_check_asn_value()
