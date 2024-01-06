import datetime
import hashlib
import os
import tempfile
import uuid
from enum import Enum
from pathlib import Path
from subprocess import CompletedProcess
from subprocess import run
from typing import Optional

import magic
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
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
from documents.matching import document_matches_workflow
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import FileInfo
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowTrigger
from documents.parsers import DocumentParser
from documents.parsers import ParseError
from documents.parsers import get_parser_class_for_mime_type
from documents.parsers import parse_date
from documents.permissions import set_permissions_for_object
from documents.signals import document_consumption_finished
from documents.signals import document_consumption_started
from documents.utils import copy_basic_file_stats
from documents.utils import copy_file_with_basic_stats


class ConsumerError(Exception):
    pass


class ConsumerStatusShortMessage(str, Enum):
    DOCUMENT_ALREADY_EXISTS = "document_already_exists"
    ASN_ALREADY_EXISTS = "asn_already_exists"
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


class ConsumerFilePhase(str, Enum):
    STARTED = "STARTED"
    WORKING = "WORKING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Consumer(LoggingMixin):
    logging_name = "paperless.consumer"

    def _send_progress(
        self,
        current_progress: int,
        max_progress: int,
        status: ConsumerFilePhase,
        message: Optional[ConsumerStatusShortMessage] = None,
        document_id=None,
    ):  # pragma: no cover
        payload = {
            "filename": os.path.basename(self.filename) if self.filename else None,
            "task_id": self.task_id,
            "current_progress": current_progress,
            "max_progress": max_progress,
            "status": status,
            "message": message,
            "document_id": document_id,
            "owner_id": self.override_owner_id if self.override_owner_id else None,
        }
        async_to_sync(self.channel_layer.group_send)(
            "status_updates",
            {"type": "status_update", "data": payload},
        )

    def _fail(
        self,
        message: ConsumerStatusShortMessage,
        log_message: Optional[str] = None,
        exc_info=None,
        exception: Optional[Exception] = None,
    ):
        self._send_progress(100, 100, ConsumerFilePhase.FAILED, message)
        self.log.error(log_message or message, exc_info=exc_info)
        raise ConsumerError(f"{self.filename}: {log_message or message}") from exception

    def __init__(self):
        super().__init__()
        self.path: Optional[Path] = None
        self.original_path: Optional[Path] = None
        self.filename = None
        self.override_title = None
        self.override_correspondent_id = None
        self.override_tag_ids = None
        self.override_document_type_id = None
        self.override_asn = None
        self.task_id = None
        self.override_owner_id = None
        self.override_custom_field_ids = None

        self.channel_layer = get_channel_layer()

    def pre_check_file_exists(self):
        """
        Confirm the input file still exists where it should
        """
        if not os.path.isfile(self.original_path):
            self._fail(
                ConsumerStatusShortMessage.FILE_NOT_FOUND,
                f"Cannot consume {self.original_path}: File not found.",
            )

    def pre_check_duplicate(self):
        """
        Using the MD5 of the file, check this exact file doesn't already exist
        """
        with open(self.original_path, "rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        existing_doc = Document.objects.filter(
            Q(checksum=checksum) | Q(archive_checksum=checksum),
        )
        if existing_doc.exists():
            if settings.CONSUMER_DELETE_DUPLICATES:
                os.unlink(self.original_path)
            self._fail(
                ConsumerStatusShortMessage.DOCUMENT_ALREADY_EXISTS,
                f"Not consuming {self.filename}: It is a duplicate of"
                f" {existing_doc.get().title} (#{existing_doc.get().pk})",
            )

    def pre_check_directories(self):
        """
        Ensure all required directories exist before attempting to use them
        """
        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)
        os.makedirs(settings.THUMBNAIL_DIR, exist_ok=True)
        os.makedirs(settings.ORIGINALS_DIR, exist_ok=True)
        os.makedirs(settings.ARCHIVE_DIR, exist_ok=True)

    def pre_check_asn_value(self):
        """
        Check that if override_asn is given, it is unique and within a valid range
        """
        if not self.override_asn:
            # check not necessary in case no ASN gets set
            return
        # Validate the range is above zero and less than uint32_t max
        # otherwise, Whoosh can't handle it in the index
        if (
            self.override_asn < Document.ARCHIVE_SERIAL_NUMBER_MIN
            or self.override_asn > Document.ARCHIVE_SERIAL_NUMBER_MAX
        ):
            self._fail(
                ConsumerStatusShortMessage.ASN_RANGE,
                f"Not consuming {self.filename}: "
                f"Given ASN {self.override_asn} is out of range "
                f"[{Document.ARCHIVE_SERIAL_NUMBER_MIN:,}, "
                f"{Document.ARCHIVE_SERIAL_NUMBER_MAX:,}]",
            )
        if Document.objects.filter(archive_serial_number=self.override_asn).exists():
            self._fail(
                ConsumerStatusShortMessage.ASN_ALREADY_EXISTS,
                f"Not consuming {self.filename}: Given ASN already exists!",
            )

    def run_pre_consume_script(self):
        """
        If one is configured and exists, run the pre-consume script and
        handle its output and/or errors
        """
        if not settings.PRE_CONSUME_SCRIPT:
            return

        if not os.path.isfile(settings.PRE_CONSUME_SCRIPT):
            self._fail(
                ConsumerStatusShortMessage.PRE_CONSUME_SCRIPT_NOT_FOUND,
                f"Configured pre-consume script "
                f"{settings.PRE_CONSUME_SCRIPT} does not exist.",
            )

        self.log.info(f"Executing pre-consume script {settings.PRE_CONSUME_SCRIPT}")

        working_file_path = str(self.working_copy)
        original_file_path = str(self.original_path)

        script_env = os.environ.copy()
        script_env["DOCUMENT_SOURCE_PATH"] = original_file_path
        script_env["DOCUMENT_WORKING_PATH"] = working_file_path
        script_env["TASK_ID"] = self.task_id or ""

        try:
            completed_proc = run(
                args=[
                    settings.PRE_CONSUME_SCRIPT,
                    original_file_path,
                ],
                env=script_env,
                capture_output=True,
            )

            self._log_script_outputs(completed_proc)

            # Raises exception on non-zero output
            completed_proc.check_returncode()

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

        if not os.path.isfile(settings.POST_CONSUME_SCRIPT):
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
        script_env["DOCUMENT_CORRESPONDENT"] = str(document.correspondent)
        script_env["DOCUMENT_TAGS"] = str(
            ",".join(document.tags.all().values_list("name", flat=True)),
        )
        script_env["DOCUMENT_ORIGINAL_FILENAME"] = str(document.original_filename)
        script_env["TASK_ID"] = self.task_id or ""

        try:
            completed_proc = run(
                args=[
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
                env=script_env,
                capture_output=True,
            )

            self._log_script_outputs(completed_proc)

            # Raises exception on non-zero output
            completed_proc.check_returncode()

        except Exception as e:
            self._fail(
                ConsumerStatusShortMessage.POST_CONSUME_SCRIPT_ERROR,
                f"Error while executing post-consume script: {e}",
                exc_info=True,
                exception=e,
            )

    def try_consume_file(
        self,
        path: Path,
        override_filename=None,
        override_title=None,
        override_correspondent_id=None,
        override_document_type_id=None,
        override_tag_ids=None,
        override_storage_path_id=None,
        task_id=None,
        override_created=None,
        override_asn=None,
        override_owner_id=None,
        override_view_users=None,
        override_view_groups=None,
        override_change_users=None,
        override_change_groups=None,
        override_custom_field_ids=None,
    ) -> Document:
        """
        Return the document object if it was successfully created.
        """

        self.original_path = Path(path).resolve()
        self.filename = override_filename or self.original_path.name
        self.override_title = override_title
        self.override_correspondent_id = override_correspondent_id
        self.override_document_type_id = override_document_type_id
        self.override_tag_ids = override_tag_ids
        self.override_storage_path_id = override_storage_path_id
        self.task_id = task_id or str(uuid.uuid4())
        self.override_created = override_created
        self.override_asn = override_asn
        self.override_owner_id = override_owner_id
        self.override_view_users = override_view_users
        self.override_view_groups = override_view_groups
        self.override_change_users = override_change_users
        self.override_change_groups = override_change_groups
        self.override_custom_field_ids = override_custom_field_ids

        self._send_progress(
            0,
            100,
            ConsumerFilePhase.STARTED,
            ConsumerStatusShortMessage.NEW_FILE,
        )

        # Make sure that preconditions for consuming the file are met.

        self.pre_check_file_exists()
        self.pre_check_directories()
        self.pre_check_duplicate()
        self.pre_check_asn_value()

        self.log.info(f"Consuming {self.filename}")

        # For the actual work, copy the file into a tempdir
        tempdir = tempfile.TemporaryDirectory(
            prefix="paperless-ngx",
            dir=settings.SCRATCH_DIR,
        )
        self.working_copy = Path(tempdir.name) / Path(self.filename)
        copy_file_with_basic_stats(self.original_path, self.working_copy)

        # Determine the parser class.

        mime_type = magic.from_file(self.working_copy, mime=True)

        self.log.debug(f"Detected mime type: {mime_type}")

        # Based on the mime type, get the parser for that type
        parser_class: Optional[type[DocumentParser]] = get_parser_class_for_mime_type(
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

        def progress_callback(current_progress, max_progress):  # pragma: no cover
            # recalculate progress to be within 20 and 80
            p = int((current_progress / max_progress) * 50 + 20)
            self._send_progress(p, 100, ConsumerFilePhase.WORKING)

        # This doesn't parse the document yet, but gives us a parser.

        document_parser: DocumentParser = parser_class(
            self.logging_group,
            progress_callback=progress_callback,
        )

        self.log.debug(f"Parser: {type(document_parser).__name__}")

        # However, this already created working directories which we have to
        # clean up.

        # Parse the document. This may take some time.

        text = None
        date = None
        thumbnail = None
        archive_path = None

        try:
            self._send_progress(
                20,
                100,
                ConsumerFilePhase.WORKING,
                ConsumerStatusShortMessage.PARSING_DOCUMENT,
            )
            self.log.debug(f"Parsing {self.filename}...")
            document_parser.parse(self.working_copy, mime_type, self.filename)

            self.log.debug(f"Generating thumbnail for {self.filename}...")
            self._send_progress(
                70,
                100,
                ConsumerFilePhase.WORKING,
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
                    ConsumerFilePhase.WORKING,
                    ConsumerStatusShortMessage.PARSE_DATE,
                )
                date = parse_date(self.filename, text)
            archive_path = document_parser.get_archive_path()

        except ParseError as e:
            self._fail(
                str(e),
                f"Error occurred while consuming document {self.filename}: {e}",
                exc_info=True,
                exception=e,
            )
        except Exception as e:
            document_parser.cleanup()
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
            ConsumerFilePhase.WORKING,
            ConsumerStatusShortMessage.SAVE_DOCUMENT,
        )
        # now that everything is done, we can start to store the document
        # in the system. This will be a transaction and reasonably fast.
        try:
            with transaction.atomic():
                # store the document.
                document = self._store(text=text, date=date, mime_type=mime_type)

                # If we get here, it was successful. Proceed with post-consume
                # hooks. If they fail, nothing will get changed.

                document_consumption_finished.send(
                    sender=self.__class__,
                    document=document,
                    logging_group=self.logging_group,
                    classifier=classifier,
                )

                # After everything is in the database, copy the files into
                # place. If this fails, we'll also rollback the transaction.
                with FileLock(settings.MEDIA_LOCK):
                    document.filename = generate_unique_filename(document)
                    create_source_path_directory(document.source_path)

                    self._write(
                        document.storage_type,
                        self.working_copy,
                        document.source_path,
                    )

                    self._write(
                        document.storage_type,
                        thumbnail,
                        document.thumbnail_path,
                    )

                    if archive_path and os.path.isfile(archive_path):
                        document.archive_filename = generate_unique_filename(
                            document,
                            archive_filename=True,
                        )
                        create_source_path_directory(document.archive_path)
                        self._write(
                            document.storage_type,
                            archive_path,
                            document.archive_path,
                        )

                        with open(archive_path, "rb") as f:
                            document.archive_checksum = hashlib.md5(
                                f.read(),
                            ).hexdigest()

                # Don't save with the lock active. Saving will cause the file
                # renaming logic to acquire the lock as well.
                # This triggers things like file renaming
                document.save()

                # Delete the file only if it was successfully consumed
                self.log.debug(f"Deleting file {self.working_copy}")
                self.original_path.unlink()
                self.working_copy.unlink()

                # https://github.com/jonaswinkler/paperless-ng/discussions/1037
                shadow_file = os.path.join(
                    os.path.dirname(self.original_path),
                    "._" + os.path.basename(self.original_path),
                )

                if os.path.isfile(shadow_file):
                    self.log.debug(f"Deleting file {shadow_file}")
                    os.unlink(shadow_file)

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
            ConsumerFilePhase.SUCCESS,
            ConsumerStatusShortMessage.FINISHED,
            document.id,
        )

        # Return the most up to date fields
        document.refresh_from_db()

        return document

    def get_workflow_overrides(
        self,
        input_doc: ConsumableDocument,
    ) -> DocumentMetadataOverrides:
        """
        Get overrides from matching workflows
        """
        overrides = DocumentMetadataOverrides()
        for workflow in Workflow.objects.filter(enabled=True).order_by("order"):
            template_overrides = DocumentMetadataOverrides()

            if document_matches_workflow(
                input_doc,
                workflow,
                WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            ):
                for action in workflow.actions.all():
                    self.log.info(
                        f"Applying overrides in {action} from {workflow}",
                    )
                    if action.assign_title is not None:
                        template_overrides.title = action.assign_title
                    if action.assign_tags is not None:
                        template_overrides.tag_ids = [
                            tag.pk for tag in action.assign_tags.all()
                        ]
                    if action.assign_correspondent is not None:
                        template_overrides.correspondent_id = (
                            action.assign_correspondent.pk
                        )
                    if action.assign_document_type is not None:
                        template_overrides.document_type_id = (
                            action.assign_document_type.pk
                        )
                    if action.assign_storage_path is not None:
                        template_overrides.storage_path_id = (
                            action.assign_storage_path.pk
                        )
                    if action.assign_owner is not None:
                        template_overrides.owner_id = action.assign_owner.pk
                    if action.assign_view_users is not None:
                        template_overrides.view_users = [
                            user.pk for user in action.assign_view_users.all()
                        ]
                    if action.assign_view_groups is not None:
                        template_overrides.view_groups = [
                            group.pk for group in action.assign_view_groups.all()
                        ]
                    if action.assign_change_users is not None:
                        template_overrides.change_users = [
                            user.pk for user in action.assign_change_users.all()
                        ]
                    if action.assign_change_groups is not None:
                        template_overrides.change_groups = [
                            group.pk for group in action.assign_change_groups.all()
                        ]
                    if action.assign_custom_fields is not None:
                        template_overrides.custom_field_ids = [
                            field.pk for field in action.assign_custom_fields.all()
                        ]

                    overrides.update(template_overrides)
        return overrides

    def _parse_title_placeholders(self, title: str) -> str:
        local_added = timezone.localtime(timezone.now())

        correspondent_name = (
            Correspondent.objects.get(pk=self.override_correspondent_id).name
            if self.override_correspondent_id is not None
            else None
        )
        doc_type_name = (
            DocumentType.objects.get(pk=self.override_document_type_id).name
            if self.override_document_type_id is not None
            else None
        )
        owner_username = (
            User.objects.get(pk=self.override_owner_id).username
            if self.override_owner_id is not None
            else None
        )

        return parse_doc_title_w_placeholders(
            title,
            correspondent_name,
            doc_type_name,
            owner_username,
            local_added,
            self.filename,
        )

    def _store(
        self,
        text: str,
        date: Optional[datetime.datetime],
        mime_type: str,
    ) -> Document:
        # If someone gave us the original filename, use it instead of doc.

        file_info = FileInfo.from_filename(self.filename)

        self.log.debug("Saving record to database")

        if self.override_created is not None:
            create_date = self.override_created
            self.log.debug(
                f"Creation date from post_documents parameter: {create_date}",
            )
        elif file_info.created is not None:
            create_date = file_info.created
            self.log.debug(f"Creation date from FileInfo: {create_date}")
        elif date is not None:
            create_date = date
            self.log.debug(f"Creation date from parse_date: {create_date}")
        else:
            stats = os.stat(self.original_path)
            create_date = timezone.make_aware(
                datetime.datetime.fromtimestamp(stats.st_mtime),
            )
            self.log.debug(f"Creation date from st_mtime: {create_date}")

        storage_type = Document.STORAGE_TYPE_UNENCRYPTED

        document = Document.objects.create(
            title=(
                self._parse_title_placeholders(self.override_title)
                if self.override_title is not None
                else file_info.title
            )[:127],
            content=text,
            mime_type=mime_type,
            checksum=hashlib.md5(self.working_copy.read_bytes()).hexdigest(),
            created=create_date,
            modified=create_date,
            storage_type=storage_type,
            original_filename=self.filename,
        )

        self.apply_overrides(document)

        document.save()

        return document

    def apply_overrides(self, document):
        if self.override_correspondent_id:
            document.correspondent = Correspondent.objects.get(
                pk=self.override_correspondent_id,
            )

        if self.override_document_type_id:
            document.document_type = DocumentType.objects.get(
                pk=self.override_document_type_id,
            )

        if self.override_tag_ids:
            for tag_id in self.override_tag_ids:
                document.tags.add(Tag.objects.get(pk=tag_id))

        if self.override_storage_path_id:
            document.storage_path = StoragePath.objects.get(
                pk=self.override_storage_path_id,
            )

        if self.override_asn:
            document.archive_serial_number = self.override_asn

        if self.override_owner_id:
            document.owner = User.objects.get(
                pk=self.override_owner_id,
            )

        if (
            self.override_view_users is not None
            or self.override_view_groups is not None
            or self.override_change_users is not None
            or self.override_change_users is not None
        ):
            permissions = {
                "view": {
                    "users": self.override_view_users or [],
                    "groups": self.override_view_groups or [],
                },
                "change": {
                    "users": self.override_change_users or [],
                    "groups": self.override_change_groups or [],
                },
            }
            set_permissions_for_object(permissions=permissions, object=document)

        if self.override_custom_field_ids:
            for field_id in self.override_custom_field_ids:
                field = CustomField.objects.get(pk=field_id)
                CustomFieldInstance.objects.create(
                    field=field,
                    document=document,
                )  # adds to document

    def _write(self, storage_type, source, target):
        with open(source, "rb") as read_file, open(target, "wb") as write_file:
            write_file.write(read_file.read())

        # Attempt to copy file's original stats, but it's ok if we can't
        try:
            copy_basic_file_stats(source, target)
        except Exception:  # pragma: no cover
            pass

    def _log_script_outputs(self, completed_process: CompletedProcess):
        """
        Decodes a process stdout and stderr streams and logs them to the main log
        """
        # Log what the script exited as
        self.log.info(
            f"{completed_process.args[0]} exited {completed_process.returncode}",
        )

        # Decode the output (if any)
        if len(completed_process.stdout):
            stdout_str = (
                completed_process.stdout.decode("utf8", errors="ignore")
                .strip()
                .split(
                    "\n",
                )
            )
            self.log.info("Script stdout:")
            for line in stdout_str:
                self.log.info(line)

        if len(completed_process.stderr):
            stderr_str = (
                completed_process.stderr.decode("utf8", errors="ignore")
                .strip()
                .split(
                    "\n",
                )
            )

            self.log.warning("Script stderr:")
            for line in stderr_str:
                self.log.warning(line)


def parse_doc_title_w_placeholders(
    title: str,
    correspondent_name: str,
    doc_type_name: str,
    owner_username: str,
    local_added: datetime.datetime,
    original_filename: str,
    created: Optional[datetime.datetime] = None,
) -> str:
    """
    Available title placeholders for Workflows depend on what has already been assigned,
    e.g. for pre-consumption triggers created will not have been parsed yet, but it will
    for added / updated triggers
    """
    formatting = {
        "correspondent": correspondent_name,
        "document_type": doc_type_name,
        "added": local_added.isoformat(),
        "added_year": local_added.strftime("%Y"),
        "added_year_short": local_added.strftime("%y"),
        "added_month": local_added.strftime("%m"),
        "added_month_name": local_added.strftime("%B"),
        "added_month_name_short": local_added.strftime("%b"),
        "added_day": local_added.strftime("%d"),
        "added_time": local_added.strftime("%H:%M"),
        "owner_username": owner_username,
        "original_filename": Path(original_filename).stem,
    }
    if created is not None:
        formatting.update(
            {
                "created": created.isoformat(),
                "created_year": created.strftime("%Y"),
                "created_year_short": created.strftime("%y"),
                "created_month": created.strftime("%m"),
                "created_month_name": created.strftime("%B"),
                "created_month_name_short": created.strftime("%b"),
                "created_day": created.strftime("%d"),
                "created_time": created.strftime("%H:%M"),
            },
        )
    return title.format(**formatting).strip()
