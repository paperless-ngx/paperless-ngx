import json
import os
import re
import subprocess

import ocrmypdf
import pdftotext
from PIL import Image
from django.conf import settings
from ocrmypdf import InputFileError, EncryptedPdfError

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

    def is_image(self, mime_type):
        return mime_type in [
            "image/png",
            "image/jpeg",
            "image/tiff",
            "image/bmp",
            "image/gif",
        ]

    def get_dpi(self, image):
        try:
            with Image.open(image) as im:
                x, y = im.info['dpi']
                return x
        except Exception as e:
            self.log(
                'warning',
                f"Error while getting DPI from image {image}: {e}")
            return None

    def parse(self, document_path, mime_type):
        text_original = get_text_from_pdf(document_path)
        has_text = text_original and len(text_original) > 50

        if settings.OCR_MODE == "skip_noarchive" and has_text:
            self.text = text_original
            return

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

        # Mode selection.

        if settings.OCR_MODE in ['skip', 'skip_noarchive']:
            ocr_args['skip_text'] = True
        elif settings.OCR_MODE == 'redo':
            ocr_args['redo_ocr'] = True
        elif settings.OCR_MODE == 'force':
            ocr_args['force_ocr'] = True

        if self.is_image(mime_type):
            dpi = self.get_dpi(document_path)
            if dpi:
                self.log(
                    "debug",
                    f"Detected DPI for image {document_path}: {dpi}"
                )
                ocr_args['image_dpi'] = dpi
            elif settings.OCR_IMAGE_DPI:
                ocr_args['image_dpi'] = settings.OCR_IMAGE_DPI
            else:
                raise ParseError(
                    f"Cannot produce archive PDF for image {document_path}, "
                    f"no DPI information is present in this image and "
                    f"OCR_IMAGE_DPI is not set.")

        if settings.OCR_USER_ARGS:
            try:
                user_args = json.loads(settings.OCR_USER_ARGS)
                ocr_args = {**ocr_args, **user_args}
            except Exception as e:
                self.log(
                    "warning",
                    f"There is an issue with PAPERLESS_OCR_USER_ARGS, so "
                    f"they will not be used: {e}")

        # This forces tesseract to use one core per page.
        os.environ['OMP_THREAD_LIMIT'] = "1"

        try:
            self.log("debug",
                     f"Calling OCRmyPDF with {str(ocr_args)}")
            ocrmypdf.ocr(**ocr_args)
            # success! announce results
            self.archive_path = archive_path
            self.text = get_text_from_pdf(archive_path)

        except (InputFileError, EncryptedPdfError) as e:
            # This happens with some PDFs when used with the redo_ocr option.
            # This is not the end of the world, we'll just use what we already
            # have in the document.
            self.text = text_original
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
                f"without text, or something is wrong with this document.")
            self.text = ""


def strip_excess_whitespace(text):
    if not text:
        return None

    collapsed_spaces = re.sub(r"([^\S\r\n]+)", " ", text)
    no_leading_whitespace = re.sub(
        r"([\n\r]+)([^\S\n\r]+)", '\\1', collapsed_spaces)
    no_trailing_whitespace = re.sub(
        r"([^\S\n\r]+)$", '', no_leading_whitespace)

    # TODO: this needs a rework
    return no_trailing_whitespace.strip()


def get_text_from_pdf(pdf_file):

    with open(pdf_file, "rb") as f:
        try:
            pdf = pdftotext.PDF(f)
        except pdftotext.Error:
            # might not be a PDF file
            return None

    text = "\n".join(pdf)

    return strip_excess_whitespace(text)
