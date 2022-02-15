import json
import os
import re

from PIL import Image
from django.conf import settings

from documents.parsers import DocumentParser, ParseError, \
    make_thumbnail_from_pdf


class NoTextFoundException(Exception):
    pass


class RasterisedDocumentParser(DocumentParser):
    """
    This parser uses Tesseract to try and get some text out of a rasterised
    image, whether it's a PDF, or other graphical format (JPEG, TIFF, etc.)
    """

    logging_name = "paperless.parsing.tesseract"

    def extract_metadata(self, document_path, mime_type):

        result = []
        if mime_type == 'application/pdf':
            import pikepdf

            namespace_pattern = re.compile(r"\{(.*)\}(.*)")

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

    def get_thumbnail(self, document_path, mime_type, file_name=None):
        return make_thumbnail_from_pdf(
            self.archive_path or document_path,
            self.tempdir,
            self.logging_group)

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
                return round(x)
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

    def extract_text(self, sidecar_file, pdf_file):
        if sidecar_file and os.path.isfile(sidecar_file):
            with open(sidecar_file, "r") as f:
                text = f.read()

            if "[OCR skipped on page" not in text:
                # This happens when there's already text in the input file.
                # The sidecar file will only contain text for OCR'ed pages.
                self.log("debug", "Using text from sidecar file")
                return post_process_text(text)
            else:
                self.log("debug", "Incomplete sidecar file: discarding.")

        # no success with the sidecar file, try PDF

        if not os.path.isfile(pdf_file):
            return None

        from pdfminer.high_level import extract_text as pdfminer_extract_text
        from pdfminer.pdftypes import PDFException

        try:
            stripped = post_process_text(pdfminer_extract_text(pdf_file))

            self.log("debug", f"Extracted text from PDF file {pdf_file}")
            return stripped
        except Exception:
            # TODO catch all for various issues with PDFminer.six.
            #  If PDFminer fails, fall back to OCR.
            self.log("warn",
                     "Error while getting text from PDF document with "
                     "pdfminer.six", exc_info=True)
            # probably not a PDF file.
            return None

    def construct_ocrmypdf_parameters(self,
                                      input_file,
                                      mime_type,
                                      output_file,
                                      sidecar_file,
                                      safe_fallback=False):
        ocrmypdf_args = {
            'input_file': input_file,
            'output_file': output_file,
            # need to use threads, since this will be run in daemonized
            # processes by django-q.
            'use_threads': True,
            'jobs': settings.THREADS_PER_WORKER,
            'language': settings.OCR_LANGUAGE,
            'output_type': settings.OCR_OUTPUT_TYPE,
            'progress_bar': False
        }

        if settings.OCR_MODE == 'force' or safe_fallback:
            ocrmypdf_args['force_ocr'] = True
        elif settings.OCR_MODE in ['skip', 'skip_noarchive']:
            ocrmypdf_args['skip_text'] = True
        elif settings.OCR_MODE == 'redo':
            ocrmypdf_args['redo_ocr'] = True
        else:
            raise ParseError(
                f"Invalid ocr mode: {settings.OCR_MODE}")

        if settings.OCR_CLEAN == 'clean':
            ocrmypdf_args['clean'] = True
        elif settings.OCR_CLEAN == 'clean-final':
            if settings.OCR_MODE == 'redo':
                ocrmypdf_args['clean'] = True
            else:
                ocrmypdf_args['clean_final'] = True

        if settings.OCR_DESKEW and not settings.OCR_MODE == 'redo':
            ocrmypdf_args['deskew'] = True

        if settings.OCR_ROTATE_PAGES:
            ocrmypdf_args['rotate_pages'] = True
            ocrmypdf_args['rotate_pages_threshold'] = settings.OCR_ROTATE_PAGES_THRESHOLD  # NOQA: E501

        if settings.OCR_PAGES > 0:
            ocrmypdf_args['pages'] = f"1-{settings.OCR_PAGES}"
        else:
            # sidecar is incompatible with pages
            ocrmypdf_args['sidecar'] = sidecar_file

        if self.is_image(mime_type):
            dpi = self.get_dpi(input_file)
            a4_dpi = self.calculate_a4_dpi(input_file)
            if dpi:
                self.log(
                    "debug",
                    f"Detected DPI for image {input_file}: {dpi}"
                )
                ocrmypdf_args['image_dpi'] = dpi
            elif settings.OCR_IMAGE_DPI:
                ocrmypdf_args['image_dpi'] = settings.OCR_IMAGE_DPI
            elif a4_dpi:
                ocrmypdf_args['image_dpi'] = a4_dpi
            else:
                raise ParseError(
                    f"Cannot produce archive PDF for image {input_file}, "
                    f"no DPI information is present in this image and "
                    f"OCR_IMAGE_DPI is not set.")

        if settings.OCR_USER_ARGS and not safe_fallback:
            try:
                user_args = json.loads(settings.OCR_USER_ARGS)
                ocrmypdf_args = {**ocrmypdf_args, **user_args}
            except Exception as e:
                self.log(
                    "warning",
                    f"There is an issue with PAPERLESS_OCR_USER_ARGS, so "
                    f"they will not be used. Error: {e}")

        return ocrmypdf_args

    def parse(self, document_path, mime_type, file_name=None):
        # This forces tesseract to use one core per page.
        os.environ['OMP_THREAD_LIMIT'] = "1"

        if mime_type == "application/pdf":
            text_original = self.extract_text(None, document_path)
            original_has_text = text_original and len(text_original) > 50
        else:
            text_original = None
            original_has_text = False

        if settings.OCR_MODE == "skip_noarchive" and original_has_text:
            self.log("debug",
                     "Document has text, skipping OCRmyPDF entirely.")
            self.text = text_original
            return

        import ocrmypdf
        from ocrmypdf import InputFileError, EncryptedPdfError

        archive_path = os.path.join(self.tempdir, "archive.pdf")
        sidecar_file = os.path.join(self.tempdir, "sidecar.txt")

        args = self.construct_ocrmypdf_parameters(
            document_path, mime_type, archive_path, sidecar_file)

        try:
            self.log("debug", f"Calling OCRmyPDF with args: {args}")
            ocrmypdf.ocr(**args)

            self.archive_path = archive_path
            self.text = self.extract_text(sidecar_file, archive_path)

            if not self.text:
                raise NoTextFoundException(
                    "No text was found in the original document")
        except EncryptedPdfError:
            self.log("warning",
                     "This file is encrypted, OCR is impossible. Using "
                     "any text present in the original file.")
            if original_has_text:
                self.text = text_original
        except (NoTextFoundException, InputFileError) as e:
            self.log("warning",
                     f"Encountered an error while running OCR: {str(e)}. "
                     f"Attempting force OCR to get the text.")

            archive_path_fallback = os.path.join(
                self.tempdir, "archive-fallback.pdf")
            sidecar_file_fallback = os.path.join(
                self.tempdir, "sidecar-fallback.txt")

            # Attempt to run OCR with safe settings.

            args = self.construct_ocrmypdf_parameters(
                document_path, mime_type,
                archive_path_fallback, sidecar_file_fallback,
                safe_fallback=True
            )

            try:
                self.log("debug",
                         f"Fallback: Calling OCRmyPDF with args: {args}")
                ocrmypdf.ocr(**args)

                # Don't return the archived file here, since this file
                # is bigger and blurry due to --force-ocr.

                self.text = self.extract_text(
                    sidecar_file_fallback, archive_path_fallback)

            except Exception as e:
                # If this fails, we have a serious issue at hand.
                raise ParseError(f"{e.__class__.__name__}: {str(e)}")

        except Exception as e:
            # Anything else is probably serious.
            raise ParseError(f"{e.__class__.__name__}: {str(e)}")

        # As a last resort, if we still don't have any text for any reason,
        # try to extract the text from the original document.
        if not self.text:
            if original_has_text:
                self.text = text_original
            else:
                self.log(
                    "warning",
                    f"No text was found in {document_path}, the content will "
                    f"be empty."
                )
                self.text = ""


def post_process_text(text):
    if not text:
        return None

    collapsed_spaces = re.sub(r"([^\S\r\n]+)", " ", text)
    no_leading_whitespace = re.sub(
        r"([\n\r]+)([^\S\n\r]+)", '\\1', collapsed_spaces)
    no_trailing_whitespace = re.sub(
        r"([^\S\n\r]+)$", '', no_leading_whitespace)

    # TODO: this needs a rework
    # replace \0 prevents issues with saving to postgres.
    # text may contain \0 when this character is present in PDF files.
    return no_trailing_whitespace.strip().replace("\0", " ")
