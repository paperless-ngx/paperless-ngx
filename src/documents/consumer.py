from django.db import transaction
import datetime
import hashlib
import logging
import os
import re
import time
import uuid

from operator import itemgetter
from django.conf import settings
from django.utils import timezone
from paperless.db import GnuPG

from .models import Document, FileInfo, Tag
from .parsers import ParseError
from .signals import (
    document_consumer_declaration,
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

    # Files are considered ready for consumption if they have been unmodified
    # for this duration
    FILES_MIN_UNMODIFIED_DURATION = 0.5

    def __init__(self, consume=settings.CONSUMPTION_DIR,
                 scratch=settings.SCRATCH_DIR):

        self.logger = logging.getLogger(__name__)
        self.logging_group = None

        self._ignore = []
        self.consume = consume
        self.scratch = scratch

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

        self.parsers = []
        for response in document_consumer_declaration.send(self):
            self.parsers.append(response[1])

        if not self.parsers:
            raise ConsumerError(
                "No parsers could be found, not even the default.  "
                "This is a problem."
            )

    def log(self, level, message):
        getattr(self.logger, level)(message, extra={
            "group": self.logging_group
        })

    def consume_new_files(self):
        """
        Find non-ignored files in consumption dir and consume them if they have
        been unmodified for FILES_MIN_UNMODIFIED_DURATION.
        """
        ignored_files = []
        files = []
        for entry in os.scandir(self.consume):
            if entry.is_file():
                file = (entry.path, entry.stat().st_mtime)
                if file in self._ignore:
                    ignored_files.append(file)
                else:
                    files.append(file)

        if not files:
            return

        # Set _ignore to only include files that still exist.
        # This keeps it from growing indefinitely.
        self._ignore[:] = ignored_files

        files_old_to_new = sorted(files, key=itemgetter(1))

        time.sleep(self.FILES_MIN_UNMODIFIED_DURATION)

        for file, mtime in files_old_to_new:
            if mtime == os.path.getmtime(file):
                # File has not been modified and can be consumed
                if not self.try_consume_file(file):
                    self._ignore.append((file, mtime))

    @transaction.atomic
    def try_consume_file(self, file):
        """
        Return True if file was consumed
        """

        if not re.match(FileInfo.REGEXES["title"], file):
            return False

        doc = file

        if self._is_duplicate(doc):
            self.log(
                "info",
                "Skipping {} as it appears to be a duplicate".format(doc)
            )
            return False

        parser_class = self._get_parser_class(doc)
        if not parser_class:
            self.log(
                "error", "No parsers could be found for {}".format(doc))
            return False

        self.logging_group = uuid.uuid4()

        self.log("info", "Consuming {}".format(doc))

        document_consumption_started.send(
            sender=self.__class__,
            filename=doc,
            logging_group=self.logging_group
        )

        parsed_document = parser_class(doc)

        try:
            thumbnail = parsed_document.get_thumbnail()
            date = parsed_document.get_date()
            document = self._store(
                parsed_document.get_text(),
                doc,
                thumbnail,
                date
            )
        except ParseError as e:
            self.log("error", "PARSE FAILURE for {}: {}".format(doc, e))
            parsed_document.cleanup()
            return False
        else:
            parsed_document.cleanup()
            self._cleanup_doc(doc)

            self.log(
                "info",
                "Document {} consumption finished".format(document)
            )

            document_consumption_finished.send(
                sender=self.__class__,
                document=document,
                logging_group=self.logging_group
            )
            return True

    def _get_parser_class(self, doc):
        """
        Determine the appropriate parser class based on the file
        """

        options = []
        for parser in self.parsers:
            result = parser(doc)
            if result:
                options.append(result)

        self.log(
            "info",
            "Parsers available: {}".format(
                ", ".join([str(o["parser"].__name__) for o in options])
            )
        )

        if not options:
            return None

        # Return the parser with the highest weight.
        return sorted(
            options, key=lambda _: _["weight"], reverse=True)[0]["parser"]

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

        relevant_tags = set(list(Tag.match_all(text)) + list(file_info.tags))
        if relevant_tags:
            tag_names = ", ".join([t.slug for t in relevant_tags])
            self.log("debug", "Tagging with {}".format(tag_names))
            document.tags.add(*relevant_tags)

        self._write(document, doc, document.source_path)
        self._write(document, thumbnail, document.thumbnail_path)

        self.log("info", "Completed")

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
