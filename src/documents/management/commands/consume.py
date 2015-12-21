import glob
import os
import random
import re
import shutil
import subprocess
import time

import pyocr

from PIL import Image

from django.conf import settings
from django.core.management.base import BaseCommand

from documents.models import Document


class Command(BaseCommand):
    """
    Loop over every file found in CONSUMPTION_DIR and:
      1. Convert it to a greyscale tif
      2. Convert it to a full-colour jpg
      3. Use tesseract on the tif
      4. Store the OCR'd text in the database along with the paths to the jpg
         and original pdf
      5. Delete the pdf and images
    """

    CONVERT = settings.CONVERT_BINARY
    SCRATCH = settings.SCRATCH_DIR
    CONSUME = settings.CONSUMPTION_DIR

    OCR = pyocr.get_available_tools()[0]

    MEDIA_IMG = os.path.join(settings.MEDIA_ROOT, "documents", "img")
    MEDIA_PDF = os.path.join(settings.MEDIA_ROOT, "documents", "pdf")

    PARSER_REGEX = re.compile(r"^.*/(.*) - (.*)\.pdf$")

    def __init__(self, *args, **kwargs):
        self.verbosity = 0
        self.stats = {}
        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]

        self._setup()

        try:
            while True:
                self.loop()
                time.sleep(10)
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

            if self.verbosity > 1:
                print("Consuming {}".format(pdf))

            pngs = self._get_greyscale(pdf)
            jpgs = self._get_colour(pdf)
            text = self._get_ocr(pngs)

            self._store(text, jpgs, pdf)
            self._cleanup(pngs, jpgs)

    def _setup(self):
        for d in (self.SCRATCH, self.MEDIA_IMG, self.MEDIA_PDF):
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

        i = random.randint(1000000, 4999999)
        png = os.path.join(self.SCRATCH, "{}.png".format(i))

        subprocess.Popen((
            self.CONVERT, "-density", "300", "-depth", "8",
            "-type", "grayscale", pdf, png
        )).wait()

        return sorted(glob.glob(os.path.join(self.SCRATCH, "{}*".format(i))))

    def _get_colour(self, pdf):

        i = random.randint(5000000, 9999999)
        jpg = os.path.join(self.SCRATCH, "{}.jpg".format(i))

        subprocess.Popen((self.CONVERT, pdf, jpg)).wait()

        return sorted(glob.glob(os.path.join(self.SCRATCH, "{}*".format(i))))

    def _get_ocr(self, pngs):

        r = ""
        for png in pngs:
            with Image.open(os.path.join(self.SCRATCH, png)) as f:
                r += self.OCR.image_to_string(f)
                r += "\n\n\n\n\n\n\n\n"

        return r

    def _store(self, text, jpgs, pdf):

        sender, title = self._parse_file_name(pdf)

        doc = Document.objects.create(sender=sender, title=title, content=text)

        shutil.move(jpgs[0], os.path.join(
            self.MEDIA_IMG, "{:07}.jpg".format(doc.pk)))
        shutil.move(pdf, os.path.join(
            self.MEDIA_PDF, "{:07}.pdf".format(doc.pk)))

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

    def _cleanup(self, pngs, jpgs):

        jpg_glob = os.path.join(
            self.SCRATCH, re.sub(r"^.*/(\d+)-\d+.jpg$", "\\1*", jpgs[0]))
        png_glob = os.path.join(
            self.SCRATCH, re.sub(r"^.*/(\d+)-\d+.png$", "\\1*", pngs[0]))

        for f in list(glob.glob(jpg_glob)) + list(glob.glob(png_glob)):
            os.unlink(f)
