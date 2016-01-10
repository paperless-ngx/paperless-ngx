import datetime
import glob
import gnupg
import os
import random
import re
import subprocess
import time

import pyocr

from PIL import Image

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from documents.models import Document


class Command(BaseCommand):
    """
    Loop over every file found in CONSUMPTION_DIR and:
      1. Convert it to a greyscale png
      2. Use tesseract on the png
      3. Encrypt and store the PDF in the MEDIA_ROOT
      4. Store the OCR'd text in the database
      5. Delete the pdf and image(s)
    """

    LOOP_TIME = 10  # Seconds

    CONVERT = settings.CONVERT_BINARY
    SCRATCH = settings.SCRATCH_DIR
    CONSUME = settings.CONSUMPTION_DIR

    OCR = pyocr.get_available_tools()[0]
    MEDIA_PDF = os.path.join(settings.MEDIA_ROOT, "documents", "pdf")

    PARSER_REGEX = re.compile(r"^.*/(.*) - (.*)\.pdf$")

    def __init__(self, *args, **kwargs):
        self.verbosity = 0
        self.stats = {}
        self.gpg = gnupg.GPG(gnupghome=settings.GNUPG_HOME)
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

        for pdf in os.listdir(self.CONSUME):

            pdf = os.path.join(self.CONSUME, pdf)

            if not os.path.isfile(pdf):
                continue

            if not pdf.endswith(".pdf"):
                continue

            if self._is_ready(pdf):
                continue

            self._render("Consuming {}".format(pdf), 1)

            pngs = self._get_greyscale(pdf)
            text = self._get_ocr(pngs)

            self._store(text, pdf)
            self._cleanup(pngs, pdf)

    def _setup(self):
        for d in (self.SCRATCH, self.MEDIA_PDF):
            try:
                os.makedirs(d)
            except FileExistsError:
                pass

    def _is_ready(self, pdf):
        """
        Detect whether `pdf` is ready to consume or if it's still being written
        to by the scanner.
        """

        t = os.stat(pdf).st_mtime

        if self.stats.get(pdf) == t:
            del(self.stats[pdf])
            return True

        self.stats[pdf] = t

        return False

    def _get_greyscale(self, pdf):

        self._render("  Generating greyscale image", 2)

        i = random.randint(1000000, 9999999)
        png = os.path.join(self.SCRATCH, "{}.png".format(i))

        subprocess.Popen((
            self.CONVERT, "-density", "300", "-depth", "8",
            "-type", "grayscale", pdf, png
        )).wait()

        return sorted(glob.glob(os.path.join(self.SCRATCH, "{}*".format(i))))

    def _get_ocr(self, pngs):

        self._render("  OCRing the PDF", 2)

        r = ""
        for png in pngs:
            with Image.open(os.path.join(self.SCRATCH, png)) as f:
                self._render("    {}".format(f.filename), 3)
                r += self.OCR.image_to_string(f)
                r += "\n\n\n\n\n\n\n\n"

        return r

    def _store(self, text, pdf):

        sender, title = self._parse_file_name(pdf)

        stats = os.stat(pdf)

        self._render("  Saving record to database", 2)

        doc = Document.objects.create(
            sender=sender,
            title=title,
            content=text,
            created=timezone.make_aware(
                datetime.datetime.fromtimestamp(stats.st_mtime)),
            modified=timezone.make_aware(
                datetime.datetime.fromtimestamp(stats.st_mtime))
        )

        with open(pdf, "rb") as unencrypted:
            with open(doc.pdf_path, "wb") as encrypted:
                self._render("  Encrypting", 3)
                encrypted.write(self.gpg.encrypt_file(
                    unencrypted,
                    recipients=None,
                    passphrase=settings.PASSPHRASE,
                    symmetric=True
                ).data)

    def _parse_file_name(self, pdf):
        """
        We use a crude naming convention to make handling the sender and title
        easier:
          "sender - title.pdf"
        """

        m = re.match(self.PARSER_REGEX, pdf)
        if m:
            return m.group(1), m.group(2)

        return "", ""

    def _cleanup(self, pngs, pdf):

        png_glob = os.path.join(
            self.SCRATCH, re.sub(r"^.*/(\d+)-\d+.png$", "\\1*", pngs[0]))

        for f in list(glob.glob(png_glob)) + [pdf]:
            self._render("  Deleting {}".format(f), 2)
            os.unlink(f)

    def _render(self, text, verbosity):
        if self.verbosity >= verbosity:
            print(text)
