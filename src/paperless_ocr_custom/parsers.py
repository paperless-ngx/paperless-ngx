import io
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Optional

import PyPDF2
from django.conf import settings
import requests
from PyPDF2 import PdfFileWriter, PdfFileReader, PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image,ImageDraw,ImageFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

from documents.parsers import DocumentParser
from documents.parsers import ParseError
from documents.parsers import make_thumbnail_from_pdf
from documents.utils import maybe_override_pixel_limit
from documents.utils import run_subprocess
from paperless.config import OcrConfig
from paperless.models import ArchiveFileChoices
from paperless.models import CleanChoices
from paperless.models import ModeChoices


class NoTextFoundException(Exception):
    pass


class RtlLanguageException(Exception):
    pass


class RasterisedDocumentParser(DocumentParser):
    """
    This parser uses Tesseract to try and get some text out of a rasterised
    image, whether it's a PDF, or other graphical format (JPEG, TIFF, etc.)
    """

    logging_name = "paperless.parsing.tesseract"

    def get_settings(self) -> OcrConfig:
        """
        This parser uses the OCR configuration settings to parse documents
        """
        return OcrConfig()

    def extract_metadata(self, document_path, mime_type):
        result = []
        if mime_type == "application/pdf":
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
                    if m is None:  # pragma: no cover
                        continue
                    namespace = m.group(1)
                    key_value = m.group(2)
                    try:
                        namespace.encode("utf-8")
                        key_value.encode("utf-8")
                    except UnicodeEncodeError as e:  # pragma: no cover
                        self.log.debug(f"Skipping metadata key {key}: {e}")
                        continue
                    result.append(
                        {
                            "namespace": namespace,
                            "prefix": meta.REVERSE_NS[namespace],
                            "key": key_value,
                            "value": value,
                        },
                    )
                except Exception as e:
                    self.log.warning(
                        f"Error while reading metadata {key}: {value}. Error: {e}",
                    )
        return result

    def get_thumbnail(self, document_path, mime_type, file_name=None):
        return make_thumbnail_from_pdf(
            self.archive_path or document_path,
            self.tempdir,
            self.logging_group,
        )

    def is_image(self, mime_type) -> bool:
        return mime_type in [
            "image/png",
            "image/jpeg",
            "image/tiff",
            "image/bmp",
            "image/gif",
            "image/webp",
        ]

    def has_alpha(self, image) -> bool:
        with Image.open(image) as im:
            return im.mode in ("RGBA", "LA")

    def remove_alpha(self, image_path: str) -> Path:
        no_alpha_image = Path(self.tempdir) / "image-no-alpha"
        run_subprocess(
            [
                settings.CONVERT_BINARY,
                "-alpha",
                "off",
                image_path,
                no_alpha_image,
            ],
            logger=self.log,
        )
        return no_alpha_image

    def get_dpi(self, image) -> Optional[int]:
        try:
            with Image.open(image) as im:
                x, y = im.info["dpi"]
                return round(x)
        except Exception as e:
            self.log.warning(f"Error while getting DPI from image {image}: {e}")
            return None

    def calculate_a4_dpi(self, image) -> Optional[int]:
        try:
            with Image.open(image) as im:
                width, height = im.size
                # divide image width by A4 width (210mm) in inches.
                dpi = int(width / (21 / 2.54))
                self.log.debug(f"Estimated DPI {dpi} based on image width {width}")
                return dpi

        except Exception as e:
            self.log.warning(f"Error while calculating DPI for image {image}: {e}")
            return None
    # get ocr file img/pdf
    def ocr_file(self,path_file):
        # get text from api 
        ocr_custom_username = settings.TCGROUP_OCR_CUSTOM["ACCOUNT"]["OCR_CUSTOM_USERNAME"]
        ocr_custom_password = settings.TCGROUP_OCR_CUSTOM["ACCOUNT"]["OCR_CUSTOM_PASSWORD"]
        url_login = settings.TCGROUP_OCR_CUSTOM["URL"]["URL_LOGIN"]
        data = {
            'username': ocr_custom_username,
            'password': ocr_custom_password
        }
        response_login = requests.post(url_login, data=data)
        access_token = ''
        if response_login.status_code == 200:
            response_data = response_login.json()
            access_token = response_data.get('access_token','')
        else:
            logging.error('login: ', response_login.status_code)
        
        # upload file
        get_file_id = ''
        url_upload_file = settings.TCGROUP_OCR_CUSTOM["URL"]["URL_UPLOAD_FILE"]
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        pdf_data = None
        with open(path_file, 'rb') as file:
            pdf_data = file.read()
        
        response_upload = requests.post(url_upload_file, files={'file': (str(path_file).split("/")[-1], pdf_data)}, headers=headers)
        # logging.debug('pdf file',response_upload)
        if response_upload.status_code == 200:
            get_file_id = response_upload.json().get('file_id','')
        else:
            logging.error('upload file: ',response_upload.status_code) 

        # ocr by file_id
        # logging.debug('gia tri file id:', get_file_id)
        params = {'file_id': get_file_id}
        url_ocr_pdf_by_fileid = settings.TCGROUP_OCR_CUSTOM["URL"]["URL_OCR_BY_FILEID"]
        response_ocr = requests.post(url_ocr_pdf_by_fileid, headers=headers, params=params)
        data_ocr = None
        
        # logging.error('ocr: ', response_ocr.status_code)

        if response_ocr.status_code == 200:
            data_ocr = response_ocr.json()
        else:
            logging.error('ocr: ', response_ocr.text)

        return data_ocr
    def render_pdf_ocr(self, sidecar, mime_type, input_path, output_path):
        font_name = 'Arial'
        c = None
        data = self.ocr_file(input_path)
        if not data:
                return
        font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'arial-font/arial.ttf')            
        with open(sidecar, "w") as txt_sidecar:
            txt_sidecar.write(data.get("content",""))
        if self.is_image(mime_type):
            img = Image.open(input_path)
            width, height = img.size
            c = canvas.Canvas(str(output_path), pagesize=(width, height))
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            # viet text vao file
            for page in data["pages"]:
                for block in page["blocks"]:
                    for line in block.get("lines", []):
                        for word in line.get("words", []):   
                            x1 = word["bbox"][0][0]
                            y1 = word["bbox"][0][1]
                            x2 = word["bbox"][1][0]
                            y2 = word["bbox"][1][1]
                            value = word["value"]
                            font_size = (y2-y1) * 72 / 96
                            
                            
                            # font = ImageFont.truetype(font_path, font_size)
                            # text = "Hello, world!"
                            # text_width, text_height = font.textsize(text)
                            # print(f"Text width: {text_width}, Text height: {text_height}")
                            x_center_coordinates =x2 - (x2-x1)/2
                            y_center_coordinates =y2 - (y2-y1)/2
                            w = c.stringWidth(value, font_name, font_size)
                            self.log.debug('w:', )
                            c.setFont('Arial', font_size)
                            c.drawString(x_center_coordinates - w/2 , height - y_center_coordinates - (font_size/2) , value)            
            c.drawImage(input_path, 0, 0, width=width, height=height)
            c.save()
        else:
            shutil.copy(str(input_path), str(output_path))
            output_pdf = PdfWriter()
            input_pdf = PdfReader(output_path)
            
            for page_num, page in enumerate(input_pdf.pages):
                page_height = input_pdf.pages[page_num].mediabox[3]
                page_width = input_pdf.pages[page_num].mediabox[2]
                
                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=letter)
                pdfmetrics.registerFont(TTFont('Arial', font_path))
                width_api_img = data["pages"][page_num]["dimensions"][1]
                height_api_img = data["pages"][page_num]["dimensions"][0]
                rolate_height =  height_api_img /page_height
                rolate_width = width_api_img /page_width
                for block in data["pages"][page_num]["blocks"]:
                    for line in block.get("lines", []):
                        for word in line.get("words", []):   
                            x1 = word["bbox"][0][0] / float(rolate_width)
                            y1 = word["bbox"][0][1] / float(rolate_height)
                            x2 = word["bbox"][1][0] / float(rolate_width)
                            y2 = word["bbox"][1][1] / float(rolate_height)
                            value = word["value"]
                            font_size = float(y2-y1) * 72 / 96 
                            x_center_coordinates =x2 - (x2-x1)/2
                            y_center_coordinates =y2 - (y2-y1)/2
                            w = can.stringWidth(value, font_name, font_size)
                            can.setFont('Arial', font_size)
                            can.drawString(x_center_coordinates - w/2 , int(page_height) - y_center_coordinates - (font_size/2) , value)            

                can.showPage()
                can.save()
                packet.seek(0)
                new_pdf = PdfReader(packet)
                page.merge_page(new_pdf.pages[0])

                output_pdf.add_page(page)

            output_pdf.write(output_path)
        shutil.copyfile(str(output_path), "/home/otxtan/python/opt/paperless/pdfa.pdf")

    # create pdf from image 
    def pdf_create_layer_text(self, sidecar, input_path, output_path):
        


        packet = io.BytesIO()
        # test
        
        c = Canvas(packet, pagesize=letter)

        # get data 
        data = self.ocr_file(input_path)
        if not data:
            return PdfFileReader(packet)
        # viet text vao file
        with open(sidecar, "w") as txt_sidecar:
            txt_sidecar.write(data.get("content",""))

        for page in data["pages"]:
            if "blocks" in page:
                for block in page["blocks"]:
                    for word in block.get("words",[]):
                        x1 = word["bbox"][0][0]
                        y1 = word["bbox"][0][1]
                        x2 = word["bbox"][1][0]
                        y2 = word["bbox"][1][1]
                        value = word["value"]
                        c.drawString(x1, y1, value)            
            c.showPage()
        c.save()
        packet.seek(0)
        return PdfFileReader(packet)

    # Tạo lớp 2 (nội dung)
    def merge_pdfs(self, mime_type, input_path, output_path, overlay):
        pdf = None
        if self.is_image(mime_type):
            packet = io.BytesIO()
            img = Image.open(input_path)
            width, height = img.size
            c = canvas.Canvas(packet, pagesize=(width, height))
            c.drawImage(input_path, 0, 0, width=width, height=height)
            c.save()
            packet.seek(0)
            pdf = PdfFileReader(packet)
        else:    
            pdf = PdfFileReader(input_path)
        pdf_writer = PdfFileWriter()

        for page_number in range(pdf.getNumPages()):
            page = pdf.getPage(page_number)
            page.mergePage(overlay.getPage(page_number))
            pdf_writer.addPage(page)

        with open(output_path, 'wb') as out:
            pdf_writer.write(out)
        with open("/home/otxtan/python/opt/paperless/pdfa.pdf", 'wb') as f:
            pdf_writer.write(f)
        # 
        pdf_writer1 = PdfFileWriter()
        for page_num in range(pdf.numPages):
            page = pdf.getPage(page_num)
            pdf_writer1.addPage(page)

        with open("/home/otxtan/python/opt/paperless/pdfa1.pdf", 'wb') as output_file:
            pdf_writer1.write(output_file)
            
    def ocr_img_or_pdf(self, document_path, mime_type, sidecar, output_file, **kwargs):
        self.log.info('mime_type:',mime_type)
        # overlay_text = self.pdf_create_layer_text(sidecar, document_path, output_file)
        # self.merge_pdfs(mime_type, input_path = document_path, output_path = output_file, overlay = overlay_text)
        self.render_pdf_ocr(sidecar, mime_type, document_path, output_file)
     

    def extract_text(
        self,
        sidecar_file: Optional[Path],
        pdf_file: Path,
    ) -> Optional[str]:
        # When re-doing OCR, the sidecar contains ONLY the new text, not
        # the whole text, so do not utilize it in that case
        logging.info('đã vào: ',sidecar_file)  
        if (
            sidecar_file is not None
            and os.path.isfile(sidecar_file)
            and self.settings.mode != "redo"
        ):
            text = self.read_file_handle_unicode_errors(sidecar_file)

            if "[OCR skipped on page" not in text:
                # This happens when there's already text in the input file.
                # The sidecar file will only contain text for OCR'ed pages.
                self.log.debug("Using text from sidecar file")
                return post_process_text(text)
            else:
                self.log.debug("Incomplete sidecar file: discarding.")

        # no success with the sidecar file, try PDF

        if not os.path.isfile(pdf_file):
            return None

        try:
            text = None
            with tempfile.NamedTemporaryFile(
                mode="w+",
                dir=self.tempdir,
            ) as tmp:
                run_subprocess(
                    [
                        "pdftotext",
                        "-q",
                        "-layout",
                        "-enc",
                        "UTF-8",
                        pdf_file,
                        tmp.name,
                    ],
                    logger=self.log,
                )
            text = self.read_file_handle_unicode_errors(Path(tmp.name))
            
            # data_ocr = self.ocr_file(pdf_file).get('content','')
            # if not data_ocr:
            #     data_ocr = ''        

            # logging.info()    
            return post_process_text(text)

        except Exception:
            #  If pdftotext fails, fall back to OCR.
            self.log.warning(
                "Error while getting text from PDF document with pdftotext",
                exc_info=True,
            )
            # probably not a PDF file.
            return None

    def construct_ocrmypdf_parameters(
        self,
        input_file,
        mime_type,
        output_file,
        sidecar_file,
        safe_fallback=False,
    ):
        if TYPE_CHECKING:
            assert isinstance(self.settings, OcrConfig)
        ocrmypdf_args = {
            "input_file": input_file,
            "output_file": output_file,
            # need to use threads, since this will be run in daemonized
            # processes via the task library.
            "use_threads": True,
            "jobs": settings.THREADS_PER_WORKER,
            "language": self.settings.language,
            "output_type": self.settings.output_type,
            "progress_bar": False,
        }

        if "pdfa" in ocrmypdf_args["output_type"]:
            ocrmypdf_args["color_conversion_strategy"] = (
                self.settings.color_conversion_strategy
            )

        if self.settings.mode == ModeChoices.FORCE or safe_fallback:
            ocrmypdf_args["force_ocr"] = True
        elif self.settings.mode in {
            ModeChoices.SKIP,
            ModeChoices.SKIP_NO_ARCHIVE,
        }:
            ocrmypdf_args["skip_text"] = True
        elif self.settings.mode == ModeChoices.REDO:
            ocrmypdf_args["redo_ocr"] = True
        else:  # pragma: no cover
            raise ParseError(f"Invalid ocr mode: {self.settings.mode}")

        if self.settings.clean == CleanChoices.CLEAN:
            ocrmypdf_args["clean"] = True
        elif self.settings.clean == CleanChoices.FINAL:
            if self.settings.mode == ModeChoices.REDO:
                ocrmypdf_args["clean"] = True
            else:
                # --clean-final is not compatible with --redo-ocr
                ocrmypdf_args["clean_final"] = True

        if self.settings.deskew and self.settings.mode != ModeChoices.REDO:
            # --deskew is not compatible with --redo-ocr
            ocrmypdf_args["deskew"] = True

        if self.settings.rotate:
            ocrmypdf_args["rotate_pages"] = True
            ocrmypdf_args["rotate_pages_threshold"] = self.settings.rotate_threshold

        if self.settings.pages is not None and self.settings.pages > 0:
            ocrmypdf_args["pages"] = f"1-{self.settings.pages}"
        else:
            # sidecar is incompatible with pages
            ocrmypdf_args["sidecar"] = sidecar_file

        if self.is_image(mime_type):
            # This may be required, depending on the known imformation
            maybe_override_pixel_limit()

            dpi = self.get_dpi(input_file)
            a4_dpi = self.calculate_a4_dpi(input_file)

            if self.has_alpha(input_file):
                self.log.info(
                    f"Removing alpha layer from {input_file} "
                    "for compatibility with img2pdf",
                )
                # Replace the input file with the non-alpha
                ocrmypdf_args["input_file"] = self.remove_alpha(input_file)

            if dpi:
                self.log.debug(f"Detected DPI for image {input_file}: {dpi}")
                ocrmypdf_args["image_dpi"] = dpi
            elif self.settings.image_dpi is not None:
                ocrmypdf_args["image_dpi"] = self.settings.image_dpi
            elif a4_dpi:
                ocrmypdf_args["image_dpi"] = a4_dpi
            else:
                raise ParseError(
                    f"Cannot produce archive PDF for image {input_file}, "
                    f"no DPI information is present in this image and "
                    f"OCR_IMAGE_DPI is not set.",
                )
            if ocrmypdf_args["image_dpi"] < 70:  # pragma: no cover
                self.log.warning(
                    f"Image DPI of {ocrmypdf_args['image_dpi']} is low, OCR may fail",
                )

        if self.settings.user_args is not None:
            try:
                ocrmypdf_args = {**ocrmypdf_args, **self.settings.user_args}
            except Exception as e:
                self.log.warning(
                    f"There is an issue with PAPERLESS_OCR_USER_ARGS, so "
                    f"they will not be used. Error: {e}",
                )

        if (
            self.settings.max_image_pixel is not None
            and self.settings.max_image_pixel >= 0
        ):
            # Convert pixels to mega-pixels and provide to ocrmypdf
            max_pixels_mpixels = self.settings.max_image_pixel / 1_000_000.0
            msg = (
                "OCR pixel limit is disabled!"
                if max_pixels_mpixels == 0
                else f"Calculated {max_pixels_mpixels} megapixels for OCR"
            )
            self.log.debug(msg)
            ocrmypdf_args["max_image_mpixels"] = max_pixels_mpixels

        return ocrmypdf_args

    def parse(self, document_path: Path, mime_type, file_name=None):
        # This forces tesseract to use one core per page.
        os.environ["OMP_THREAD_LIMIT"] = "1"
        VALID_TEXT_LENGTH = 50

        if mime_type == "application/pdf":
            text_original = self.extract_text(None, document_path)
            original_has_text = (
                text_original is not None and len(text_original) > VALID_TEXT_LENGTH
            )
        else:
            text_original = None
            original_has_text = False

        # If the original has text, and the user doesn't want an archive,
        # we're done here
        skip_archive_for_text = (
            self.settings.mode == ModeChoices.SKIP_NO_ARCHIVE
            or self.settings.skip_archive_file
            in {
                ArchiveFileChoices.WITH_TEXT,
                ArchiveFileChoices.ALWAYS,
            }
        )
        if skip_archive_for_text and original_has_text:
            self.log.debug("Document has text, skipping OCRmyPDF entirely.")
            self.text = text_original
            return

        # Either no text was in the original or there should be an archive
        # file created, so OCR the file and create an archive with any
        # text located via OCR

        import ocrmypdf
        from ocrmypdf import EncryptedPdfError
        from ocrmypdf import InputFileError
        from ocrmypdf import SubprocessOutputError

        archive_path = Path(os.path.join(self.tempdir, "archive.pdf"))
        sidecar_file = Path(os.path.join(self.tempdir, "sidecar.txt"))

        args = self.construct_ocrmypdf_parameters(
            document_path,
            mime_type,
            archive_path,
            sidecar_file,
        )

        try:
            self.log.debug(f"Calling OCRmyPDF with args: {args}")
            # ocrmypdf.ocr(**args)
            self.log.info("gia tri document_path: ", document_path)
            self.ocr_img_or_pdf(document_path, mime_type,**args)
            if self.settings.skip_archive_file != ArchiveFileChoices.ALWAYS:
                self.archive_path = archive_path

            self.text = self.extract_text(sidecar_file, archive_path)

            if not self.text:
                raise NoTextFoundException("No text was found in the original document")
        except EncryptedPdfError:
            self.log.warning(
                "This file is encrypted, OCR is impossible. Using "
                "any text present in the original file.",
            )
            if original_has_text:
                self.text = text_original
        except SubprocessOutputError as e:
            if "Ghostscript PDF/A rendering" in str(e):
                self.log.warning(
                    "Ghostscript PDF/A rendering failed, consider setting "
                    "PAPERLESS_OCR_USER_ARGS: '{\"continue_on_soft_render_error\": true}'",
                )

            raise ParseError(
                f"SubprocessOutputError: {e!s}. See logs for more information.",
            ) from e
        except (NoTextFoundException, InputFileError) as e:
            self.log.warning(
                f"Encountered an error while running OCR: {e!s}. "
                f"Attempting force OCR to get the text.",
            )

            archive_path_fallback = Path(
                os.path.join(self.tempdir, "archive-fallback.pdf"),
            )
            sidecar_file_fallback = Path(
                os.path.join(self.tempdir, "sidecar-fallback.txt"),
            )

            # Attempt to run OCR with safe settings.

            args = self.construct_ocrmypdf_parameters(
                document_path,
                mime_type,
                archive_path_fallback,
                sidecar_file_fallback,
                safe_fallback=True,
            )

            try:
                self.log.debug(f"Fallback: Calling OCRmyPDF with args: {args}")
                # ocrmypdf.ocr(**args)
                self.ocr_img_or_pdf(document_path, mime_type,**args)
                # Don't return the archived file here, since this file
                # is bigger and blurry due to --force-ocr.

                self.text = self.extract_text(
                    sidecar_file_fallback,
                    archive_path_fallback,
                )

            except Exception as e:
                # If this fails, we have a serious issue at hand.
                raise ParseError(f"{e.__class__.__name__}: {e!s}") from e

        except Exception as e:
            # Anything else is probably serious.
            raise ParseError(f"{e.__class__.__name__}: {e!s}") from e

        # As a last resort, if we still don't have any text for any reason,
        # try to extract the text from the original document.
        if not self.text:
            if original_has_text:
                self.text = text_original
            else:
                self.log.warning(
                    f"No text was found in {document_path}, the content will "
                    f"be empty.",
                )
                self.text = ""


def post_process_text(text):
    if not text:
        return None

    collapsed_spaces = re.sub(r"([^\S\r\n]+)", " ", text)
    no_leading_whitespace = re.sub(r"([\n\r]+)([^\S\n\r]+)", "\\1", collapsed_spaces)
    no_trailing_whitespace = re.sub(r"([^\S\n\r]+)$", "", no_leading_whitespace)

    # TODO: this needs a rework
    # replace \0 prevents issues with saving to postgres.
    # text may contain \0 when this character is present in PDF files.
    return no_trailing_whitespace.strip().replace("\0", " ")
