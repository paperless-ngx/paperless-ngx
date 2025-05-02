import json
import logging
import socket
import time
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature

from documents.models import Document
from edoc.models import ApplicationConfiguration

logger = logging.getLogger("edoc.common")


def generate_token(data, secret_key):
    # Sử dụng secret key tùy chỉnh
    signer = TimestampSigner(key=secret_key)

    # Tạo token chứa ID của user
    token = signer.sign(data)
    return token


def verify_token(token, secret_key,
                 max_age_seconds=15 * 24 * 60 * 60):  # 15 ngày
    signer = TimestampSigner(key=secret_key)

    try:
        # Giải mã token và kiểm tra thời gian hết hạn
        task_id = signer.unsign(token, max_age=max_age_seconds)
        return {"valid": True, "task_id": task_id}
    except SignatureExpired:
        # Token đã hết hạn
        return {"valid": False, "error": "Token đã hết hạn."}
    except BadSignature:
        # Token không hợp lệ
        return {"valid": False, "error": "Token không hợp lệ."}


def call_ocr_api_with_retries(method, url, headers, params, payload,
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
            logger.info("Got response", url, response_ocr.status_code)
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
                logger.error("Got response", response_ocr.status_code)
                return False
            else:
                logger.error('OCR error response: %s',
                             response_ocr.json())
                retries += 1
                time.sleep(delay)
        except requests.exceptions.Timeout:
            retries += 1
            logger.warning(
                f'OCR request timed out. Retrying... time{retries}')
            time.sleep(delay)
        except requests.exceptions.RequestException as e:
            logger.exception('OCR request failed: %s', e)
            break

        except Exception as e:
            logger.exception(e)
            break

    logger.error('Max retries reached. OCR request failed.')
    return None


def login_ocr(username_ocr, password_ocr, api_login_ocr):
    # check token
    payload = f"username={username_ocr}&password={password_ocr}"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    return call_ocr_api_with_retries("POST", api_login_ocr,
                                     headers=headers,
                                     params={},
                                     payload=payload,
                                     max_retries=2,
                                     delay=5,
                                     timeout=20)


def get_access_and_refresh_token(refresh_token_ocr, api_refresh_ocr,
                                 username_ocr, password_ocr,
                                 api_login_ocr):
    # check token
    headers = {
        'Content-Type': 'application/json'
    }
    payload = json.dumps({
        "refresh": f"{refresh_token_ocr}"
    })
    token = call_ocr_api_with_retries("POST", api_refresh_ocr,
                                      headers,
                                      params={},
                                      payload=payload,
                                      max_retries=2,
                                      delay=5,
                                      timeout=20,
                                      status_code_fail=[401, 400])
    if not token:
        token = login_ocr(username_ocr, password_ocr, api_login_ocr)
    return token


def upload_file(path_document, file_id, callback_url, api_upload_file_ocr,
                username_ocr,
                password_ocr, api_login_ocr, api_refresh_ocr,
                refresh_token_ocr):
    try:

        # upload file -------------------
        get_file_id = ''

        access_token_ocr = cache.get('access_token_ocr', '')
        logger.info(
            f"access_token_ocr {len(access_token_ocr)} , file_id: {file_id}")
        headers = {
            'Authorization': f"Bearer {access_token_ocr}"
        }
        with open(path_document, 'rb') as file:
            pdf_data = file.read()
        payload = {'title': (str(path_document).split("/")[-1]),
                   'folder': settings.FOLDER_UPLOAD,
                   'get_value': '1',
                   'callback_url': callback_url,
                   }
        if file_id:
            payload['file_id'] = file_id
        response_upload = requests.post(api_upload_file_ocr, data=payload,
                                        files={
                                            'file': (
                                                str(path_document).split("/")[
                                                    -1],
                                                pdf_data)} if not file_id else None,
                                        headers=headers)
        logger.info(f"Response status code: {response_upload.status_code}")
        logger.info(f"Response content: {response_upload}")
        if access_token_ocr == '' or response_upload.status_code == 401:
            logger.info("access_token not exist")
            token = get_access_and_refresh_token(
                username_ocr=username_ocr,
                password_ocr=password_ocr,
                api_login_ocr=api_login_ocr,
                refresh_token_ocr=refresh_token_ocr,
                api_refresh_ocr=api_refresh_ocr)
            token = token.get('data', None)
            if token is not None and token.get('access',
                                               '') != '' and token.get(
                'refresh', '') != '':
                cache.set("access_token_ocr", token['access'], 86400)
                cache.set("refresh_token_ocr", token['refresh'], 86400)

            elif token is not None and token.get('access',
                                                 '') != '' and token.get(
                'refresh', '') == '':
                cache.set("access_token_ocr", token['access'], 86400)

            else:
                logger.error("Cannot get access token and refresh token")
                return None

            headers = {
                'Authorization': f"Bearer {token['access']}"
            }

            with open(path_document, 'rb') as file:
                pdf_data = file.read()

            response_upload = requests.post(api_upload_file_ocr, data=payload,
                                            files={
                                                'file': (
                                                    str(path_document).split(
                                                        "/")[
                                                        -1],
                                                    pdf_data)} if not file_id else None,
                                            headers=headers)
        logger.info(
            f"response_upload:{api_upload_file_ocr}{response_upload.status_code}", )

        if response_upload.status_code == 201:
            # get_file_id = response_upload.json().get('id', '')
            logger.info("Upload file success")

            return response_upload.json()
        return None

    except Exception as e:
        logger.exception("Exception", e)
        return None


def peel_field(document: Document, callback_url):
    app_config = ApplicationConfiguration.objects.filter().first()
    username_ocr = app_config.username_ocr
    password_ocr = app_config.password_ocr
    api_login_ocr = settings.API_LOGIN_OCR
    api_refresh_ocr = settings.API_REFRESH_OCR
    refresh_token_ocr = cache.get('refresh_token_ocr', '')
    api_upload_file_ocr = settings.API_UPLOAD_FILE_OCR
    logger.info(f"into peel-field with callback_url {callback_url}")

    response = upload_file(path_document=document.archive_path,
                           file_id=document.file_id,
                           callback_url=callback_url,
                           api_upload_file_ocr=api_upload_file_ocr,
                           username_ocr=username_ocr,
                           password_ocr=password_ocr,
                           api_login_ocr=api_login_ocr,
                           api_refresh_ocr=api_refresh_ocr,
                           refresh_token_ocr=refresh_token_ocr)
    logger.info(f"response upload peel field: {response}")
    update = False
    if response:
        update = True

    if not document.file_id and update:
        document.file_id = response.get('id', None)
        document.save()
        logger.info(
            f'update document.file_id: {document.id} with file_id: {response.get("id", None)}')
    return response


def ocr_file_webhook(path_file, username_ocr, password_ocr, api_login_ocr,
                     api_refresh_ocr, api_upload_file_ocr, api_call_count,
                     task_id, **args):
    file_id = None
    data_ocr = None
    data_ocr_fields = None
    refresh_token_ocr = cache.get("refresh_token_ocr", '')
    try:

        app_config: ApplicationConfiguration | None
        access_token_ocr = cache.get('access_token_ocr', '')
        # login API custom-field

        # upload file -------------------
        headers = {
            'Authorization': f"Bearer {access_token_ocr}"
        }
        token_auth = generate_token(task_id, settings.EDOC_SECRET_KEY_OCR)

        callback_url = ""
        try:
            callback_url = settings.CSRF_TRUSTED_ORIGINS[0]
        except (AttributeError, IndexError):
            # fallback nếu CSRF_TRUSTED_ORIGINS không tồn tại hoặc rỗng
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            callback_url = f"http://{ip_address}"
        callback_url = f"{callback_url}/api/process_ocr/{quote(token_auth)}/update-content-document/"

        with open(path_file, 'rb') as file:
            pdf_data = file.read()
        payload = {'title': (str(path_file).split("/")[-1]),
                   'folder': settings.FOLDER_UPLOAD,
                   'extract': '1',
                   'callback_url': callback_url
                   }
        response_upload = requests.post(api_upload_file_ocr, data=payload,
                                        files={
                                            'file': (
                                                str(path_file).split("/")[
                                                    -1],
                                                pdf_data)},
                                        headers=headers)

        # login get access token and refresh token
        if access_token_ocr == '' or response_upload.status_code == 401:
            token = get_access_and_refresh_token(
                username_ocr=username_ocr,
                password_ocr=password_ocr,
                api_login_ocr=api_login_ocr,
                refresh_token_ocr=refresh_token_ocr,
                api_refresh_ocr=api_refresh_ocr)
            token = token.get('data', None)
            if token is not None and token.get('access',
                                               '') != '' and token.get(
                'refresh', '') != '':
                cache.set("access_token_ocr", token['access'], 86400)
                cache.set("refresh_token_ocr", token['refresh'], 86400)

            elif token is not None and token.get('access',
                                                 '') != '' and token.get(
                'refresh', '') == '':
                cache.set("access_token_ocr", token['access'], 86400)

            else:
                raise Exception(
                    "Cannot get access token and refresh token")

            headers = {
                'Authorization': f"Bearer {cache.get('access_token_ocr', '')}"
            }
            pdf_data = None

            with open(path_file, 'rb') as file:
                pdf_data = file.read()

            payload = {'title': (str(path_file).split("/")[-1]),
                       'folder': settings.FOLDER_UPLOAD,
                       'extract': '1',
                       'callback_url': callback_url
                       }
            response_upload = requests.post(api_upload_file_ocr,
                                            data=payload,
                                            files={'file': (
                                                str(path_file).split("/")[-1],
                                                pdf_data)},
                                            headers=headers)
            api_call_count += 1
            if response_upload.status_code != 201:
                raise Exception(
                    f"Cannot upload file to OCR API, status code: {response_upload.status_code}")

        if response_upload.status_code == 201:
            get_file_id = response_upload.json().get('id', '')
            file_id = get_file_id
            api_call_count += 1

    # except Exception as e:
    #     self.log.error("error", e)
    finally:
        return (data_ocr, data_ocr_fields, file_id, api_call_count)


def get_setting_ocr(field):
    """
    Trả về giá trị của 1 trường từ ApplicationConfiguration nếu tồn tại.
    Ưu tiên lấy từ cache. Nếu không có thì lấy từ DB và cache lại.
    """
    cache_key = f"{field}"

    value = cache.get(cache_key)
    if value is not None:
        return value

    valid_fields = {f.name for f in
                    ApplicationConfiguration._meta.get_fields()}
    if field not in valid_fields:
        return None

    try:
        config = ApplicationConfiguration.objects.first()
        if config is not None:
            value = getattr(config, field, None)
            cache.set(cache_key, value, timeout=60 * 60 * 60)  # Cache 1 tiếng
            return value
    except Exception:
        return None
