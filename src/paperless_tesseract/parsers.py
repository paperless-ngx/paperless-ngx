import json
import os
import re

import ocrmypdf
import pdftotext
import pikepdf
from PIL import Image
from django.conf import settings
from ocrmypdf import InputFileError, EncryptedPdfError

from documents.parsers import DocumentParser, ParseError, \
    make_thumbnail_from_pdf


class RasterisedDocumentParser(DocumentParser):
    """
    This parser uses Tesseract to try and get some text out of a rasterised
    image, whether it's a PDF, or other graphical format (JPEG, TIFF, etc.)
    """

    def extract_metadata(self, document_path, mime_type):
        namespace_pattern = re.compile(r"\{(.*)\}(.*)")

        result = []
        if mime_type == 'application/pdf':
            pdf = pikepdf.open(document_path)
            meta = pdf.open_metadata()
            for key, value in meta.items():
                if isinstance(value, list):
                    value = " ".join([str(e) for e in value])
                value = str(value)
                try:
                    m = namespace_pattern.match(key)
                    result.append({
                        "namespace": m.group(1),
                        "prefix": meta.REVERSE_NS[m.group(1)],
                        "key": m.group(2),
                        "value": value
                    })
                except Exception as e:
                    self.log(
                        "warning",
                        f"Error while reading metadata {key}: {value}. Error: "
                        f"{e}"
                    )
        return result

    def get_thumbnail(self, document_path, mime_type):
        return make_thumbnail_from_pdf(
            document_path, self.tempdir, self.logging_group)

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

    def calculate_a4_dpi(self, image):
        try:
            with Image.open(image) as im:
                width, height = im.size
                # divide image width by A4 width (210mm) in inches.
                dpi = int(width / (21 / 2.54))
                self.log(
                    'debug',
                    f"Estimated DPI {dpi} based on image width {width}"
                )
                return dpi

        except Exception as e:
            self.log(
                'warning',
                f"Error while calculating DPI for image {image}: {e}")
            return None

    def parse(self, document_path, mime_type, file_name=None):
        mode = settings.OCR_MODE

        text_original = get_text_from_pdf(document_path)
        has_text = text_original and len(text_original) > 50

        if mode == "skip_noarchive" and has_text:
            self.log("debug",
                     "Document has text, skipping OCRmyPDF entirely.")
            self.text = text_original
            return

        if mode in ['skip', 'skip_noarchive'] and not has_text:
            # upgrade to redo, since there appears to be no text in the
            # document. This happens to some weird encrypted documents or
            # documents with failed OCR attempts for which OCRmyPDF will
            # still report that there actually is text in them.
            self.log("debug",
                     "No text was found in the document and skip is "
                     "specified. Upgrading OCR mode to redo.")
            mode = "redo"

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

        if mode in ['skip', 'skip_noarchive']:
            ocr_args['skip_text'] = True
        elif mode == 'redo':
            ocr_args['redo_ocr'] = True
        elif mode == 'force':
            ocr_args['force_ocr'] = True
        else:
            raise ParseError(
                f"Invalid ocr mode: {mode}")

        if self.is_image(mime_type):
            dpi = self.get_dpi(document_path)
            a4_dpi = self.calculate_a4_dpi(document_path)
            if dpi:
                self.log(
                    "debug",
                    f"Detected DPI for image {document_path}: {dpi}"
                )
                ocr_args['image_dpi'] = dpi
            elif settings.OCR_IMAGE_DPI:
                ocr_args['image_dpi'] = settings.OCR_IMAGE_DPI
            elif a4_dpi:
                ocr_args['image_dpi'] = a4_dpi
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

            self.log("debug",
                     f"Encountered an error: {e}. Trying to use text from "
                     f"original.")
            # This happens with some PDFs when used with the redo_ocr option.
            # This is not the end of the world, we'll just use what we already
            # have in the document.
            self.text = text_original
            # Also, no archived file.
            if not self.text:
                # However, if we don't have anything, fail:
                raise ParseError(f"{e.__class__.__name__}: {str(e)}")

        except Exception as e:
            # Anything else is probably serious.
            raise ParseError(f"{e.__class__.__name__}: {str(e)}")

        if not self.text:
            # This may happen for files that don't have any text.
            self.log(
                'warning',
                f"Document {document_path} does not have any text. "
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

    if not os.path.isfile(pdf_file):
        return None

    with open(pdf_file, "rb") as f:
        try:
            pdf = pdftotext.PDF(f)
        except pdftotext.Error:
            # might not be a PDF file
            return None

    text = "\n".join(pdf)

    return strip_excess_whitespace(text)
