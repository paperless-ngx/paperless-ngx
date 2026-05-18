import datetime
import logging
import os
import shutil
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final

import magic
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max
from django.db.models import Q
from django.utils import timezone
from filelock import FileLock
from rest_framework.reverse import reverse

from documents.classifier import load_classifier
from documents.data_models import ConsumableDocument
from documents.data_models import ConsumeFileSuccessResult
from documents.data_models import DocumentMetadataOverrides
from documents.file_handling import create_source_path_directory
from documents.file_handling import generate_filename
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
from documents.parsers import ParseError
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
from documents.signals import document_updated
from documents.signals.handlers import run_workflows
from documents.templating.workflows import parse_w_workflow_placeholders
from documents.utils import compute_checksum
from documents.utils import copy_basic_file_stats
from documents.utils import copy_file_with_basic_stats
from documents.utils import run_subprocess
from paperless.config import OcrConfig
from paperless.models import ArchiveFileGenerationChoices
from paperless.parsers import ParserContext
from paperless.parsers import ParserProtocol
from paperless.parsers.registry import get_parser_registry
from paperless.parsers.utils import PDF_TEXT_MIN_LENGTH
from paperless.parsers.utils import extract_pdf_text
from paperless.parsers.utils import is_tagged_pdf

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


class ConsumeFileDuplicateError(ConsumerError):
    """Raised when a file is rejected because it duplicates an existing document."""

    def __init__(self, message: str, duplicate_id: int, *, in_trash: bool) -> None:
        super().__init__(message)
        self.duplicate_id = duplicate_id
        self.in_trash = in_trash


class ConsumerStatusShortMessage(StrEnum):
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


def should_produce_archive(
    parser: "ParserProtocol",
    mime_type: str,
    document_path: Path,
    log: logging.Logger | None = None,
) -> bool:
    """Return True if a PDF/A archive should be produced for this document.

    IMPORTANT: *parser* must be an instantiated parser, not the class.
    ``requires_pdf_rendition`` and ``can_produce_archive`` are instance
    ``@property`` methods — accessing them on the class returns the descriptor
    (always truthy).
    """
    _log = log or logging.getLogger(LOGGING_NAME)

    # Must produce a PDF so the frontend can display the original format at all.
    if parser.requires_pdf_rendition:
        _log.debug("Archive: yes — parser requires PDF rendition for frontend display")
        return True

    # Parser cannot produce an archive (e.g. TextDocumentParser).
    if not parser.can_produce_archive:
        _log.debug("Archive: no — parser cannot produce archives")
        return False

    generation = OcrConfig().archive_file_generation

    if generation == ArchiveFileGenerationChoices.ALWAYS:
        _log.debug("Archive: yes — ARCHIVE_FILE_GENERATION=always")
        return True
    if generation == ArchiveFileGenerationChoices.NEVER:
        _log.debug("Archive: no — ARCHIVE_FILE_GENERATION=never")
        return False

    # auto: produce archives for scanned/image documents; skip for born-digital PDFs.
    if mime_type.startswith("image/"):
        _log.debug("Archive: yes — image document, ARCHIVE_FILE_GENERATION=auto")
        return True
    if mime_type == "application/pdf":
        if is_tagged_pdf(document_path):
            _log.debug(
                "Archive: no — born-digital PDF (structure tags detected),"
                " ARCHIVE_FILE_GENERATION=auto",
            )
            return False
        text = extract_pdf_text(document_path)
        if text is None or len(text) <= PDF_TEXT_MIN_LENGTH:
            _log.debug(
                "Archive: yes — scanned PDF (text_length=%d ≤ %d),"
                " ARCHIVE_FILE_GENERATION=auto",
                len(text) if text else 0,
                PDF_TEXT_MIN_LENGTH,
            )
            return True
        _log.debug(
            "Archive: no — born-digital PDF (text_length=%d > %d),"
            " ARCHIVE_FILE_GENERATION=auto",
            len(text),
            PDF_TEXT_MIN_LENGTH,
        )
        return False
    _log.debug(
        "Archive: no — MIME type %r not eligible for auto archive generation",
        mime_type,
    )
    return False


class ConsumerPluginMixin:
    if TYPE_CHECKING:
        from logging import Logger
        from logging import LoggerAdapter

        log: "LoggerAdapter"  # type: ignore[type-arg]

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
            document_id=document_id,
            owner_id=self.metadata.owner_id if self.metadata.owner_id else None,
            users_can_view=(self.metadata.view_users or [])
            + (self.metadata.change_users or []),
            groups_can_view=(self.metadata.view_groups or [])
            + (self.metadata.change_groups or []),
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

    def _create_version_from_root(
        self,
        root_doc: Document,
        *,
        text: str | None,
        page_count: int | None,
        mime_type: str,
    ) -> Document:
        self.log.debug("Saving record for updated version to database")
        root_doc_frozen = Document.objects.select_for_update().get(pk=root_doc.pk)
        next_version_index = (
            Document.global_objects.filter(
                root_document_id=root_doc_frozen.pk,
            ).aggregate(
                max_index=Max("version_index"),
            )["max_index"]
            or 0
        )
        file_for_checksum = (
            self.unmodified_original
            if self.unmodified_original is not None
            else self.working_copy
        )
        version_doc = Document(
            root_document=root_doc_frozen,
            version_index=next_version_index + 1,
            checksum=compute_checksum(file_for_checksum),
            content=text or "",
            page_count=page_count,
            mime_type=mime_type,
            original_filename=self.filename,
            owner_id=root_doc_frozen.owner_id,
            created=root_doc_frozen.created,
            title=root_doc_frozen.title,
            added=timezone.now(),
            modified=timezone.now(),
        )
        if self.metadata.version_label is not None:
            version_doc.version_label = self.metadata.version_label
        return version_doc

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

    def run(self) -> "ConsumeFileSuccessResult":
        """
        Return the document object if it was successfully created.
        """

        # Preflight has already run including progress update to 0%
        self.log.info(f"Consuming {self.filename}")

        # For the actual work, copy the file into a tempdir
        with tempfile.TemporaryDirectory(
            prefix="paperless-ngx",
            dir=settings.SCRATCH_DIR,
        ) as tmpdir:
            self.working_copy = Path(tmpdir) / Path(self.filename)
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
                        Path(tmpdir) / Path("uo") / Path(self.filename)
                    )
                    self.unmodified_original.parent.mkdir(exist_ok=True)
                    copy_file_with_basic_stats(
                        self.input_doc.original_file,
                        self.unmodified_original,
                    )
                except Exception as e:
                    self.log.error(f"Error attempting to clean PDF: {e}")

            # Based on the mime type, get the parser for that type
            parser_class: type[ParserProtocol] | None = (
                get_parser_registry().get_parser_for_file(
                    mime_type,
                    self.filename,
                    self.working_copy,
                )
            )
            if not parser_class:
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

            # This doesn't parse the document yet, but gives us a parser.
            with parser_class() as document_parser:
                document_parser.configure(
                    ParserContext(mailrule_id=self.input_doc.mailrule_id),
                )

                self.log.debug(
                    f"Parser: {document_parser.name} v{document_parser.version}",
                )

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

                    produce_archive = should_produce_archive(
                        document_parser,
                        mime_type,
                        self.working_copy,
                        self.log,
                    )
                    document_parser.parse(
                        self.working_copy,
                        mime_type,
                        produce_archive=produce_archive,
                    )

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
                    page_count = document_parser.get_page_count(
                        self.working_copy,
                        mime_type,
                    )

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
                        if self.input_doc.root_document_id:
                            # If this is a new version of an existing document, we need
                            # to make sure we're not creating a new document, but updating
                            # the existing one.
                            root_doc = Document.objects.get(
                                pk=self.input_doc.root_document_id,
                            )
                            original_document = self._create_version_from_root(
                                root_doc,
                                text=text,
                                page_count=page_count,
                                mime_type=mime_type,
                            )
                            actor = None

                            # Save the new version, potentially creating an audit log entry for the version addition if enabled.
                            if (
                                settings.AUDIT_LOG_ENABLED
                                and self.metadata.actor_id is not None
                            ):
                                actor = User.objects.filter(
                                    pk=self.metadata.actor_id,
                                ).first()
                                if actor is not None:
                                    from auditlog.context import (  # type: ignore[import-untyped]
                                        set_actor,
                                    )

                                    with set_actor(actor):
                                        original_document.save()
                                else:
                                    original_document.save()
                            else:
                                original_document.save()

                            # Create a log entry for the version addition, if enabled
                            if settings.AUDIT_LOG_ENABLED:
                                from auditlog.models import (  # type: ignore[import-untyped]
                                    LogEntry,
                                )

                                LogEntry.objects.log_create(
                                    instance=root_doc,
                                    changes={
                                        "Version Added": ["None", original_document.id],
                                    },
                                    action=LogEntry.Action.UPDATE,
                                    actor=actor,
                                    additional_data={
                                        "reason": "Version added",
                                        "version_id": original_document.id,
                                    },
                                )
                            document = original_document
                        else:
                            document = self._store(
                                text=text,
                                date=date,
                                page_count=page_count,
                                mime_type=mime_type,
                            )

                        # If we get here, it was successful. Proceed with post-consume
                        # hooks. If they fail, nothing will get changed.

                        document = Document.objects.prefetch_related("versions").get(
                            pk=document.pk,
                        )

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
                            generated_filename = generate_unique_filename(document)
                            if (
                                len(str(generated_filename))
                                > Document.MAX_STORED_FILENAME_LENGTH
                            ):
                                self.log.warning(
                                    "Generated source filename exceeds db path limit, falling back to default naming",
                                )
                                generated_filename = generate_filename(
                                    document,
                                    use_format=False,
                                )
                            document.filename = generated_filename
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
                                generated_archive_filename = generate_unique_filename(
                                    document,
                                    archive_filename=True,
                                )
                                if (
                                    len(str(generated_archive_filename))
                                    > Document.MAX_STORED_FILENAME_LENGTH
                                ):
                                    self.log.warning(
                                        "Generated archive filename exceeds db path limit, falling back to default naming",
                                    )
                                    generated_archive_filename = generate_filename(
                                        document,
                                        archive_filename=True,
                                        use_format=False,
                                    )
                                document.archive_filename = generated_archive_filename
                                create_source_path_directory(document.archive_path)
                                self._write(
                                    archive_path,
                                    document.archive_path,
                                )

                                document.archive_checksum = compute_checksum(
                                    document.archive_path,
                                )

                        # Don't save with the lock active. Saving will cause the file
                        # renaming logic to acquire the lock as well.
                        # This triggers things like file renaming
                        document.save()

                        if document.root_document_id:
                            document_updated.send(
                                sender=self.__class__,
                                document=document.root_document,
                            )

                        # Delete the file only if it was successfully consumed
                        self.log.debug(
                            f"Deleting original file {self.input_doc.original_file}",
                        )
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

        return ConsumeFileSuccessResult(document_id=document.pk)

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
            checksum=compute_checksum(file_for_checksum),
            created=create_date,
            modified=create_date,
            page_count=page_count,
            original_filename=self.filename,
        )

        self.apply_overrides(document)

        document.save()

        return document

    def apply_overrides(self, document: Document) -> None:
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

        if self.metadata.version_label is not None:
            document.version_label = self.metadata.version_label

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

    def _write(self, source, target) -> None:
        with (
            Path(source).open("rb") as read_file,
            Path(target).open("wb") as write_file,
        ):
            shutil.copyfileobj(read_file, write_file)

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
        Using the SHA256 of the file, check this exact file doesn't already exist
        """
        checksum = compute_checksum(Path(self.input_doc.original_file))
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

                self._send_progress(100, 100, ProgressStatusOptions.FAILED, status_msg)
                self.log.error(failure_msg)
                in_trash = duplicates_in_trash.exists()
                raise ConsumeFileDuplicateError(
                    f"{self.filename}: {failure_msg}",
                    duplicate.pk,
                    in_trash=in_trash,
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
