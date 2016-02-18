import datetime
import tempfile
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

from logger.models import Log
from paperless.db import GnuPG

from .models import Sender, Tag, Document
from .languages import ISO639


def image_to_string(args):
    self, png, lang = args
    with Image.open(os.path.join(self.SCRATCH, png)) as f:
        if self.OCR.can_detect_orientation():
            orientation = self.OCR.detect_orientation(f, lang=lang)
            f = f.rotate(orientation["angle"], expand=1)
        return self.OCR.image_to_string(f, lang=lang)


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

    OCR = pyocr.get_available_tools()[0]
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

    def __init__(self, verbosity=1):

        self.verbosity = verbosity

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

            Log.info("Consuming {}".format(doc), Log.COMPONENT_CONSUMER)

            tempdir = tempfile.mkdtemp(prefix="paperless", dir=self.SCRATCH)
            pngs = self._get_greyscale(tempdir, doc)

            try:
                text = self._get_ocr(pngs)
                self._store(text, doc)
            except OCRError:
                self._ignore.append(doc)
                Log.error("OCR FAILURE: {}".format(doc), Log.COMPONENT_CONSUMER)
                continue
            finally:
                self._cleanup(tempdir, doc)

    def _get_greyscale(self, tempdir, doc):

        Log.debug(
            "Generating greyscale image from {}".format(doc),
            Log.COMPONENT_CONSUMER
        )

        png = os.path.join(tempdir, "convert-%04d.jpg")

        subprocess.Popen((
            self.CONVERT, "-density", "300", "-depth", "8",
            "-type", "grayscale", doc, png
        )).wait()

        pngs = [os.path.join(tempdir, f) for f in os.listdir(tempdir) if f.startswith("convert")]
        return sorted(filter(lambda f: os.path.isfile(f), pngs))

    @staticmethod
    def _guess_language(text):
        try:
            guess = langdetect.detect(text)
            Log.debug(
                "Language detected: {}".format(guess),
                Log.COMPONENT_CONSUMER
            )
            return guess
        except Exception as e:
            Log.warning(
                "Language detection error: {}".format(e), Log.COMPONENT_MAIL)

    def _get_ocr(self, pngs):
        """
        Attempts to do the best job possible OCR'ing the document based on
        simple language detection trial & error.
        """

        if not pngs:
            raise OCRError

        Log.debug("OCRing the document", Log.COMPONENT_CONSUMER)

        # Since the division gets rounded down by int, this calculation works
        # for every edge-case, i.e. 1
        middle = int(len(pngs) / 2)
        raw_text = self._ocr([pngs[middle]], self.DEFAULT_OCR_LANGUAGE)

        guessed_language = self._guess_language(raw_text)

        if not guessed_language or guessed_language not in ISO639:
            Log.warning("Language detection failed!", Log.COMPONENT_CONSUMER)
            if settings.FORGIVING_OCR:
                Log.warning(
                    "As FORGIVING_OCR is enabled, we're going to make the best "
                    "with what we have.",
                    Log.COMPONENT_CONSUMER
                )
                raw_text = self._assemble_ocr_sections(pngs, middle, raw_text)
                return raw_text
            raise OCRError

        if ISO639[guessed_language] == self.DEFAULT_OCR_LANGUAGE:
            raw_text = self._assemble_ocr_sections(pngs, middle, raw_text)
            return raw_text

        try:
            return self._ocr(pngs, ISO639[guessed_language])
        except pyocr.pyocr.tesseract.TesseractError:
            if settings.FORGIVING_OCR:
                Log.warning(
                    "OCR for {} failed, but we're going to stick with what "
                    "we've got since FORGIVING_OCR is enabled.".format(
                        guessed_language
                    ),
                    Log.COMPONENT_CONSUMER
                )
                raw_text = self._assemble_ocr_sections(pngs, middle, raw_text)
                return raw_text
            raise OCRError

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

        Log.debug("Parsing for {}".format(lang), Log.COMPONENT_CONSUMER)

        with Pool(processes=self.THREADS) as pool:
            r = pool.map(
                image_to_string, itertools.product([self], pngs, [lang]))
            r = " ".join(r)

        # Strip out excess white space to allow matching to go smoother
        return re.sub(r"\s+", " ", r)

    def _guess_attributes_from_name(self, parseable):
        """
        We use a crude naming convention to make handling the sender, title, and
        tags easier:
          "<sender> - <title> - <tags>.<suffix>"
          "<sender> - <title>.<suffix>"
          "<title>.<suffix>"
        """

        def get_sender(sender_name):
            return Sender.objects.get_or_create(
                name=sender_name, defaults={"slug": slugify(sender_name)})[0]

        def get_tags(tags):
            r = []
            for t in tags.split(","):
                r.append(
                    Tag.objects.get_or_create(slug=t, defaults={"name": t})[0])
            return tuple(r)

        # First attempt: "<sender> - <title> - <tags>.<suffix>"
        m = re.match(self.REGEX_SENDER_TITLE_TAGS, parseable)
        if m:
            return (
                get_sender(m.group(1)),
                m.group(2),
                get_tags(m.group(3)),
                m.group(4)
            )

        # Second attempt: "<sender> - <title>.<suffix>"
        m = re.match(self.REGEX_SENDER_TITLE, parseable)
        if m:
            return get_sender(m.group(1)), m.group(2), (), m.group(3)

        # That didn't work, so we assume sender and tags are None
        m = re.match(self.REGEX_TITLE, parseable)
        return None, m.group(1), (), m.group(2)

    def _store(self, text, doc):

        sender, title, tags, file_type = self._guess_attributes_from_name(doc)
        relevant_tags = set(list(Tag.match_all(text)) + list(tags))

        stats = os.stat(doc)

        Log.debug("Saving record to database", Log.COMPONENT_CONSUMER)

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
            Log.debug(
                "Tagging with {}".format(tag_names), Log.COMPONENT_CONSUMER)
            document.tags.add(*relevant_tags)

        with open(doc, "rb") as unencrypted:
            with open(document.source_path, "wb") as encrypted:
                Log.debug("Encrypting", Log.COMPONENT_CONSUMER)
                encrypted.write(GnuPG.encrypted(unencrypted))

    def _cleanup(self, tempdir, doc):
        # Remove temporary directory recursively
        Log.debug("Deleting directory {}".format(tempdir), Log.COMPONENT_CONSUMER)
        shutil.rmtree(tempdir)

        # Remove doc
        Log.debug("Deleting document {}".format(doc), Log.COMPONENT_CONSUMER)
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
