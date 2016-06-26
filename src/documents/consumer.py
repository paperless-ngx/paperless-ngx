import datetime
import hashlib
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
from pyocr.tesseract import TesseractError

from paperless.db import GnuPG

from .models import Tag, Document, FileInfo
from .languages import ISO639
from .signals import (
    document_consumption_started, document_consumption_finished)


class OCRError(Exception):
    pass


class ConsumerError(Exception):
    pass


class Consumer(object):
    """
    Loop over every file found in CONSUMPTION_DIR and:
      1. Convert it to a greyscale pnm
      2. Use tesseract on the pnm
      3. Encrypt and store the document in the MEDIA_ROOT
      4. Store the OCR'd text in the database
      5. Delete the document and image(s)
    """

    SCRATCH = settings.SCRATCH_DIR
    CONVERT = settings.CONVERT_BINARY
    UNPAPER = settings.UNPAPER_BINARY
    CONSUME = settings.CONSUMPTION_DIR
    THREADS = int(settings.OCR_THREADS) if settings.OCR_THREADS else None
    DENSITY = settings.CONVERT_DENSITY if settings.CONVERT_DENSITY else 300

    DEFAULT_OCR_LANGUAGE = settings.OCR_LANGUAGE

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
            "group": self.logging_group
        })

    def consume(self):

        for doc in os.listdir(self.CONSUME):

            doc = os.path.join(self.CONSUME, doc)

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

            self.logging_group = uuid.uuid4()

            self.log("info", "Consuming {}".format(doc))

            document_consumption_started.send(
                sender=self.__class__,
                filename=doc,
                logging_group=self.logging_group
            )

            tempdir = tempfile.mkdtemp(prefix="paperless", dir=self.SCRATCH)
            imgs = self._get_greyscale(tempdir, doc)
            thumbnail = self._get_thumbnail(tempdir, doc)

            try:

                document = self._store(self._get_ocr(imgs), doc, thumbnail)

            except OCRError as e:

                self._ignore.append(doc)
                self.log("error", "OCR FAILURE for {}: {}".format(doc, e))
                self._cleanup_tempdir(tempdir)

                continue

            else:

                self._cleanup_tempdir(tempdir)
                self._cleanup_doc(doc)

                document_consumption_finished.send(
                    sender=self.__class__,
                    document=document,
                    logging_group=self.logging_group
                )

    def _get_greyscale(self, tempdir, doc):
        """
        Greyscale images are easier for Tesseract to OCR
        """

        self.log("info", "Generating greyscale image from {}".format(doc))

        # Convert PDF to multiple PNMs
        pnm = os.path.join(tempdir, "convert-%04d.pnm")
        run_convert(
            self.CONVERT,
            "-density", str(self.DENSITY),
            "-depth", "8",
            "-type", "grayscale",
            doc, pnm,
        )

        # Get a list of converted images
        pnms = []
        for f in os.listdir(tempdir):
            if f.endswith(".pnm"):
                pnms.append(os.path.join(tempdir, f))

        # Run unpaper in parallel on converted images
        with Pool(processes=self.THREADS) as pool:
            pool.map(run_unpaper, itertools.product([self.UNPAPER], pnms))

        # Return list of converted images, processed with unpaper
        pnms = []
        for f in os.listdir(tempdir):
            if f.endswith(".unpaper.pnm"):
                pnms.append(os.path.join(tempdir, f))

        return sorted(filter(lambda __: os.path.isfile(__), pnms))

    def _get_thumbnail(self, tempdir, doc):
        """
        The thumbnail of a PDF is just a 500px wide image of the first page.
        """

        self.log("info", "Generating the thumbnail")

        run_convert(
            self.CONVERT,
            "-scale", "500x5000",
            "-alpha", "remove",
            doc, os.path.join(tempdir, "convert-%04d.png")
        )

        return os.path.join(tempdir, "convert-0000.png")

    def _guess_language(self, text):
        try:
            guess = langdetect.detect(text)
            self.log("debug", "Language detected: {}".format(guess))
            return guess
        except Exception as e:
            self.log("warning", "Language detection error: {}".format(e))

    def _get_ocr(self, imgs):
        """
        Attempts to do the best job possible OCR'ing the document based on
        simple language detection trial & error.
        """

        if not imgs:
            raise OCRError("No images found")

        self.log("info", "OCRing the document")

        # Since the division gets rounded down by int, this calculation works
        # for every edge-case, i.e. 1
        middle = int(len(imgs) / 2)
        raw_text = self._ocr([imgs[middle]], self.DEFAULT_OCR_LANGUAGE)

        guessed_language = self._guess_language(raw_text)

        if not guessed_language or guessed_language not in ISO639:
            self.log("warning", "Language detection failed!")
            if settings.FORGIVING_OCR:
                self.log(
                    "warning",
                    "As FORGIVING_OCR is enabled, we're going to make the "
                    "best with what we have."
                )
                raw_text = self._assemble_ocr_sections(imgs, middle, raw_text)
                return raw_text
            raise OCRError("Language detection failed")

        if ISO639[guessed_language] == self.DEFAULT_OCR_LANGUAGE:
            raw_text = self._assemble_ocr_sections(imgs, middle, raw_text)
            return raw_text

        try:
            return self._ocr(imgs, ISO639[guessed_language])
        except pyocr.pyocr.tesseract.TesseractError:
            if settings.FORGIVING_OCR:
                self.log(
                    "warning",
                    "OCR for {} failed, but we're going to stick with what "
                    "we've got since FORGIVING_OCR is enabled.".format(
                        guessed_language
                    )
                )
                raw_text = self._assemble_ocr_sections(imgs, middle, raw_text)
                return raw_text
            raise OCRError(
                "The guessed language is not available in this instance of "
                "Tesseract."
            )

    def _assemble_ocr_sections(self, imgs, middle, text):
        """
        Given a `middle` value and the text that middle page represents, we OCR
        the remainder of the document and return the whole thing.
        """
        text = self._ocr(imgs[:middle], self.DEFAULT_OCR_LANGUAGE) + text
        text += self._ocr(imgs[middle + 1:], self.DEFAULT_OCR_LANGUAGE)
        return text

    def _ocr(self, imgs, lang):
        """
        Performs a single OCR attempt.
        """

        if not imgs:
            return ""

        self.log("info", "Parsing for {}".format(lang))

        with Pool(processes=self.THREADS) as pool:
            r = pool.map(image_to_string, itertools.product(imgs, [lang]))
            r = " ".join(r)

        # Strip out excess white space to allow matching to go smoother
        return re.sub(r"\s+", " ", r)

    def _store(self, text, doc, thumbnail):

        file_info = FileInfo.from_path(doc)

        stats = os.stat(doc)

        self.log("debug", "Saving record to database")

        with open(doc, "rb") as f:
            document = Document.objects.create(
                correspondent=file_info.correspondent,
                title=file_info.title,
                content=text,
                file_type=file_info.extension,
                checksum=hashlib.md5(f.read()).hexdigest(),
                created=timezone.make_aware(
                    datetime.datetime.fromtimestamp(stats.st_mtime)),
                modified=timezone.make_aware(
                    datetime.datetime.fromtimestamp(stats.st_mtime))
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

    @staticmethod
    def _is_duplicate(doc):
        with open(doc, "rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        return Document.objects.filter(checksum=checksum).exists()


def image_to_string(args):
    img, lang = args
    ocr = pyocr.get_available_tools()[0]
    with Image.open(os.path.join(Consumer.SCRATCH, img)) as f:
        if ocr.can_detect_orientation():
            try:
                orientation = ocr.detect_orientation(f, lang=lang)
                f = f.rotate(orientation["angle"], expand=1)
            except TesseractError:
                pass
        return ocr.image_to_string(f, lang=lang)


def run_unpaper(args):
    unpaper, pnm = args
    subprocess.Popen(
        (unpaper, pnm, pnm.replace(".pnm", ".unpaper.pnm"))).wait()


def run_convert(*args):

    environment = os.environ.copy()
    if settings.CONVERT_MEMORY_LIMIT:
        environment["MAGICK_MEMORY_LIMIT"] = settings.CONVERT_MEMORY_LIMIT
    if settings.CONVERT_TMPDIR:
        environment["MAGICK_TMPDIR"] = settings.CONVERT_TMPDIR

    subprocess.Popen(args, env=environment).wait()
