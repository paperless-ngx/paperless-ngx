import os
import re

from django.conf import settings

from .base import Consumer, OCRError


class FileConsumerError(Exception):
    pass


class FileConsumer(Consumer):

    CONSUME = settings.CONSUMPTION_DIR

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

            if not re.match(self.REGEX_TITLE, doc):
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
