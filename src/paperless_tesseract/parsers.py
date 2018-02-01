import itertools
import os
import re
import subprocess
from multiprocessing.pool import Pool
import pdftotext

import langdetect
import pyocr
from django.conf import settings
from documents.parsers import DocumentParser, ParseError
from PIL import Image
from pyocr.libtesseract.tesseract_raw import \
    TesseractError as OtherTesseractError
from pyocr.tesseract import TesseractError

from .languages import ISO639


class OCRError(Exception):
    pass


class RasterisedDocumentParser(DocumentParser):
    """
    This parser uses Tesseract to try and get some text out of a rasterised
    image, whether it's a PDF, or other graphical format (JPEG, TIFF, etc.)
    """

    CONVERT = settings.CONVERT_BINARY
    DENSITY = settings.CONVERT_DENSITY if settings.CONVERT_DENSITY else 300
    THREADS = int(settings.OCR_THREADS) if settings.OCR_THREADS else None
    UNPAPER = settings.UNPAPER_BINARY
    DEFAULT_OCR_LANGUAGE = settings.OCR_LANGUAGE
    OCR_ALWAYS = settings.OCR_ALWAYS

    def get_thumbnail(self):
        """
        The thumbnail of a PDF is just a 500px wide image of the first page.
        """

        run_convert(
            self.CONVERT,
            "-scale", "500x5000",
            "-alpha", "remove",
            self.document_path, os.path.join(self.tempdir, "convert-%04d.png")
        )

        return os.path.join(self.tempdir, "convert-0000.png")

    def _is_ocred(self):
        # Extract text from PDF using pdftotext
        text = get_text_from_pdf(self.document_path)

        # We assume, that a PDF with at least 50 characters contains text
        # (so no OCR required)
        if len(text) > 50:
            return True

        return False

    def get_text(self):
        if not self.OCR_ALWAYS and self._is_ocred():
            self.log("info", "Skipping OCR, using Text from PDF")
            return get_text_from_pdf(self.document_path)

        images = self._get_greyscale()

        try:

            return self._get_ocr(images)
        except OCRError as e:
            raise ParseError(e)

    def _get_greyscale(self):
        """
        Greyscale images are easier for Tesseract to OCR
        """

        # Convert PDF to multiple PNMs
        pnm = os.path.join(self.tempdir, "convert-%04d.pnm")
        run_convert(
            self.CONVERT,
            "-density", str(self.DENSITY),
            "-depth", "8",
            "-type", "grayscale",
            self.document_path, pnm,
        )

        # Get a list of converted images
        pnms = []
        for f in os.listdir(self.tempdir):
            if f.endswith(".pnm"):
                pnms.append(os.path.join(self.tempdir, f))

        # Run unpaper in parallel on converted images
        with Pool(processes=self.THREADS) as pool:
            pool.map(run_unpaper, itertools.product([self.UNPAPER], pnms))

        # Return list of converted images, processed with unpaper
        pnms = []
        for f in os.listdir(self.tempdir):
            if f.endswith(".unpaper.pnm"):
                pnms.append(os.path.join(self.tempdir, f))

        return sorted(filter(lambda __: os.path.isfile(__), pnms))

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
        return strip_excess_whitespace(r)

    def _assemble_ocr_sections(self, imgs, middle, text):
        """
        Given a `middle` value and the text that middle page represents, we OCR
        the remainder of the document and return the whole thing.
        """
        text = self._ocr(imgs[:middle], self.DEFAULT_OCR_LANGUAGE) + text
        text += self._ocr(imgs[middle + 1:], self.DEFAULT_OCR_LANGUAGE)
        return text


def run_convert(*args):

    environment = os.environ.copy()
    if settings.CONVERT_MEMORY_LIMIT:
        environment["MAGICK_MEMORY_LIMIT"] = settings.CONVERT_MEMORY_LIMIT
    if settings.CONVERT_TMPDIR:
        environment["MAGICK_TMPDIR"] = settings.CONVERT_TMPDIR

    subprocess.Popen(args, env=environment).wait()


def run_unpaper(args):
    unpaper, pnm = args
    subprocess.Popen(
        (unpaper, pnm, pnm.replace(".pnm", ".unpaper.pnm"))).wait()


def strip_excess_whitespace(text):
    collapsed_spaces = re.sub(r"([^\S\r\n]+)", " ", text)
    no_leading_whitespace = re.sub(
        "([\n\r]+)([^\S\n\r]+)", '\\1', collapsed_spaces)
    no_trailing_whitespace = re.sub("([^\S\n\r]+)$", '', no_leading_whitespace)
    return no_trailing_whitespace


def image_to_string(args):
    img, lang = args
    ocr = pyocr.get_available_tools()[0]
    with Image.open(os.path.join(RasterisedDocumentParser.SCRATCH, img)) as f:
        if ocr.can_detect_orientation():
            try:
                orientation = ocr.detect_orientation(f, lang=lang)
                f = f.rotate(orientation["angle"], expand=1)
            except (TesseractError, OtherTesseractError):
                pass
        return ocr.image_to_string(f, lang=lang)


def get_text_from_pdf(pdf_file):
    with open(pdf_file, "rb") as f:
        try:
            pdf = pdftotext.PDF(f)
        except pdftotext.Error:
            return False

    return "\n".join(pdf)
