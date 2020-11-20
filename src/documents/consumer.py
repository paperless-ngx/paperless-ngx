import datetime
import hashlib
import logging
import os
import re

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from paperless.db import GnuPG
from .classifier import DocumentClassifier, IncompatibleClassifierVersionError
from .file_handling import generate_filename, create_source_path_directory
from .loggers import LoggingMixin
from .models import Document, FileInfo, Correspondent, DocumentType, Tag
from .parsers import ParseError, get_parser_class
from .signals import (
    document_consumption_finished,
    document_consumption_started
)


class ConsumerError(Exception):
    pass


class Consumer(LoggingMixin):

    def _send_progress(self, filename, current_progress, max_progress, status,
                       message, document_id=None):
        payload = {
            'filename': os.path.basename(filename),
            'current_progress': current_progress,
            'max_progress': max_progress,
            'status': status,
            'message': message,
            'document_id': document_id
        }
        async_to_sync(self.channel_layer.group_send)("status_updates",
                                                     {'type': 'status_update',
                                                      'data': payload})

    def __init__(self):
        super().__init__()
        self.path = None
        self.filename = None
        self.override_title = None
        self.override_correspondent_id = None
        self.override_tag_ids = None
        self.override_document_type_id = None

        self.channel_layer = get_channel_layer()

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

    def pre_check_regex(self):
        if not re.match(FileInfo.REGEXES["title"], self.filename):
            raise ConsumerError(
                "Filename {} does not seem to be safe to "
                "consume".format(self.filename))

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
        self.pre_check_regex()
        self.pre_check_duplicate()

        self.log("info", "Consuming {}".format(self.filename))

        # Determine the parser class.

        parser_class = get_parser_class(self.filename)
        if not parser_class:
            raise ConsumerError("No parsers abvailable for {}".format(self.filename))
        else:
            self.log("debug", "Parser: {}".format(parser_class.__name__))

        # Notify all listeners that we're going to do some work.

        self._send_progress(self.filename, 0, 100, 'WORKING', 'Consumption started')

        document_consumption_started.send(
            sender=self.__class__,
            filename=self.path,
            logging_group=self.logging_group
        )

        def progress_callback(current_progress, max_progress, message):
            # recalculate progress to be within 20 and 80
            p = int((current_progress / max_progress) * 60 + 20)
            self._send_progress(self.filename, p, 100, "WORKING", message)

        # This doesn't parse the document yet, but gives us a parser.

        document_parser = parser_class(self.path, self.logging_group, progress_callback)

        # However, this already created working directories which we have to
        # clean up.

        # Parse the document. This may take some time.

        try:
            self.log("debug", "Generating thumbnail for {}...".format(self.filename))
            self._send_progress(self.filename, 10, 100, 'WORKING',
                                'Generating thumbnail...')
            thumbnail = document_parser.get_optimised_thumbnail()
            self.log("debug", "Parsing {}...".format(self.filename))
            self._send_progress(self.filename, 20, 100, 'WORKING',
                                'Getting text from document...')
            text = document_parser.get_text()
            self._send_progress(self.filename, 80, 100, 'WORKING',
                                'Getting date from document...')
            date = document_parser.get_date()
        except ParseError as e:
            document_parser.cleanup()
            self._send_progress(self.filename, 100, 100, 'FAILED',
                                "Failed: {}".format(e))
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
        self._send_progress(self.filename, 85, 100, 'WORKING',
                            'Storing the document...')
        # now that everything is done, we can start to store the document
        # in the system. This will be a transaction and reasonably fast.
        try:
            with transaction.atomic():

                # store the document.
                document = self._store(
                    text=text,
                    date=date
                )

                # If we get here, it was successful. Proceed with post-consume
                # hooks. If they fail, nothing will get changed.

                self._send_progress(self.filename, 90, 100, 'WORKING',
                                    'Performing post-consumption tasks...')

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
            self._send_progress(self.filename, 100, 100, 'FAILED',
                                "Failed: {}".format(e))
            raise ConsumerError(e)
        finally:
            document_parser.cleanup()

        self.log(
            "info",
            "Document {} consumption finished".format(document)
        )

        self._send_progress(self.filename, 100, 100, 'SUCCESS',
                            'Finished.', document.id)

        return document

    def _store(self, text, date):

        # If someone gave us the original filename, use it instead of doc.

        file_info = FileInfo.from_path(self.filename)

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
                file_type=file_info.extension,
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
            document.correspondent = Correspondent.objects.get(pk=self.override_correspondent_id)

        if self.override_document_type_id:
            document.document_type = DocumentType.objects.get(pk=self.override_document_type_id)

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
