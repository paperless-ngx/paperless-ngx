import datetime
import hashlib
import logging
import os

import magic
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from paperless.db import GnuPG
from .classifier import DocumentClassifier, IncompatibleClassifierVersionError
from .file_handling import generate_filename, create_source_path_directory
from .loggers import LoggingMixin
from .models import Document, FileInfo, Correspondent, DocumentType, Tag
from .parsers import ParseError, get_parser_class_for_mime_type
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
            raise ConsumerError("Cannot consume {}: It is not a file".format(
                self.path))

    def pre_check_consumption_dir(self):
        if not settings.CONSUMPTION_DIR:
            raise ConsumerError(
                "The CONSUMPTION_DIR settings variable does not appear to be "
                "set.")

        if not os.path.isdir(settings.CONSUMPTION_DIR):
            raise ConsumerError(
                "Consumption directory {} does not exist".format(
                    settings.CONSUMPTION_DIR))

    def pre_check_duplicate(self):
        with open(self.path, "rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        if Document.objects.filter(checksum=checksum).exists():
            if settings.CONSUMER_DELETE_DUPLICATES:
                os.unlink(self.path)
            raise ConsumerError(
                "Not consuming {}: It is a duplicate.".format(self.filename)
            )

    def pre_check_directories(self):
        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)
        os.makedirs(settings.THUMBNAIL_DIR, exist_ok=True)
        os.makedirs(settings.ORIGINALS_DIR, exist_ok=True)

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
        self.pre_check_consumption_dir()
        self.pre_check_directories()
        self.pre_check_duplicate()

        self.log("info", "Consuming {}".format(self.filename))

        # Determine the parser class.

        mime_type = magic.from_file(self.path, mime=True)

        parser_class = get_parser_class_for_mime_type(mime_type)
        if not parser_class:
            raise ConsumerError(f"No parsers abvailable for {self.filename}")
        else:
            self.log("debug",
                     f"Parser: {parser_class.__name__} "
                     f"based on mime type {mime_type}")

        # Notify all listeners that we're going to do some work.

        document_consumption_started.send(
            sender=self.__class__,
            filename=self.path,
            logging_group=self.logging_group
        )

        # This doesn't parse the document yet, but gives us a parser.

        document_parser = parser_class(self.path, self.logging_group)

        # However, this already created working directories which we have to
        # clean up.

        # Parse the document. This may take some time.

        try:
            self.log("debug", f"Generating thumbnail for {self.filename}...")
            thumbnail = document_parser.get_optimised_thumbnail()
            self.log("debug", "Parsing {}...".format(self.filename))
            text = document_parser.get_text()
            date = document_parser.get_date()
        except ParseError as e:
            document_parser.cleanup()
            raise ConsumerError(e)

        # Prepare the document classifier.

        # TODO: I don't really like to do this here, but this way we avoid
        #   reloading the classifier multiple times, since there are multiple
        #   post-consume hooks that all require the classifier.

        try:
            classifier = DocumentClassifier()
            classifier.reload()
        except (FileNotFoundError, IncompatibleClassifierVersionError) as e:
            logging.getLogger(__name__).warning(
                "Cannot classify documents: {}.".format(e))
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

                create_source_path_directory(document.source_path)
                self._write(document, self.path, document.source_path)
                self._write(document, thumbnail, document.thumbnail_path)

                # Delete the file only if it was successfully consumed
                self.log("debug", "Deleting file {}".format(self.path))
                os.unlink(self.path)
        except Exception as e:
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

        if settings.PASSPHRASE:
            storage_type = Document.STORAGE_TYPE_GPG
        else:
            storage_type = Document.STORAGE_TYPE_UNENCRYPTED

        with open(self.path, "rb") as f:
            document = Document.objects.create(
                correspondent=file_info.correspondent,
                title=file_info.title,
                content=text,
                mime_type=mime_type,
                checksum=hashlib.md5(f.read()).hexdigest(),
                created=created,
                modified=created,
                storage_type=storage_type
            )

        relevant_tags = set(file_info.tags)
        if relevant_tags:
            tag_names = ", ".join([t.slug for t in relevant_tags])
            self.log("debug", "Tagging with {}".format(tag_names))
            document.tags.add(*relevant_tags)

        self.apply_overrides(document)

        document.filename = generate_filename(document)

        # We need to save the document twice, since we need the PK of the
        # document in order to create its filename above.
        document.save()

        return document

    def apply_overrides(self, document):
        if self.override_title:
            document.title = self.override_title

        if self.override_correspondent_id:
            document.correspondent = Correspondent.objects.get(
                pk=self.override_correspondent_id)

        if self.override_document_type_id:
            document.document_type = DocumentType.objects.get(
                pk=self.override_document_type_id)

        if self.override_tag_ids:
            for tag_id in self.override_tag_ids:
                document.tags.add(Tag.objects.get(pk=tag_id))

    def _write(self, document, source, target):
        with open(source, "rb") as read_file:
            with open(target, "wb") as write_file:
                if document.storage_type == Document.STORAGE_TYPE_UNENCRYPTED:
                    write_file.write(read_file.read())
                    return
                self.log("debug", "Encrypting")
                write_file.write(GnuPG.encrypted(read_file))
