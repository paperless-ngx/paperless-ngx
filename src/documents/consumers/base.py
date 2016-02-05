import datetime
import glob
import langdetect
import os
import random
import re
import subprocess

import pyocr

from PIL import Image

from django.conf import settings
from django.utils import timezone
from django.template.defaultfilters import slugify

from paperless.db import GnuPG

from ..models import Sender, Tag, Document
from ..languages import ISO639


class OCRError(Exception):
    pass


class Consumer(object):

    SCRATCH = settings.SCRATCH_DIR
    CONVERT = settings.CONVERT_BINARY

    OCR = pyocr.get_available_tools()[0]
    DEFAULT_OCR_LANGUAGE = settings.OCR_LANGUAGE

    REGEX_TITLE = re.compile(
        r"^.*/(.*)\.(pdf|jpe?g|png|gif|tiff)$",
        flags=re.IGNORECASE
    )
    REGEX_SENDER_TITLE = re.compile(
        r"^.*/(.*) - (.*)\.(pdf|jpe?g|png|gif|tiff)",
        flags=re.IGNORECASE
    )
    REGEX_SENDER_TITLE_TAGS = re.compile(
        r"^.*/(.*) - (.*) - ([a-z\-,])\.(pdf|jpe?g|png|gif|tiff)",
        flags=re.IGNORECASE
    )

    def __init__(self, verbosity=1):

        self.verbosity = verbosity

        try:
            os.makedirs(self.SCRATCH)
        except FileExistsError:
            pass

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
            return r

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
            return get_sender(m.group(1)), m.group(2), [], m.group(3)

        # That didn't work, so we assume sender and tags are None
        m = re.match(self.REGEX_TITLE, parseable)
        return None, m.group(1), [], m.group(2)

    def _store(self, text, doc):

        sender, title, file_type = self._guess_attributes_from_name(doc)

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
