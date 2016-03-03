import datetime
import logging
import tempfile
import uuid

from multiprocessing.pool import Pool

import itertools

import langdetect
import os
import re
import subprocess

import pyocr
import shutil

from PIL import Image

from django.conf import settings
from django.utils import timezone
from django.template.defaultfilters import slugify
from pyocr.tesseract import TesseractError

from paperless.db import GnuPG

from .models import Correspondent, Tag, Document, Log
from .languages import ISO639


class OCRError(Exception):
    pass


class ConsumerError(Exception):
    pass


class Consumer(object):
    """
    Loop over every file found in CONSUMPTION_DIR and:
      1. Convert it to a greyscale png
      2. Use tesseract on the png
      3. Encrypt and store the document in the MEDIA_ROOT
      4. Store the OCR'd text in the database
      5. Delete the document and image(s)
    """

    SCRATCH = settings.SCRATCH_DIR
    CONVERT = settings.CONVERT_BINARY
    CONSUME = settings.CONSUMPTION_DIR
    THREADS = int(settings.OCR_THREADS) if settings.OCR_THREADS else None

    DEFAULT_OCR_LANGUAGE = settings.OCR_LANGUAGE

    REGEX_TITLE = re.compile(
        r"^.*/(.*)\.(pdf|jpe?g|png|gif|tiff)$",
        flags=re.IGNORECASE
    )
    REGEX_SENDER_TITLE = re.compile(
        r"^.*/(.+) - (.*)\.(pdf|jpe?g|png|gif|tiff)$",
        flags=re.IGNORECASE
    )
    REGEX_SENDER_TITLE_TAGS = re.compile(
        r"^.*/(.*) - (.*) - ([a-z0-9\-,]*)\.(pdf|jpe?g|png|gif|tiff)$",
        flags=re.IGNORECASE
    )

    def __init__(self):

        self.logger = logging.getLogger(__name__)
        self.logging_group = None

        try:
            os.makedirs(self.SCRATCH)
        except FileExistsError:
            pass

        self.stats = {}
        self._ignore = []

        if not self.CONSUME:
            raise ConsumerError(
                "The CONSUMPTION_DIR settings variable does not appear to be "
                "set."
            )

        if not os.path.exists(self.CONSUME):
            raise ConsumerError(
                "Consumption directory {} does not exist".format(self.CONSUME))

    def log(self, level, message):
        getattr(self.logger, level)(message, extra={
            "group": self.logging_group,
            "component": Log.COMPONENT_CONSUMER
        })

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

            self.logging_group = uuid.uuid4()

            self.log("info", "Consuming {}".format(doc))

            tempdir = tempfile.mkdtemp(prefix="paperless", dir=self.SCRATCH)
            pngs = self._get_greyscale(tempdir, doc)

            try:
                text = self._get_ocr(pngs)
                self._store(text, doc)
            except OCRError as e:
                self._ignore.append(doc)
                self.log("error", "OCR FAILURE for {}: {}".format(doc, e))
                self._cleanup_tempdir(tempdir)
                continue
            else:
                self._cleanup_tempdir(tempdir)
                self._cleanup_doc(doc)

    def _get_greyscale(self, tempdir, doc):

        self.log("info", "Generating greyscale image from {}".format(doc))

        png = os.path.join(tempdir, "convert-%04d.jpg")

        subprocess.Popen((
            self.CONVERT, "-density", "300", "-depth", "8",
            "-type", "grayscale", doc, png
        )).wait()

        pngs = []
        for f in os.listdir(tempdir):
            if f.startswith("convert"):
                pngs.append(os.path.join(tempdir, f))

        return sorted(filter(lambda __: os.path.isfile(__), pngs))

    def _guess_language(self, text):
        try:
            guess = langdetect.detect(text)
            self.log("debug", "Language detected: {}".format(guess))
            return guess
        except Exception as e:
            self.log("warning", "Language detection error: {}".format(e))

    def _get_ocr(self, pngs):
        """
        Attempts to do the best job possible OCR'ing the document based on
        simple language detection trial & error.
        """

        if not pngs:
            raise OCRError("No images found")

        self.log("info", "OCRing the document")

        # Since the division gets rounded down by int, this calculation works
        # for every edge-case, i.e. 1
        middle = int(len(pngs) / 2)
        raw_text = self._ocr([pngs[middle]], self.DEFAULT_OCR_LANGUAGE)

        guessed_language = self._guess_language(raw_text)

        if not guessed_language or guessed_language not in ISO639:
            self.log("warning", "Language detection failed!")
            if settings.FORGIVING_OCR:
                self.log(
                    "warning",
                    "As FORGIVING_OCR is enabled, we're going to make the "
                    "best with what we have."
                )
                raw_text = self._assemble_ocr_sections(pngs, middle, raw_text)
                return raw_text
            raise OCRError("Language detection failed")

        if ISO639[guessed_language] == self.DEFAULT_OCR_LANGUAGE:
            raw_text = self._assemble_ocr_sections(pngs, middle, raw_text)
            return raw_text

        try:
            return self._ocr(pngs, ISO639[guessed_language])
        except pyocr.pyocr.tesseract.TesseractError:
            if settings.FORGIVING_OCR:
                self.log(
                    "warning",
                    "OCR for {} failed, but we're going to stick with what "
                    "we've got since FORGIVING_OCR is enabled.".format(
                        guessed_language
                    )
                )
                raw_text = self._assemble_ocr_sections(pngs, middle, raw_text)
                return raw_text
            raise OCRError(
                "The guessed language is not available in this instance of "
                "Tesseract."
            )

    def _assemble_ocr_sections(self, pngs, middle, text):
        """
        Given a `middle` value and the text that middle page represents, we OCR
        the remainder of the document and return the whole thing.
        """
        text = self._ocr(pngs[:middle], self.DEFAULT_OCR_LANGUAGE) + text
        text += self._ocr(pngs[middle+1:], self.DEFAULT_OCR_LANGUAGE)
        return text

    def _ocr(self, pngs, lang):
        """
        Performs a single OCR attempt.
        """

        if not pngs:
            return ""

        self.log("info", "Parsing for {}".format(lang))

        with Pool(processes=self.THREADS) as pool:
            r = pool.map(image_to_string, itertools.product(pngs, [lang]))
            r = " ".join(r)

        # Strip out excess white space to allow matching to go smoother
        return re.sub(r"\s+", " ", r)

    def _guess_attributes_from_name(self, parseable):
        """
        We use a crude naming convention to make handling the sender, title,
        and tags easier:
          "<sender> - <title> - <tags>.<suffix>"
          "<sender> - <title>.<suffix>"
          "<title>.<suffix>"
        """

        def get_sender(sender_name):
            return Correspondent.objects.get_or_create(
                name=sender_name, defaults={"slug": slugify(sender_name)})[0]

        def get_tags(tags):
            r = []
            for t in tags.split(","):
                r.append(
                    Tag.objects.get_or_create(slug=t, defaults={"name": t})[0])
            return tuple(r)

        def get_suffix(suffix):
            suffix = suffix.lower()
            if suffix == "jpeg":
                return "jpg"
            return suffix

        # First attempt: "<sender> - <title> - <tags>.<suffix>"
        m = re.match(self.REGEX_SENDER_TITLE_TAGS, parseable)
        if m:
            return (
                get_sender(m.group(1)),
                m.group(2),
                get_tags(m.group(3)),
                get_suffix(m.group(4))
            )

        # Second attempt: "<sender> - <title>.<suffix>"
        m = re.match(self.REGEX_SENDER_TITLE, parseable)
        if m:
            return (
                get_sender(m.group(1)),
                m.group(2),
                (),
                get_suffix(m.group(3))
            )

        # That didn't work, so we assume sender and tags are None
        m = re.match(self.REGEX_TITLE, parseable)
        return None, m.group(1), (), get_suffix(m.group(2))

    def _store(self, text, doc):

        sender, title, tags, file_type = self._guess_attributes_from_name(doc)
        relevant_tags = set(list(Tag.match_all(text)) + list(tags))

        stats = os.stat(doc)

        self.log("debug", "Saving record to database")

        document = Document.objects.create(
            sender=sender,
            title=title,
            content=text,
            file_type=file_type,
            created=timezone.make_aware(
                datetime.datetime.fromtimestamp(stats.st_mtime)),
            modified=timezone.make_aware(
                datetime.datetime.fromtimestamp(stats.st_mtime))
        )

        if relevant_tags:
            tag_names = ", ".join([t.slug for t in relevant_tags])
            self.log("debug", "Tagging with {}".format(tag_names))
            document.tags.add(*relevant_tags)

        with open(doc, "rb") as unencrypted:
            with open(document.source_path, "wb") as encrypted:
                self.log("debug", "Encrypting")
                encrypted.write(GnuPG.encrypted(unencrypted))

        self.log("info", "Completed")

    def _cleanup_tempdir(self, d):
        self.log("debug", "Deleting directory {}".format(d))
        shutil.rmtree(d)

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


def image_to_string(args):
    """
    I have no idea why, but if this function were a method of Consumer, it
    would explode with:

      `TypeError: cannot serialize '_io.TextIOWrapper' object`.
    """

    png, lang = args
    ocr = pyocr.get_available_tools()[0]
    with Image.open(os.path.join(Consumer.SCRATCH, png)) as f:
        if ocr.can_detect_orientation():
            try:
                orientation = ocr.detect_orientation(f, lang=lang)
                f = f.rotate(orientation["angle"], expand=1)
            except TesseractError:
                pass
        return ocr.image_to_string(f, lang=lang)
