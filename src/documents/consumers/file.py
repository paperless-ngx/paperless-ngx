import os
import re

from django.conf import settings
from django.template.defaultfilters import slugify

from ..models import Sender
from . import Consumer, OCRError


class FileConsumerError(Exception):
    pass


class FileConsumer(Consumer):

    CONSUME = settings.CONSUMPTION_DIR

    PARSER_REGEX_TITLE = re.compile(
        r"^.*/(.*)\.(pdf|jpe?g|png|gif|tiff)$", flags=re.IGNORECASE)
    PARSER_REGEX_SENDER_TITLE = re.compile(
        r"^.*/(.*) - (.*)\.(pdf|jpe?g|png|gif|tiff)", flags=re.IGNORECASE)

    def __init__(self, *args, **kwargs):

        Consumer.__init__(self, *args, **kwargs)

        self.stats = {}
        self._ignore = []

        if not self.CONSUME:
            raise FileConsumerError(
                "The CONSUMPTION_DIR settings variable does not appear to be "
                "set."
            )

        if not os.path.exists(self.CONSUME):
            raise FileConsumerError(
                "Consumption directory {} does not exist".format(self.CONSUME))

    def consume(self):

        for doc in os.listdir(self.CONSUME):

            doc = os.path.join(self.CONSUME, doc)

            if not os.path.isfile(doc):
                continue

            if not re.match(self.PARSER_REGEX_TITLE, doc):
                continue

            if doc in self._ignore:
                continue

            if self._is_ready(doc):
                continue

            self._render("Consuming {}".format(doc), 1)

            pngs = self._get_greyscale(doc)

            try:
                text = self._get_ocr(pngs)
            except OCRError:
                self._ignore.append(doc)
                self._render("OCR FAILURE: {}".format(doc), 0)
                continue

            self._store(text, doc)
            self._cleanup(pngs, doc)

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

    def _guess_file_attributes(self, doc):
        """
        We use a crude naming convention to make handling the sender and title
        easier:
          "<sender> - <title>.<suffix>"
        """

        # First we attempt "<sender> - <title>.<suffix>"
        m = re.match(self.PARSER_REGEX_SENDER_TITLE, doc)
        if m:
            sender_name, title, file_type = m.group(1), m.group(2), m.group(3)
            sender, __ = Sender.objects.get_or_create(
                name=sender_name, defaults={"slug": slugify(sender_name)})
            return sender, title, file_type

        # That didn't work, so we assume sender is None
        m = re.match(self.PARSER_REGEX_TITLE, doc)
        return None, m.group(1), m.group(2)
