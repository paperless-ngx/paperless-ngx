import itertools
import os
import re
import subprocess
from multiprocessing.pool import ThreadPool

import langdetect
import pdftotext
import pyocr
from PIL import Image
from django.conf import settings
from pyocr import PyocrException

from documents.parsers import DocumentParser, ParseError, run_unpaper, \
    run_convert
from .languages import ISO639


class OCRError(Exception):
    pass


class RasterisedDocumentParser(DocumentParser):
    """
    This parser uses Tesseract to try and get some text out of a rasterised
    image, whether it's a PDF, or other graphical format (JPEG, TIFF, etc.)
    """

    def __init__(self, path, logging_group):
        super().__init__(path, logging_group)
        self._text = None

    def get_thumbnail(self):
        """
        The thumbnail of a PDF is just a 500px wide image of the first page.
        """

        out_path = os.path.join(self.tempdir, "convert.png")

        # Run convert to get a decent thumbnail
        try:
            run_convert(density=300,
                        scale="500x5000>",
                        alpha="remove",
                        strip=True,
                        trim=True,
                        input_file="{}[0]".format(self.document_path),
                        output_file=out_path,
                        logging_group=self.logging_group)
        except ParseError:
            # if convert fails, fall back to extracting
            # the first PDF page as a PNG using Ghostscript
            self.log('warning', 'Thumbnail generation with ImageMagick failed, falling back to ghostscript. Check your /etc/ImageMagick-x/policy.xml!')
            gs_out_path = os.path.join(self.tempdir, "gs_out.png")
            cmd = [settings.GS_BINARY,
                   "-q",
                   "-sDEVICE=pngalpha",
                   "-o", gs_out_path,
                   self.document_path]
            if not subprocess.Popen(cmd).wait() == 0:
                raise ParseError("Thumbnail (gs) failed at {}".format(cmd))
            # then run convert on the output from gs
            run_convert(density=300,
                        scale="500x5000>",
                        alpha="remove",
                        strip=True,
                        trim=True,
                        input_file=gs_out_path,
                        output_file=out_path,
                        logging_group=self.logging_group)

        return out_path

    def _is_ocred(self):

        # Extract text from PDF using pdftotext
        text = get_text_from_pdf(self.document_path)

        # We assume, that a PDF with at least 50 characters contains text
        # (so no OCR required)
        return len(text) > 50

    def get_text(self):

        if self._text is not None:
            return self._text

        if not settings.OCR_ALWAYS and self._is_ocred():
            self.log("info", "Skipping OCR, using Text from PDF")
            self._text = get_text_from_pdf(self.document_path)
            return self._text

        images = self._get_greyscale()

        if not images:
            raise ParseError("Empty document, nothing to do.")

        try:

            sample_page_index = int(len(images) / 2)
            self.log("info", "Attempting language detection on page {} of {}...".format(sample_page_index + 1, len(images)))
            sample_page_text = self._ocr([images[sample_page_index]], settings.OCR_LANGUAGE)[0]
            guessed_language = self._guess_language(sample_page_text)

            if not guessed_language or guessed_language not in ISO639:
                self.log("warning", "Language detection failed.")
                ocr_pages = self._complete_ocr_default_language(images, sample_page_index, sample_page_text)

            elif ISO639[guessed_language] == settings.OCR_LANGUAGE:
                self.log("info", "Detected language: {} (default language)".format(guessed_language))
                ocr_pages = self._complete_ocr_default_language(images, sample_page_index, sample_page_text)

            elif not ISO639[guessed_language] in pyocr.get_available_tools()[0].get_available_languages():
                self.log("warning", "Detected language {} is not available on this system.".format(guessed_language))
                ocr_pages = self._complete_ocr_default_language(images, sample_page_index, sample_page_text)

            else:
                self.log("info", "Detected language: {}".format(guessed_language))
                ocr_pages = self._ocr(images, ISO639[guessed_language])

            self.log("info", "OCR completed.")
            self._text = strip_excess_whitespace(" ".join(ocr_pages))
            return self._text

        except OCRError as e:
            raise ParseError(e)

    def _get_greyscale(self):
        """
        Greyscale images are easier for Tesseract to OCR
        """

        self.log("info", "Converting document {} into greyscale images...".format(self.document_path))

        # Convert PDF to multiple PNMs
        pnm = os.path.join(self.tempdir, "convert-%04d.pnm")

        run_convert(density=settings.CONVERT_DENSITY,
                    depth="8",
                    type="grayscale",
                    input_file=self.document_path,
                    output_file=pnm,
                    logging_group=self.logging_group)

        # Get a list of converted images
        pnms = []
        for f in os.listdir(self.tempdir):
            if f.endswith(".pnm"):
                pnms.append(os.path.join(self.tempdir, f))

        self.log("info", "Running unpaper on {} pages...".format(len(pnms)))

        # Run unpaper in parallel on converted images
        with ThreadPool(processes=settings.THREADS_PER_WORKER) as pool:
            pnms = pool.map(run_unpaper, pnms)

        return sorted(filter(lambda __: os.path.isfile(__), pnms))

    def _guess_language(self, text):
        try:
            guess = langdetect.detect(text)
            return guess
        except Exception as e:
            self.log('debug', "Language detection failed with: {}".format(e))
            return None

    def _ocr(self, imgs, lang):
        self.log("info", "Performing OCR on {} page(s) with language {}".format(len(imgs), lang))
        with ThreadPool(processes=settings.THREADS_PER_WORKER) as pool:
            r = pool.map(image_to_string, itertools.product(imgs, [lang]))
            return r

    def _complete_ocr_default_language(self, images, sample_page_index, sample_page):
        """
        Given a `middle` value and the text that middle page represents, we OCR
        the remainder of the document and return the whole thing.
        """
        # text = self._ocr(imgs[:middle], settings.OCR_LANGUAGE) + text
        # text += self._ocr(imgs[middle + 1:], settings.OCR_LANGUAGE)
        images_copy = list(images)
        del images_copy[sample_page_index]
        if images_copy:
            self.log('info', 'Continuing ocr with default language.')
            ocr_pages = self._ocr(images_copy, settings.OCR_LANGUAGE)
            ocr_pages.insert(sample_page_index, sample_page)
            return ocr_pages
        else:
            return [sample_page]


def strip_excess_whitespace(text):
    collapsed_spaces = re.sub(r"([^\S\r\n]+)", " ", text)
    no_leading_whitespace = re.sub(
        r"([\n\r]+)([^\S\n\r]+)", '\\1', collapsed_spaces)
    no_trailing_whitespace = re.sub(
        r"([^\S\n\r]+)$", '', no_leading_whitespace)
    return no_trailing_whitespace


def image_to_string(args):
    img, lang = args
    ocr = pyocr.get_available_tools()[0]
    with Image.open(img) as f:
        if ocr.can_detect_orientation():
            try:
                orientation = ocr.detect_orientation(f, lang=lang)
                f = f.rotate(orientation["angle"], expand=1)
            except Exception:
                # Rotation not possible, ignore
                pass
        try:
            return ocr.image_to_string(f, lang=lang)
        except PyocrException as e:
            raise OCRError(e)


def get_text_from_pdf(pdf_file):

    with open(pdf_file, "rb") as f:
        try:
            pdf = pdftotext.PDF(f)
        except pdftotext.Error:
            return ""

    return "\n".join(pdf)
