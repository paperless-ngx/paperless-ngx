import io
import json
import math
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

import requests
from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError

from django.conf import settings
from django.core.cache import cache, caches
from pdf2image import convert_from_path
from pypdf import PdfReader, PdfWriter, PageObject
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

import math

from documents.models import DossierForm
from documents.parsers import DocumentParser
from documents.parsers import ParseError
from documents.parsers import make_thumbnail_from_pdf
from documents.render_pdf import draw_text_on_pdf, draw_invisible_text, \
    render_pdf_ocr
from documents.utils import maybe_override_pixel_limit
from documents.utils import run_subprocess
from edoc.config import OcrConfig
from edoc.models import ApplicationConfiguration, ArchiveFileChoices
from edoc.models import CleanChoices
from edoc.models import ModeChoices


class NoTextFoundException(Exception):
    pass


class RtlLanguageException(Exception):
    pass


class RasterisedDocumentCustomParser(DocumentParser):
    """
    This parser uses Tesseract to try and get some text out of a rasterised
    image, whether it's a PDF, or other graphical format (JPEG, TIFF, etc.)
    """

    logging_name = "edoc.parsing.pdf"
    file_id = None
    def get_settings(self) -> OcrConfig:
        """
        This parser uses the OCR configuration settings to parse documents
        """
        return OcrConfig()

    def get_page_count(self, document_path, mime_type):
        page_count = None
        if mime_type == "application/pdf":
            try:
                import pikepdf

                with pikepdf.Pdf.open(document_path) as pdf:
                    page_count = len(pdf.pages)
            except Exception as e:
                self.log.warning(
                    f"Unable to determine PDF page count {document_path}: {e}",
                )
        return page_count

    def get_file_id(self):
        return str(self.file_id) if self.file_id else None

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
            self.log.warning(
                f"Error while getting DPI from image {image}: {e}")
            return None

    def get_api_call_count(self):
        return self.api_call_count

    def calculate_a4_dpi(self, image) -> Optional[int]:
        try:
            with Image.open(image) as im:
                width, height = im.size
                # divide image width by A4 width (210mm) in inches.
                dpi = int(width / (21 / 2.54))
                self.log.debug(
                    f"Estimated DPI {dpi} based on image width {width}")
                return dpi

        except Exception as e:
            self.log.warning(
                f"Error while calculating DPI for image {image}: {e}")
            return None

    # call api
    def call_ocr_api_with_retries(self, method, url, headers, params, payload,
                                  max_retries=5, delay=5, timeout=100,
                                  status_code_success=[200],
                                  status_code_fail=[], data_compare={}):

        retries = 0
        data_ocr = None
        while retries < max_retries:
            try:
                response_ocr = requests.request(method, url, headers=headers,
                                                params=params, data=payload,
                                                timeout=timeout, )
                self.log.info("Got response", url , response_ocr.status_code)
                if response_ocr.status_code in status_code_success:
                    flag = False
                    for key, value in data_compare.items():
                        if response_ocr.json().get(key, None) == value:
                            flag = True
                            break
                    if flag:
                        retries += 1
                        time.sleep(delay)
                    else:
                        return response_ocr.json()
                if response_ocr.status_code in status_code_fail:
                    self.log.error("Got response", response_ocr.status_code)
                    return False
                else:
                    self.log.error('OCR error response: %s, status code: %s',
                                   response_ocr.content, response_ocr.status_code)
                    retries += 1
                    time.sleep(delay)
            except requests.exceptions.Timeout:
                retries += 1
                self.log.warning(
                    f'OCR request timed out. Retrying... time{retries}')
                time.sleep(delay)
            except requests.exceptions.RequestException as e:
                self.log.exception('OCR request failed: %s', e)
                break

            except Exception as e:
                self.log.exception(e)
                break

        self.log.error('Max retries reached. OCR request failed.')
        return None

    def get_access_and_refresh_token(self, refresh_token_ocr, api_refresh_ocr,
                                     username_ocr, password_ocr,
                                     api_login_ocr):
        # check token
        headers = {
            'Content-Type': 'application/json'
        }
        payload = json.dumps({
            "refresh": f"{refresh_token_ocr}"
        })
        token = self.call_ocr_api_with_retries("POST", api_refresh_ocr,
                                               headers,
                                               params={},
                                               payload=payload,
                                               max_retries=2,
                                               delay=5,
                                               timeout=20,
                                               status_code_fail=[401,400])
        if token == False:
            token = self.login_ocr(username_ocr, password_ocr, api_login_ocr)
        return token

    def login_ocr(self, username_ocr, password_ocr, api_login_ocr):
        # check token
        payload = f"username={username_ocr}&password={password_ocr}"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        return self.call_ocr_api_with_retries("POST", api_login_ocr,
                                              headers=headers,
                                              params={},
                                              payload=payload,
                                              max_retries=2,
                                              delay=5,
                                              timeout=20)

    def ocr_file(self, path_file, username_ocr, password_ocr, api_login_ocr, api_refresh_ocr, api_upload_file_ocr, dossier_form: DossierForm, **args):
        # data general
        data_ocr = None
        data_ocr_fields = None
        form_code = ""
        app_config = ApplicationConfiguration.objects.filter().first()
        refresh_token_ocr = cache.get("refresh_token_ocr", '')

        # count page number
        page_count = 1
        try:
            with open(path_file, 'rb') as f:
                pdf_reader = PdfReader(f)
                page_count = len(pdf_reader.pages)
        except (OSError, IOError, ValueError, PdfReadError, PdfStreamError):
            pass
        # check token
        try:

            app_config: ApplicationConfiguration | None
            # access_token_ocr = args.get("access_token_ocr", 'None')
            access_token_ocr = cache.get('access_token_ocr','')
            # login API custom-field
            if len(args) == 0 and args.get('form_code') == '':
                return data_ocr, data_ocr_fields, form_code

            # upload file -------------------
            headers = {
                'Authorization': f"Bearer {access_token_ocr}"
            }

            with open(path_file, 'rb') as file:
                pdf_data = file.read()
            payload = {'title': (str(path_file).split("/")[-1]),
                       'folder': settings.FOLDER_UPLOAD,
                       'extract': '1'}
            response_upload = requests.post(api_upload_file_ocr, data=payload,
                                            files={
                                                'file': (
                                                    str(path_file).split("/")[
                                                        -1],
                                                    pdf_data)},
                                            headers=headers)

            # login get access token and refresh token
            if access_token_ocr == '' or response_upload.status_code == 401:
                token = self.get_access_and_refresh_token(
                    username_ocr=username_ocr,
                    password_ocr=password_ocr,
                    api_login_ocr=api_login_ocr,
                    refresh_token_ocr=refresh_token_ocr,
                    api_refresh_ocr=api_refresh_ocr)
                token = token.get('data', None)
                if token is not None and token.get('access', '') != '' and token.get('refresh', '') != '':
                    cache.set("access_token_ocr",token['access'],86400)
                    cache.set("refresh_token_ocr",token['refresh'],86400)

                elif token is not None and token.get('access','') != '' and token.get('refresh', '') == '':
                    cache.set("access_token_ocr",token['access'],86400)

                else:
                    raise Exception(
                        "Cannot get access token and refresh token")
                # app_config.save()

                headers = {
                    'Authorization': f"Bearer {cache.get('access_token_ocr','')}"
                }
                pdf_data = None
                with open(path_file, 'rb') as file:
                    pdf_data = file.read()

                payload = {'title': (str(path_file).split("/")[-1]),
                           'folder': settings.FOLDER_UPLOAD,
                           'extract': '1'}
                response_upload = requests.post(api_upload_file_ocr,
                                                data=payload,
                                                files={'file': (str(path_file).split("/")[-1], pdf_data)},
                                                headers=headers)

            if response_upload.status_code == 201:
                get_file_id = response_upload.json().get('id', '')
                self.file_id = get_file_id

                # else :
                #     # logging.error('upload file: ', response_upload.status_code)
                #     return data_ocr, data_ocr_fields, form_code

                # ocr by file_id --------------------------
                params = {'file_id': get_file_id}
                url_ocr_pdf_by_fileid = settings.API_OCR_BY_FILE_ID
                data_ocr_general = self.call_ocr_api_with_retries("GET",
                                                                  url_ocr_pdf_by_fileid,
                                                                  headers,
                                                                  params,
                                                                  {},
                                                                  max_retries=5,
                                                                  delay=page_count * 2,
                                                                  timeout=30,
                                                                  data_compare={'status_code': 1})

                if data_ocr_general is not None:
                    data_ocr = data_ocr_general.get('response', None)
                    enable_ocr_field = cache.get("enable_ocr_field", False)
                    url_ocr_pdf_custom_field_by_fileid = cache.get(
                        "api_ocr_field", False)
                    self.api_call_count+=1
                    if not enable_ocr_field and not url_ocr_pdf_custom_field_by_fileid:
                        return (data_ocr, data_ocr_fields, form_code)
                    # peeling field
                    get_request_id = data_ocr_general.get('request_id', None)
                    if dossier_form is None and app_config.user_args.get(
                        "form_code", False):
                        for i in app_config.user_args.get("form_code", []):
                            payload = json.dumps({
                                "request_id": f"{get_request_id}",
                                "list_form_code": [
                                    f"{i.get('name')}"
                                ]
                            })
                            headers = {
                                'Authorization': f"Bearer {args['access_token_ocr']}",
                                'Content-Type': 'application/json'
                            }
                            data_ocr_fields = self.call_ocr_api_with_retries(
                                "POST", url_ocr_pdf_custom_field_by_fileid,
                                headers, params, payload, 5, 5, 100,
                                status_code_fail=[401])

                            if not isinstance(data_ocr_fields, list):
                                continue
                            if data_ocr_fields[0].get("id") != -1:
                                form_code = i.get('name')
                                break
                    elif dossier_form is not None and dossier_form.form_rule:
                        self.log.debug("da vao dossier form")
                        payload = json.dumps({
                            "request_id": f"{get_request_id}",
                            "list_form_code": [
                                f"{dossier_form.form_rule}"
                            ]
                        })
                        headers = {
                            'Authorization': f"Bearer {args['access_token_ocr']}",
                            'Content-Type': 'application/json'
                        }
                        data_ocr_fields = self.call_ocr_api_with_retries(
                            "POST", url_ocr_pdf_custom_field_by_fileid,
                            headers, params, payload, 5, 5, 100,
                            status_code_fail=[401])

        # except Exception as e:
        #     self.log.error("error", e)
        finally:
            return (data_ocr, data_ocr_fields, form_code)

    # # get ocr file img/pdf
    # def ocr_file(self, path_file, dossier_form:DossierForm):

    #     application_configuration=ApplicationConfiguration.objects.filter().first()
    #     application_configuration: ApplicationConfiguration|None
    #     access_token_ocr=application_configuration.api_ocr.get("access_token",None)

    #     if access_token_ocr == '':
    #         access_token_ocr = self.login_ocr(application_configuration=application_configuration)
    #         if access_token_ocr is not None:
    #             application_configuration.api_ocr["access_token"]=access_token['access_token']

    #     # upload file
    #     get_file_id = ''
    #     url_upload_file = application_configuration.api_ocr.get("upload_file",None)
    #     headers = {
    #         'Authorization': f"Bearer {application_configuration.api_ocr['access_token']}"
    #     }
    #     pdf_data = None
    #     with open(path_file, 'rb') as file:
    #         pdf_data = file.read()

    #     response_upload = requests.post(url_upload_file, files={'file': (str(path_file).split("/")[-1], pdf_data)}, headers=headers)
    #     if response_upload.status_code == 200:
    #         get_file_id = response_upload.json().get('file_id','')
    #     else:
    #         logging.error('upload file: ',response_upload.status_code)

    #     # ocr by file_id
    #     params = {'file_id': get_file_id}
    #     url_ocr_pdf_by_fileid = application_configuration.api_ocr.get("ocr_by_file_id",None)
    #     data_ocr = self.call_ocr_api_with_retries("POST",url_ocr_pdf_by_fileid, headers, params, {}, 5, 5, 100)

    #     # login API custom-field
    #     if dossier_form is None:
    #         return (data_ocr,None)

    #     if len(application_configuration.api_ocr_field)>0 and dossier_form.form_rule != '':
    #         # login for the first time ...
    #         access_token = application_configuration.api_ocr_field.get("access_token",None)
    #         if access_token == '':
    #             token = self.login_ocr_field(application_configuration=application_configuration)
    #             if token is not None:
    #                 application_configuration.api_ocr_field["access_token"]=token['access']
    #                 application_configuration.api_ocr_field["refresh_token"]=token['refresh']
    #                 application_configuration.save()
    #         url_ocr_pdf_custom_field_by_fileid = application_configuration.api_ocr_field.get("ocr")
    #         payload = json.dumps({
    #         "request_id": f"{get_file_id}",
    #         "list_form_code": [
    #             f"{dossier_form.form_rule}"
    #         ]
    #         })
    #         headers = {
    #             'Authorization': f"Bearer {application_configuration.api_ocr_field['access_token']}",
    #             'Content-Type': 'application/json'
    #         }
    #         data_ocr_fields = self.call_ocr_api_with_retries("POST",url_ocr_pdf_custom_field_by_fileid, headers, params, payload, 5, 5, 100,status_code_fail=[401])
    #         # self.log.info("gia tri application_configuration", data_ocr_fields)

    #         # if token expire or WRONG
    #         if data_ocr_fields == False:
    #             token = self.get_token_ocr_field_by_refresh_token(application_configuration)
    #             if token is not None and token != False:
    #                 application_configuration.api_ocr_field["access_token"]=token['access']
    #                 application_configuration.api_ocr_field["refresh_token"]=token['refresh']
    #                 application_configuration.save()

    #                 # repeat ocr_field
    #                 payload = json.dumps({
    #                 "request_id": f"{get_file_id}",
    #                 "list_form_code": [
    #                     f"{dossier_form.form_rule}"
    #                 ]
    #                 })
    #                 headers = {
    #                     'Authorization': f"Bearer {application_configuration.api_ocr_field.get('access_token')}",
    #                     'Content-Type': 'application/json'
    #                 }
    #                 self.log.log("ocr field-------------", headers)
    #                 data_ocr_fields = self.call_ocr_api_with_retries("POST",url_ocr_pdf_custom_field_by_fileid, headers, params, payload, 5, 5, 100,status_code_fail=[401])

    #     return (data_ocr,data_ocr_fields)



    def ocr_img_or_pdf(self, document_path, mime_type, dossier_form, sidecar,
                       output_file, **kwargs):

        data_ocr = None
        data_ocr_fields = None
        form_code = None
        try:
            username_ocr = self.get_setting_ocr('username_ocr')
            password_ocr = self.get_setting_ocr('password_ocr')
            api_login_ocr = settings.API_LOGIN_OCR
            api_refresh_ocr = settings.API_REFRESH_OCR
            api_upload_file_ocr = settings.API_UPLOAD_FILE_OCR
            data_ocr, data_ocr_fields, form_code = self.ocr_file(
                path_file=document_path, username_ocr=username_ocr,
                password_ocr=password_ocr, api_login_ocr=api_login_ocr,
                api_refresh_ocr=api_refresh_ocr,
                api_upload_file_ocr=api_upload_file_ocr,
                dossier_form=dossier_form,
                **kwargs)


            render_pdf_ocr(input_path=document_path, output_path=output_file,
                           data_ocr=data_ocr,
                           quality_compress=self.quality_compress,
                           font_path=os.path.join(
                               os.path.dirname(os.path.abspath(__file__)),
                               'fonts', 'arial-font/arial.ttf'))
            content_formated = ""
            if data_ocr is not None:
                content_formated = data_ocr.get("content_formated", "")
            if len(content_formated)>0:
                    with open(sidecar, "w") as txt_sidecar:
                        txt_sidecar.write(data_ocr.get("content_formated", ""))
            # draw_text_on_pdf(
            #     input_path=document_path,
            #     output_path=output_file,
            #     data=data_ocr,
            #     font_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
            #                          'fonts', 'arial-font/arial.ttf'))
            # draw_invisible_text(
            #     input_path=document_path,
            #     output_path=output_file,
            #     data=data_ocr,
            #     quality=int(self.quality_compress),
            #     font_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
            #                            'fonts', 'arial-font/arial.ttf')
            # )

            return data_ocr, data_ocr_fields, form_code

        except Exception as e:
                raise ParseError(f"{e.__class__.__name__}: {e!s}") from e


    def extract_text(
        self,
        sidecar_file: Optional[Path],
        pdf_file: Path,
    ) -> Optional[str]:
        # When re-doing OCR, the sidecar contains ONLY the new text, not
        # the whole text, so do not utilize it in that case
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
            ocrmypdf_args[
                "rotate_pages_threshold"] = self.settings.rotate_threshold

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
                    f"There is an issue with EDOC_OCR_USER_ARGS, so "
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

    def parse(self, document_path: Path, mime_type, file_name=None,
              dossier_form=None):
        # This forces tesseract to use one core per page.
        os.environ["OMP_THREAD_LIMIT"] = "1"
        VALID_TEXT_LENGTH = 50

        if mime_type == "application/pdf":
            text_original = self.extract_text(None, document_path)
            original_has_text = (
                text_original is not None and len(
                text_original) > VALID_TEXT_LENGTH
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
        data_ocr, data_ocr_fields, form_code = None, None, ''
        try:
            self.log.debug(f"Calling OCRmyPDF with args: {args} ")
            # ocrmypdf.ocr(**args)
            # data_ocr, data_ocr_fields, form_code = self.ocr_img_or_pdf(
            #     document_path, mime_type, dossier_form, **args)
            if self.settings.skip_archive_file != ArchiveFileChoices.ALWAYS:
                self.archive_path = archive_path

            self.text = self.extract_text(sidecar_file, archive_path)

            if not self.text:
                raise NoTextFoundException(
                    "No text was found in the original document")
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
                    "EDOC_OCR_USER_ARGS: '{\"continue_on_soft_render_error\": true}'",
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
                self.log.debug(f"Fallback: Calling OCRmyPDF with args: {args} {archive_path_fallback}")
                # ocrmypdf.ocr(**args)
                data_ocr, data_ocr_fields, form_code = self.ocr_img_or_pdf(
                    document_path, mime_type, dossier_form, **args)
                # Don't return the archived file here, since this file
                # is bigger and blurry due to --force-ocr.
                self.archive_path = archive_path_fallback
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
        return data_ocr_fields, form_code

    def parse_field(self, document_path: Path, mime_type, file_name=None):
        # This forces tesseract to use one core per page.
        os.environ["OMP_THREAD_LIMIT"] = "1"
        VALID_TEXT_LENGTH = 50
        from ocrmypdf import InputFileError

        archive_path = Path(os.path.join(self.tempdir, "archive.pdf"))
        sidecar_file = Path(os.path.join(self.tempdir, "sidecar.txt"))

        args = self.construct_ocrmypdf_parameters(
            document_path,
            mime_type,
            archive_path,
            sidecar_file,
        )
        data_ocr, data_ocr_fields, form_code = None, None, ''
        try:
            self.log.debug(f"Calling OCRmyPDF with args: {args}")
            # ocrmypdf.ocr(**args)
            data_ocr, data_ocr_fields, form_code = self.ocr_img_or_pdf(
                document_path, mime_type, **args)
            if self.settings.skip_archive_file != ArchiveFileChoices.ALWAYS:
                self.archive_path = archive_path

        except (InputFileError) as e:
            self.log.warning(
                f"Encountered an error while running OCR: {e!s}. "
                f"Attempting force OCR to get the text.",
            )

            archive_path_fallback = Path(
                os.path.join(self.tempdir, "archive-fallback.pdf"),
            )

            # Attempt to run OCR with safe settings.

            args = self.construct_ocrmypdf_parameters(
                document_path,
                mime_type,
                archive_path_fallback,
                safe_fallback=True,
            )

            try:
                self.log.debug(f"Fallback: Calling OCRmyPDF with args: {args}")
                # ocrmypdf.ocr(**args)
                data_ocr, data_ocr_fields, form_code = self.ocr_img_or_pdf(
                    document_path, mime_type, **args)

            except Exception as e:
                # If this fails, we have a serious issue at hand.
                raise ParseError(f"{e.__class__.__name__}: {e!s}") from e

        except Exception as e:
            # Anything else is probably serious.
            raise ParseError(f"{e.__class__.__name__}: {e!s}") from e

        return data_ocr_fields, form_code


def post_process_text(text):
    if not text:
        return None

    collapsed_spaces = re.sub(r"([^\S\r\n]+)", " ", text)
    no_leading_whitespace = re.sub(r"([\n\r]+)([^\S\n\r]+)", "\\1",
                                   collapsed_spaces)
    no_trailing_whitespace = re.sub(r"([^\S\n\r]+)$", "",
                                    no_leading_whitespace)

    # TODO: this needs a rework
    # replace \0 prevents issues with saving to postgres.
    # text may contain \0 when this character is present in PDF files.
    return no_trailing_whitespace.strip().replace("\0", " ")
