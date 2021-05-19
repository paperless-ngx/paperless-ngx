import datetime
import hashlib
import os
import uuid
from subprocess import Popen

import magic
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from filelock import FileLock
from rest_framework.reverse import reverse

from .classifier import load_classifier
from .file_handling import create_source_path_directory, \
    generate_unique_filename
from .loggers import LoggingMixin
from .models import Document, FileInfo, Correspondent, DocumentType, Tag
from .parsers import ParseError, get_parser_class_for_mime_type, parse_date
from .signals import (
    document_consumption_finished,
    document_consumption_started
)


class ConsumerError(Exception):
    pass


MESSAGE_DOCUMENT_ALREADY_EXISTS = "document_already_exists"
MESSAGE_FILE_NOT_FOUND = "file_not_found"
MESSAGE_PRE_CONSUME_SCRIPT_NOT_FOUND = "pre_consume_script_not_found"
MESSAGE_PRE_CONSUME_SCRIPT_ERROR = "pre_consume_script_error"
MESSAGE_POST_CONSUME_SCRIPT_NOT_FOUND = "post_consume_script_not_found"
MESSAGE_POST_CONSUME_SCRIPT_ERROR = "post_consume_script_error"
MESSAGE_NEW_FILE = "new_file"
MESSAGE_UNSUPPORTED_TYPE = "unsupported_type"
MESSAGE_PARSING_DOCUMENT = "parsing_document"
MESSAGE_GENERATING_THUMBNAIL = "generating_thumbnail"
MESSAGE_PARSE_DATE = "parse_date"
MESSAGE_SAVE_DOCUMENT = "save_document"
MESSAGE_FINISHED = "finished"


class Consumer(LoggingMixin):

    logging_name = "paperless.consumer"

    def _send_progress(self, current_progress, max_progress, status,
                       message=None, document_id=None):
        payload = {
            'filename': os.path.basename(self.filename) if self.filename else None,  # NOQA: E501
            'task_id': self.task_id,
            'current_progress': current_progress,
            'max_progress': max_progress,
            'status': status,
            'message': message,
            'document_id': document_id
        }
        async_to_sync(self.channel_layer.group_send)("status_updates",
                                                     {'type': 'status_update',
                                                      'data': payload})

    def _fail(self, message, log_message=None, exc_info=None):
        self._send_progress(100, 100, 'FAILED', message)
        self.log("error", log_message or message, exc_info=exc_info)
        raise ConsumerError(f"{self.filename}: {log_message or message}")

    def __init__(self):
        super().__init__()
        self.path = None
        self.filename = None
        self.override_title = None
        self.override_correspondent_id = None
        self.override_tag_ids = None
        self.override_document_type_id = None
        self.task_id = None

        self.channel_layer = get_channel_layer()

    def pre_check_file_exists(self):
        if not os.path.isfile(self.path):
            self._fail(
                MESSAGE_FILE_NOT_FOUND,
                f"Cannot consume {self.path}: File not found."
            )

    def pre_check_duplicate(self):
        with open(self.path, "rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        if Document.objects.filter(Q(checksum=checksum) | Q(archive_checksum=checksum)).exists():  # NOQA: E501
            if settings.CONSUMER_DELETE_DUPLICATES:
                os.unlink(self.path)
            self._fail(
                MESSAGE_DOCUMENT_ALREADY_EXISTS,
                f"Not consuming {self.filename}: It is a duplicate."
            )

    def pre_check_directories(self):
        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)
        os.makedirs(settings.THUMBNAIL_DIR, exist_ok=True)
        os.makedirs(settings.ORIGINALS_DIR, exist_ok=True)
        os.makedirs(settings.ARCHIVE_DIR, exist_ok=True)

    def run_pre_consume_script(self):
        if not settings.PRE_CONSUME_SCRIPT:
            return

        if not os.path.isfile(settings.PRE_CONSUME_SCRIPT):
            self._fail(
                MESSAGE_PRE_CONSUME_SCRIPT_NOT_FOUND,
                f"Configured pre-consume script "
                f"{settings.PRE_CONSUME_SCRIPT} does not exist.")

        self.log("info",
                 f"Executing pre-consume script {settings.PRE_CONSUME_SCRIPT}")

        try:
            Popen((settings.PRE_CONSUME_SCRIPT, self.path)).wait()
        except Exception as e:
            self._fail(
                MESSAGE_PRE_CONSUME_SCRIPT_ERROR,
                f"Error while executing pre-consume script: {e}",
                exc_info=True
            )

    def run_post_consume_script(self, document):
        if not settings.POST_CONSUME_SCRIPT:
            return

        if not os.path.isfile(settings.POST_CONSUME_SCRIPT):
            self._fail(
                MESSAGE_POST_CONSUME_SCRIPT_NOT_FOUND,
                f"Configured post-consume script "
                f"{settings.POST_CONSUME_SCRIPT} does not exist."
            )

        self.log(
            "info",
            f"Executing post-consume script {settings.POST_CONSUME_SCRIPT}"
        )

        try:
            Popen((
                settings.POST_CONSUME_SCRIPT,
                str(document.pk),
                document.get_public_filename(),
                os.path.normpath(document.source_path),
                os.path.normpath(document.thumbnail_path),
                reverse("document-download", kwargs={"pk": document.pk}),
                reverse("document-thumb", kwargs={"pk": document.pk}),
                str(document.correspondent),
                str(",".join(document.tags.all().values_list(
                    "name", flat=True)))
            )).wait()
        except Exception as e:
            self._fail(
                MESSAGE_POST_CONSUME_SCRIPT_ERROR,
                f"Error while executing post-consume script: {e}",
                exc_info=True
            )

    def try_consume_file(self,
                         path,
                         override_filename=None,
                         override_title=None,
                         override_correspondent_id=None,
                         override_document_type_id=None,
                         override_tag_ids=None,
                         task_id=None):
        """
        Return the document object if it was successfully created.
        """

        self.path = path
        self.filename = override_filename or os.path.basename(path)
        self.override_title = override_title
        self.override_correspondent_id = override_correspondent_id
        self.override_document_type_id = override_document_type_id
        self.override_tag_ids = override_tag_ids
        self.task_id = task_id or str(uuid.uuid4())

        self._send_progress(0, 100, 'STARTING', MESSAGE_NEW_FILE)

        # this is for grouping logging entries for this particular file
        # together.

        self.renew_logging_group()

        # Make sure that preconditions for consuming the file are met.

        self.pre_check_file_exists()
        self.pre_check_directories()
        self.pre_check_duplicate()

        self.log("info", f"Consuming {self.filename}")

        # Determine the parser class.

        mime_type = magic.from_file(self.path, mime=True)

        self.log("debug", f"Detected mime type: {mime_type}")

        parser_class = get_parser_class_for_mime_type(mime_type)
        if not parser_class:
            self._fail(
                MESSAGE_UNSUPPORTED_TYPE,
                f"Unsupported mime type {mime_type}"
            )

        # Notify all listeners that we're going to do some work.

        document_consumption_started.send(
            sender=self.__class__,
            filename=self.path,
            logging_group=self.logging_group
        )

        self.run_pre_consume_script()

        def progress_callback(current_progress, max_progress):
            # recalculate progress to be within 20 and 80
            p = int((current_progress / max_progress) * 50 + 20)
            self._send_progress(p, 100, "WORKING")

        # This doesn't parse the document yet, but gives us a parser.

        document_parser = parser_class(self.logging_group, progress_callback)

        self.log("debug", f"Parser: {type(document_parser).__name__}")

        # However, this already created working directories which we have to
        # clean up.

        # Parse the document. This may take some time.

        text = None
        date = None
        thumbnail = None
        archive_path = None

        try:
            self._send_progress(20, 100, 'WORKING', MESSAGE_PARSING_DOCUMENT)
            self.log("debug", "Parsing {}...".format(self.filename))
            document_parser.parse(self.path, mime_type, self.filename)

            self.log("debug", f"Generating thumbnail for {self.filename}...")
            self._send_progress(70, 100, 'WORKING',
                                MESSAGE_GENERATING_THUMBNAIL)
            thumbnail = document_parser.get_optimised_thumbnail(
                self.path, mime_type, self.filename)

            text = document_parser.get_text()
            date = document_parser.get_date()
            if not date:
                self._send_progress(90, 100, 'WORKING',
                                    MESSAGE_PARSE_DATE)
                date = parse_date(self.filename, text)
            archive_path = document_parser.get_archive_path()

        except ParseError as e:
            document_parser.cleanup()
            self._fail(
                str(e),
                f"Error while consuming document {self.filename}: {e}",
                exc_info=True
            )

        # Prepare the document classifier.

        # TODO: I don't really like to do this here, but this way we avoid
        #   reloading the classifier multiple times, since there are multiple
        #   post-consume hooks that all require the classifier.

        classifier = load_classifier()

        self._send_progress(95, 100, 'WORKING', MESSAGE_SAVE_DOCUMENT)
        # now that everything is done, we can start to store the document
        # in the system. This will be a transaction and reasonably fast.
        try:
            with transaction.atomic():

                # store the document.
                document = self._store(
                    text=text,
                    date=date,
                    mime_type=mime_type
                )

                # If we get here, it was successful. Proceed with post-consume
                # hooks. If they fail, nothing will get changed.

                document_consumption_finished.send(
                    sender=self.__class__,
                    document=document,
                    logging_group=self.logging_group,
                    classifier=classifier
                )

                # After everything is in the database, copy the files into
                # place. If this fails, we'll also rollback the transaction.
                with FileLock(settings.MEDIA_LOCK):
                    document.filename = generate_unique_filename(document)
                    create_source_path_directory(document.source_path)

                    self._write(document.storage_type,
                                self.path, document.source_path)

                    self._write(document.storage_type,
                                thumbnail, document.thumbnail_path)

                    if archive_path and os.path.isfile(archive_path):
                        document.archive_filename = generate_unique_filename(
                            document,
                            archive_filename=True
                        )
                        create_source_path_directory(document.archive_path)
                        self._write(document.storage_type,
                                    archive_path, document.archive_path)

                        with open(archive_path, 'rb') as f:
                            document.archive_checksum = hashlib.md5(
                                f.read()).hexdigest()

                # Don't save with the lock active. Saving will cause the file
                # renaming logic to aquire the lock as well.
                document.save()

                # Delete the file only if it was successfully consumed
                self.log("debug", "Deleting file {}".format(self.path))
                os.unlink(self.path)

                # https://github.com/jonaswinkler/paperless-ng/discussions/1037
                shadow_file = os.path.join(
                    os.path.dirname(self.path),
                    "._" + os.path.basename(self.path))

                if os.path.isfile(shadow_file):
                    self.log("debug", "Deleting file {}".format(shadow_file))
                    os.unlink(shadow_file)

        except Exception as e:
            self._fail(
                str(e),
                f"The following error occured while consuming "
                f"{self.filename}: {e}",
                exc_info=True
            )
        finally:
            document_parser.cleanup()

        self.run_post_consume_script(document)

        self.log(
            "info",
            "Document {} consumption finished".format(document)
        )

        self._send_progress(100, 100, 'SUCCESS', MESSAGE_FINISHED, document.id)

        return document

    def _store(self, text, date, mime_type):

        # If someone gave us the original filename, use it instead of doc.

        file_info = FileInfo.from_filename(self.filename)

        stats = os.stat(self.path)

        self.log("debug", "Saving record to database")

        created = file_info.created or date or timezone.make_aware(
            datetime.datetime.fromtimestamp(stats.st_mtime))

        storage_type = Document.STORAGE_TYPE_UNENCRYPTED

        with open(self.path, "rb") as f:
            document = Document.objects.create(
                title=(self.override_title or file_info.title)[:127],
                content=text,
                mime_type=mime_type,
                checksum=hashlib.md5(f.read()).hexdigest(),
                created=created,
                modified=created,
                storage_type=storage_type
            )

        self.apply_overrides(document)

        document.save()

        return document

    def apply_overrides(self, document):
        if self.override_correspondent_id:
            document.correspondent = Correspondent.objects.get(
                pk=self.override_correspondent_id)

        if self.override_document_type_id:
            document.document_type = DocumentType.objects.get(
                pk=self.override_document_type_id)

        if self.override_tag_ids:
            for tag_id in self.override_tag_ids:
                document.tags.add(Tag.objects.get(pk=tag_id))

    def _write(self, storage_type, source, target):
        with open(source, "rb") as read_file:
            with open(target, "wb") as write_file:
                write_file.write(read_file.read())
