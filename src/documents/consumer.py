import datetime
import hashlib
import logging
import os
import re
import uuid

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
      3. Encrypt and store the document in the MEDIA_ROOT
      4. Store the OCR'd text in the database
      5. Delete the document and image(s)
    """

    def __init__(self, consume=settings.CONSUMPTION_DIR, scratch=settings.SCRATCH_DIR):

        self.logger = logging.getLogger(__name__)
        self.logging_group = None

        self.stats = {}
        self._ignore = []
        self.consume = consume
        self.scratch = scratch

        try:
            os.makedirs(self.scratch)
        except FileExistsError:
            pass

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

    def run(self):

        for doc in os.listdir(self.consume):

            doc = os.path.join(self.consume, doc)

            if not os.path.isfile(doc):
                continue

            if not re.match(FileInfo.REGEXES["title"], doc):
                continue

            if doc in self._ignore:
                continue

            if not self._is_ready(doc):
                continue

            if self._is_duplicate(doc):
                self.log(
                    "info",
                    "Skipping {} as it appears to be a duplicate".format(doc)
                )
                self._ignore.append(doc)
                continue

            parser_class = self._get_parser_class(doc)
            if not parser_class:
                self.log(
                    "error", "No parsers could be found for {}".format(doc))
                self._ignore.append(doc)
                continue

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

                self._ignore.append(doc)
                self.log("error", "PARSE FAILURE for {}: {}".format(doc, e))
                parsed_document.cleanup()

                continue

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
                modified=created
            )

        relevant_tags = set(list(Tag.match_all(text)) + list(file_info.tags))
        if relevant_tags:
            tag_names = ", ".join([t.slug for t in relevant_tags])
            self.log("debug", "Tagging with {}".format(tag_names))
            document.tags.add(*relevant_tags)

        # Encrypt and store the actual document
        with open(doc, "rb") as unencrypted:
            with open(document.source_path, "wb") as encrypted:
                self.log("debug", "Encrypting the document")
                encrypted.write(GnuPG.encrypted(unencrypted))

        # Encrypt and store the thumbnail
        with open(thumbnail, "rb") as unencrypted:
            with open(document.thumbnail_path, "wb") as encrypted:
                self.log("debug", "Encrypting the thumbnail")
                encrypted.write(GnuPG.encrypted(unencrypted))

        self.log("info", "Completed")

        return document

    def _cleanup_doc(self, doc):
        self.log("debug", "Deleting document {}".format(doc))
        os.unlink(doc)

    def _is_ready(self, doc):
        """
        Detect whether `doc` is ready to consume or if it's still being written
        to by the uploader.
        """

        t = os.stat(doc).st_mtime

        if self.stats.get(doc) == t:
            del(self.stats[doc])
            return True

        self.stats[doc] = t

        return False

    @staticmethod
    def _is_duplicate(doc):
        with open(doc, "rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        return Document.objects.filter(checksum=checksum).exists()
