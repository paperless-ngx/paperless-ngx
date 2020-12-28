import datetime
import hashlib
import logging
import os

import magic
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from filelock import FileLock

from .classifier import DocumentClassifier, IncompatibleClassifierVersionError
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


class Consumer(LoggingMixin):

    def __init__(self):
        super().__init__()
        self.path = None
        self.filename = None
        self.override_title = None
        self.override_correspondent_id = None
        self.override_tag_ids = None
        self.override_document_type_id = None

    def pre_check_file_exists(self):
        if not os.path.isfile(self.path):
            self.log(
                "error",
                "Cannot consume {}: It is not a file.".format(self.path)
            )
            raise ConsumerError("Cannot consume {}: It is not a file".format(
                self.path))

    def pre_check_duplicate(self):
        with open(self.path, "rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        if Document.objects.filter(Q(checksum=checksum) | Q(archive_checksum=checksum)).exists():  # NOQA: E501
            if settings.CONSUMER_DELETE_DUPLICATES:
                os.unlink(self.path)
            self.log(
                "error",
                "Not consuming {}: It is a duplicate.".format(self.filename)
            )
            raise ConsumerError(
                "Not consuming {}: It is a duplicate.".format(self.filename)
            )

    def pre_check_directories(self):
        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)
        os.makedirs(settings.THUMBNAIL_DIR, exist_ok=True)
        os.makedirs(settings.ORIGINALS_DIR, exist_ok=True)
        os.makedirs(settings.ARCHIVE_DIR, exist_ok=True)

    def try_consume_file(self,
                         path,
                         override_filename=None,
                         override_title=None,
                         override_correspondent_id=None,
                         override_document_type_id=None,
                         override_tag_ids=None):
        """
        Return the document object if it was successfully created.
        """

        self.path = path
        self.filename = override_filename or os.path.basename(path)
        self.override_title = override_title
        self.override_correspondent_id = override_correspondent_id
        self.override_document_type_id = override_document_type_id
        self.override_tag_ids = override_tag_ids

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
            raise ConsumerError(
                f"Unsupported mime type {mime_type} of file {self.filename}")
        else:
            self.log("debug",
                     f"Parser: {parser_class.__name__}")

        # Notify all listeners that we're going to do some work.

        document_consumption_started.send(
            sender=self.__class__,
            filename=self.path,
            logging_group=self.logging_group
        )

        # This doesn't parse the document yet, but gives us a parser.

        document_parser = parser_class(self.logging_group)

        # However, this already created working directories which we have to
        # clean up.

        # Parse the document. This may take some time.

        try:
            self.log("debug", "Parsing {}...".format(self.filename))
            document_parser.parse(self.path, mime_type)

            self.log("debug", f"Generating thumbnail for {self.filename}...")
            thumbnail = document_parser.get_optimised_thumbnail(
                self.path, mime_type)

            text = document_parser.get_text()
            date = document_parser.get_date()
            if not date:
                date = parse_date(self.filename, text)
            archive_path = document_parser.get_archive_path()

        except ParseError as e:
            document_parser.cleanup()
            self.log(
                "error",
                f"Error while consuming document {self.filename}: {e}")
            raise ConsumerError(e)

        # Prepare the document classifier.

        # TODO: I don't really like to do this here, but this way we avoid
        #   reloading the classifier multiple times, since there are multiple
        #   post-consume hooks that all require the classifier.

        try:
            classifier = DocumentClassifier()
            classifier.reload()
        except (FileNotFoundError, IncompatibleClassifierVersionError) as e:
            self.log(
                "warning",
                f"Cannot classify documents: {e}.")
            classifier = None

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
                    document.filename = generate_unique_filename(
                        document, settings.ORIGINALS_DIR)
                    create_source_path_directory(document.source_path)

                    self._write(document.storage_type,
                                self.path, document.source_path)

                    self._write(document.storage_type,
                                thumbnail, document.thumbnail_path)

                    if archive_path and os.path.isfile(archive_path):
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
        except Exception as e:
            self.log(
                "error",
                f"The following error occured while consuming "
                f"{self.filename}: {e}"
            )
            raise ConsumerError(e)
        finally:
            document_parser.cleanup()

        self.log(
            "info",
            "Document {} consumption finished".format(document)
        )

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
