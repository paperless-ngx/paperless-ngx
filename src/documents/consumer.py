import datetime
import hashlib
import logging
import os
import re
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from paperless.db import GnuPG
from .classifier import DocumentClassifier, IncompatibleClassifierVersionError
from .file_handling import generate_filename, create_source_path_directory
from .models import Document, FileInfo, Correspondent, DocumentType, Tag
from .parsers import ParseError, get_parser_class
from .signals import (
    document_consumption_finished,
    document_consumption_started
)


class ConsumerError(Exception):
    pass


class Consumer:

    def __init__(self):

        self.logger = logging.getLogger(__name__)
        self.logging_group = None

        self.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        if settings.PASSPHRASE:
            self.storage_type = Document.STORAGE_TYPE_GPG

    @staticmethod
    def pre_check_file_exists(filename):
        if not os.path.isfile(filename):
            raise ConsumerError("Cannot consume {}: It is not a file".format(
                filename))

    @staticmethod
    def pre_check_consumption_dir():
        if not settings.CONSUMPTION_DIR:
            raise ConsumerError(
                "The CONSUMPTION_DIR settings variable does not appear to be "
                "set.")

        if not os.path.isdir(settings.CONSUMPTION_DIR):
            raise ConsumerError(
                "Consumption directory {} does not exist".format(
                    settings.CONSUMPTION_DIR))

    @staticmethod
    def pre_check_regex(filename):
        if not re.match(FileInfo.REGEXES["title"], filename):
            raise ConsumerError(
                "Filename {} does not seem to be safe to "
                "consume".format(filename))

    @staticmethod
    def pre_check_duplicate(filename):
        with open(filename, "rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        if Document.objects.filter(checksum=checksum).exists():
            if settings.CONSUMER_DELETE_DUPLICATES:
                os.unlink(filename)
            raise ConsumerError(
                "Not consuming {}: It is a duplicate.".format(filename)
            )

    @staticmethod
    def pre_check_directories():
        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)
        os.makedirs(settings.THUMBNAIL_DIR, exist_ok=True)
        os.makedirs(settings.ORIGINALS_DIR, exist_ok=True)

    def log(self, level, message):
        getattr(self.logger, level)(message, extra={
            "group": self.logging_group
        })

    def try_consume_file(self,
                         filename,
                         original_filename=None,
                         force_title=None,
                         force_correspondent_id=None,
                         force_document_type_id=None,
                         force_tag_ids=None):
        """
        Return the document object if it was successfully created.
        """

        # this is for grouping logging entries for this particular file
        # together.

        self.logging_group = uuid.uuid4()

        # Make sure that preconditions for consuming the file are met.

        self.pre_check_file_exists(filename)
        self.pre_check_consumption_dir()
        self.pre_check_directories()
        self.pre_check_regex(filename)
        self.pre_check_duplicate(filename)

        self.log("info", "Consuming {}".format(filename))

        # Determine the parser class.

        parser_class = get_parser_class(original_filename or filename)
        if not parser_class:
            raise ConsumerError("No parsers abvailable for {}".format(filename))
        else:
            self.log("debug", "Parser: {}".format(parser_class.__name__))

        # Notify all listeners that we're going to do some work.

        document_consumption_started.send(
            sender=self.__class__,
            filename=filename,
            logging_group=self.logging_group
        )

        # This doesn't parse the document yet, but gives us a parser.

        document_parser = parser_class(filename, self.logging_group)

        # However, this already created working directories which we have to
        # clean up.

        # Parse the document. This may take some time.

        try:
            self.log("debug", "Generating thumbnail for {}...".format(filename))
            thumbnail = document_parser.get_optimised_thumbnail()
            self.log("debug", "Parsing {}...".format(filename))
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
                    doc=filename,
                    thumbnail=thumbnail,
                    date=date,
                    original_filename=original_filename,
                    force_title=force_title,
                    force_correspondent_id=force_correspondent_id,
                    force_document_type_id=force_document_type_id,
                    force_tag_ids=force_tag_ids
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
                self._write(document, filename, document.source_path)
                self._write(document, thumbnail, document.thumbnail_path)

                # Delete the file only if it was successfully consumed
                self.log("debug", "Deleting document {}".format(filename))
                os.unlink(filename)
        except Exception as e:
            raise ConsumerError(e)
        finally:
            document_parser.cleanup()

        self.log(
            "info",
            "Document {} consumption finished".format(document)
        )

        return document

    def _store(self, text, doc, thumbnail, date,
               original_filename=None,
               force_title=None,
               force_correspondent_id=None,
               force_document_type_id=None,
               force_tag_ids=None):

        # If someone gave us the original filename, use it instead of doc.

        file_info = FileInfo.from_path(original_filename or doc)

        stats = os.stat(doc)

        self.log("debug", "Saving record to database")

        created = file_info.created or date or timezone.make_aware(
            datetime.datetime.fromtimestamp(stats.st_mtime))

        with open(doc, "rb") as f:
            document = Document.objects.create(
                correspondent=file_info.correspondent,
                title=file_info.title,
                content=text,
                file_type=file_info.extension,
                checksum=hashlib.md5(f.read()).hexdigest(),
                created=created,
                modified=created,
                storage_type=self.storage_type
            )

        relevant_tags = set(file_info.tags)
        if relevant_tags:
            tag_names = ", ".join([t.slug for t in relevant_tags])
            self.log("debug", "Tagging with {}".format(tag_names))
            document.tags.add(*relevant_tags)

        if force_title:
            document.title = force_title

        if force_correspondent_id:
            document.correspondent = Correspondent.objects.get(pk=force_correspondent_id)

        if force_document_type_id:
            document.document_type = DocumentType.objects.get(pk=force_document_type_id)

        if force_tag_ids:
            for tag_id in force_tag_ids:
                document.tags.add(Tag.objects.get(pk=tag_id))

        document.filename = generate_filename(document)

        # We need to save the document twice, since we need the PK of the
        # document in order to create its filename above.
        document.save()

        return document

    def _write(self, document, source, target):
        with open(source, "rb") as read_file:
            with open(target, "wb") as write_file:
                if document.storage_type == Document.STORAGE_TYPE_UNENCRYPTED:
                    write_file.write(read_file.read())
                    return
                self.log("debug", "Encrypting")
                write_file.write(GnuPG.encrypted(read_file))
