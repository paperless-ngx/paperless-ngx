import datetime
import hashlib
import logging
import os
import re
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from paperless.db import GnuPG
from .classifier import DocumentClassifier, IncompatibleClassifierVersionError
from .models import Document, FileInfo
from .parsers import ParseError, get_parser_class
from .signals import (
    document_consumption_finished,
    document_consumption_started
)


class ConsumerError(Exception):
    pass


class Consumer:
    """
    Loop over every file found in CONSUMPTION_DIR and:
      1. Convert it to a greyscale pnm
      2. Use tesseract on the pnm
      3. Store the document in the MEDIA_ROOT with optional encryption
      4. Store the OCR'd text in the database
      5. Delete the document and image(s)
    """

    def _send_progress(self, filename, current_progress, max_progress, status, message, document_id=None):
        payload = {
            'filename': os.path.basename(filename),
            'current_progress': current_progress,
            'max_progress': max_progress,
            'status': status,
            'message': message,
            'document_id': document_id
        }
        async_to_sync(self.channel_layer.group_send)("status_updates", {'type': 'status_update', 'data': payload})

    def __init__(self, consume=settings.CONSUMPTION_DIR,
                 scratch=settings.SCRATCH_DIR):

        self.logger = logging.getLogger(__name__)
        self.logging_group = None

        self.consume = consume
        self.scratch = scratch

        self.classifier = DocumentClassifier()

        self.channel_layer = get_channel_layer()

        os.makedirs(self.scratch, exist_ok=True)

        self.storage_type = Document.STORAGE_TYPE_UNENCRYPTED
        if settings.PASSPHRASE:
            self.storage_type = Document.STORAGE_TYPE_GPG

        if not self.consume:
            raise ConsumerError(
                "The CONSUMPTION_DIR settings variable does not appear to be "
                "set."
            )

        if not os.path.exists(self.consume):
            raise ConsumerError(
                "Consumption directory {} does not exist".format(self.consume))

    def log(self, level, message):
        getattr(self.logger, level)(message, extra={
            "group": self.logging_group
        })

    @transaction.atomic
    def try_consume_file(self, file):
        """
        Return True if file was consumed
        """

        self.logging_group = uuid.uuid4()

        if not re.match(FileInfo.REGEXES["title"], file):
            return False

        doc = file

        if self._is_duplicate(doc):
            self.log(
                "warning",
                "Skipping {} as it appears to be a duplicate".format(doc)
            )
            return False

        self.log("info", "Consuming {}".format(doc))


        parser_class = get_parser_class(doc)
        if not parser_class:
            self.log(
                "error", "No parsers could be found for {}".format(doc))
            return False
        else:
            self.log("info", "Parser: {}".format(parser_class.__name__))

        self._send_progress(file, 0, 100, 'WORKING', 'Consumption started')

        document_consumption_started.send(
            sender=self.__class__,
            filename=doc,
            logging_group=self.logging_group
        )

        def progress_callback(current_progress, max_progress, message):
            # recalculate progress to be within 20 and 80
            p = int((current_progress / max_progress) * 60 + 20)
            self._send_progress(file, p, 100, "WORKING", message)

        document_parser = parser_class(doc, self.logging_group, progress_callback)

        try:
            self.log("info", "Generating thumbnail for {}...".format(doc))
            self._send_progress(file, 10, 100, 'WORKING',
                                'Generating thumbnail...')
            thumbnail = document_parser.get_optimised_thumbnail()
            self._send_progress(file, 20, 100, 'WORKING',
                                'Getting text from document...')
            text = document_parser.get_text()
            self._send_progress(file, 80, 100, 'WORKING',
                                'Getting date from document...')
            date = document_parser.get_date()
            self._send_progress(file, 85, 100, 'WORKING',
                                'Storing the document...')
            document = self._store(
                text,
                doc,
                thumbnail,
                date
            )
        except ParseError as e:
            self.log("fatal", "PARSE FAILURE for {}: {}".format(doc, e))
            self._send_progress(file, 100, 100, 'FAILED',
                                "Failed: {}".format(e))

            document_parser.cleanup()
            return False
        else:
            document_parser.cleanup()
            self._cleanup_doc(doc)

            self.log(
                "info",
                "Document {} consumption finished".format(document)
            )

            classifier = None

            try:
                self.classifier.reload()
                classifier = self.classifier
            except (FileNotFoundError, IncompatibleClassifierVersionError) as e:
                logging.getLogger(__name__).warning("Cannot classify documents: {}.".format(e))

            self._send_progress(file, 90, 100, 'WORKING',
                                'Performing post-consumption tasks...')

            document_consumption_finished.send(
                sender=self.__class__,
                document=document,
                logging_group=self.logging_group,
                classifier=classifier
            )
            self._send_progress(file, 100, 100, 'SUCCESS',
                                'Finished.', document.id)
            return True

    def _store(self, text, doc, thumbnail, date):

        file_info = FileInfo.from_path(doc)

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

        self._write(document, doc, document.source_path)
        self._write(document, thumbnail, document.thumbnail_path)

        #TODO: why do we need to save the document again?
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

    def _cleanup_doc(self, doc):
        self.log("debug", "Deleting document {}".format(doc))
        os.unlink(doc)

    @staticmethod
    def _is_duplicate(doc):
        with open(doc, "rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        return Document.objects.filter(checksum=checksum).exists()
