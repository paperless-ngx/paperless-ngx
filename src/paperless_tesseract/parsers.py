import os
import re
import subprocess

import ocrmypdf
import pdftotext
from django.conf import settings
from ocrmypdf import InputFileError

from documents.parsers import DocumentParser, ParseError, run_convert


class RasterisedDocumentParser(DocumentParser):
    """
    This parser uses Tesseract to try and get some text out of a rasterised
    image, whether it's a PDF, or other graphical format (JPEG, TIFF, etc.)
    """

    def get_thumbnail(self, document_path, mime_type):
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
                        input_file="{}[0]".format(document_path),
                        output_file=out_path,
                        logging_group=self.logging_group)
        except ParseError:
            # if convert fails, fall back to extracting
            # the first PDF page as a PNG using Ghostscript
            self.log(
                'warning',
                "Thumbnail generation with ImageMagick failed, falling back "
                "to ghostscript. Check your /etc/ImageMagick-x/policy.xml!")
            gs_out_path = os.path.join(self.tempdir, "gs_out.png")
            cmd = [settings.GS_BINARY,
                   "-q",
                   "-sDEVICE=pngalpha",
                   "-o", gs_out_path,
                   document_path]
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

    def get_text(self):

        if self._text:
            return self._text

    def parse(self, document_path, mime_type):
        archive_path = os.path.join(self.tempdir, "archive.pdf")

        ocr_args = {
            'input_file': document_path,
            'output_file': archive_path,
            'use_threads': True,
            'jobs': settings.THREADS_PER_WORKER,
            'language': settings.OCR_LANGUAGE,
            'output_type': settings.OCR_OUTPUT_TYPE,
            'progress_bar': False,
            'clean': True
        }

        if settings.OCR_PAGES > 0:
            ocr_args['pages'] = f"1-{settings.OCR_PAGES}"

        if settings.OCR_MODE == 'skip':
            ocr_args['skip_text'] = True
        elif settings.OCR_MODE == 'redo':
            ocr_args['redo_ocr'] = True
        elif settings.OCR_MODE == 'force':
            ocr_args['force_ocr'] = True

        try:
            ocrmypdf.ocr(**ocr_args)
            # success! announce results
            self.archive_path = archive_path
            self.text = get_text_from_pdf(archive_path)

        except InputFileError as e:
            # This happens with some PDFs when used with the redo_ocr option.
            # This is not the end of the world, we'll just use what we already
            # have in the document.
            self.text = get_text_from_pdf(document_path)
            # Also, no archived file.
            if not self.text:
                # However, if we don't have anything, fail:
                raise ParseError(e)

        except Exception as e:
            # Anything else is probably serious.
            raise ParseError(e)

        if not self.text:
            # This may happen for files that don't have any text.
            self.log(
                'warning',
                f"Document {document_path} does not have any text."
                f"This is probably an error or you tried to add an image "
                f"without text.")
            self.text = ""


def strip_excess_whitespace(text):
    if not text:
        return None

    collapsed_spaces = re.sub(r"([^\S\r\n]+)", " ", text)
    no_leading_whitespace = re.sub(
        r"([\n\r]+)([^\S\n\r]+)", '\\1', collapsed_spaces)
    no_trailing_whitespace = re.sub(
        r"([^\S\n\r]+)$", '', no_leading_whitespace)
    return no_trailing_whitespace


def get_text_from_pdf(pdf_file):

    with open(pdf_file, "rb") as f:
        try:
            pdf = pdftotext.PDF(f)
        except pdftotext.Error:
            return None

    text = "\n".join(pdf)

    return strip_excess_whitespace(text)
