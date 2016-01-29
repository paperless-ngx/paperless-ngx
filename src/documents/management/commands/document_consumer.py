import datetime
import glob
import langdetect
import os
import random
import re
import subprocess
import time

import pyocr

from PIL import Image

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import slugify
from django.utils import timezone

from paperless.db import GnuPG

from ...languages import ISO639
from ...models import Document, Sender, Tag


class OCRError(BaseException):
    pass


class Command(BaseCommand):
    """
    Loop over every file found in CONSUMPTION_DIR and:
      1. Convert it to a greyscale png
      2. Use tesseract on the png
      3. Encrypt and store the document in the MEDIA_ROOT
      4. Store the OCR'd text in the database
      5. Delete the document and image(s)
    """

    LOOP_TIME = 10  # Seconds

    CONVERT = settings.CONVERT_BINARY
    SCRATCH = settings.SCRATCH_DIR
    CONSUME = settings.CONSUMPTION_DIR

    OCR = pyocr.get_available_tools()[0]
    DEFAULT_OCR_LANGUAGE = settings.OCR_LANGUAGE
    MEDIA_DOCS = os.path.join(settings.MEDIA_ROOT, "documents")

    PARSER_REGEX_TITLE = re.compile(
        r"^.*/(.*)\.(pdf|jpe?g|png|gif|tiff)$", flags=re.IGNORECASE)
    PARSER_REGEX_SENDER_TITLE = re.compile(
        r"^.*/(.*) - (.*)\.(pdf|jpe?g|png|gif|tiff)", flags=re.IGNORECASE)

    def __init__(self, *args, **kwargs):

        self.verbosity = 0
        self.stats = {}
        self._ignore = []

        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]

        self._setup()

        try:
            while True:
                self.loop()
                time.sleep(self.LOOP_TIME)
                if self.verbosity > 1:
                    print(".")
        except KeyboardInterrupt:
            print("Exiting")

    def loop(self):

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

    def _setup(self):

        if not self.CONSUME:
            raise CommandError(
                "The CONSUMPTION_DIR settings variable does not appear to be "
                "set."
            )

        if not os.path.exists(self.CONSUME):
            raise CommandError("Consumption directory {} does not exist".format(
                self.CONSUME))

        for d in (self.SCRATCH, self.MEDIA_DOCS):
            try:
                os.makedirs(d)
            except FileExistsError:
                pass

    def _is_ready(self, doc):
        """
        Detect whether `doc` is ready to consume or if it's still being written
        to by the scanner.
        """

        t = os.stat(doc).st_mtime

        if self.stats.get(doc) == t:
            del(self.stats[doc])
            return True

        self.stats[doc] = t

        return False

    def _get_greyscale(self, doc):

        self._render("  Generating greyscale image", 2)

        i = random.randint(1000000, 9999999)
        png = os.path.join(self.SCRATCH, "{}.png".format(i))

        subprocess.Popen((
            self.CONVERT, "-density", "300", "-depth", "8",
            "-type", "grayscale", doc, png
        )).wait()

        return sorted(glob.glob(os.path.join(self.SCRATCH, "{}*".format(i))))

    def _get_ocr(self, pngs):

        self._render("  OCRing the document", 2)

        raw_text = self._ocr(pngs, self.DEFAULT_OCR_LANGUAGE)

        guessed_language = langdetect.detect(raw_text)

        self._render("    Language detected: {}".format(guessed_language), 2)

        if guessed_language not in ISO639:
            self._render("Language detection failed!", 0)
            if settings.FORGIVING_OCR:
                self._render(
                    "As FORGIVING_OCR is enabled, we're going to make the best "
                    "with what we have.",
                    1
                )
                return raw_text
            raise OCRError

        if ISO639[guessed_language] == self.DEFAULT_OCR_LANGUAGE:
            return raw_text

        try:
            return self._ocr(pngs, ISO639[guessed_language])
        except pyocr.pyocr.tesseract.TesseractError:
            if settings.FORGIVING_OCR:
                self._render(
                    "OCR for {} failed, but we're going to stick with what "
                    "we've got since FORGIVING_OCR is enabled.".format(
                        guessed_language
                    ),
                    0
                )
                return raw_text
            raise OCRError

    def _ocr(self, pngs, lang):

        self._render("    Parsing for {}".format(lang), 2)

        r = ""
        for png in pngs:
            with Image.open(os.path.join(self.SCRATCH, png)) as f:
                self._render("    {}".format(f.filename), 3)
                r += self.OCR.image_to_string(f, lang=lang)

        # Strip out excess white space to allow matching to go smoother
        return re.sub(r"\s+", " ", r)

    def _store(self, text, doc):

        sender, title, file_type = self._parse_file_name(doc)

        lower_text = text.lower()
        relevant_tags = [t for t in Tag.objects.all() if t.matches(lower_text)]

        stats = os.stat(doc)

        self._render("  Saving record to database", 2)

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
            self._render("    Tagging with {}".format(tag_names), 2)
            document.tags.add(*relevant_tags)

        with open(doc, "rb") as unencrypted:
            with open(document.source_path, "wb") as encrypted:
                self._render("  Encrypting", 3)
                encrypted.write(GnuPG.encrypted(unencrypted))

    def _parse_file_name(self, doc):
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

    def _cleanup(self, pngs, doc):

        png_glob = os.path.join(
            self.SCRATCH, re.sub(r"^.*/(\d+)-\d+.png$", "\\1*", pngs[0]))

        for f in list(glob.glob(png_glob)) + [doc]:
            self._render("  Deleting {}".format(f), 2)
            os.unlink(f)

        self._render("", 2)

    def _render(self, text, verbosity):
        if self.verbosity >= verbosity:
            print(text)
