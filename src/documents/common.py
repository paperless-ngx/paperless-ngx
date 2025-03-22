import json
import logging
import time

import requests

from paperless.models import ApplicationConfiguration
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("edoc.common")


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


def login_ocr( username_ocr, password_ocr, api_login_ocr):
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


def upload_file(path_document, callback_url, api_upload_file_ocr, username_ocr,
                password_ocr, api_login_ocr, api_refresh_ocr,
                refresh_token_ocr):
    try:

        # upload file -------------------
        get_file_id = ''
        access_token_ocr = cache.get('access_token_ocr', '')
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
        response_upload = requests.post(api_upload_file_ocr, data=payload,
                                        files={
                                            'file': (
                                                str(path_document).split("/")[
                                                    -1],
                                                pdf_data)},
                                        headers=headers)

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
                logger.error("Cannot get access token and refresh token")
                return None

            headers = {
                'Authorization': f"Bearer {token['access']}"
            }

            with open(path_document, 'rb') as file:
                pdf_data = file.read()

            payload = {'title': (str(path_document).split("/")[-1]),
                       'folder': settings.FOLDER_UPLOAD,
                       'get_value': '1',
                       'callback_url': callback_url}
            response_upload = requests.post(api_upload_file_ocr,
                                            data=payload,
                                            files={'file': (
                                                str(path_document).split("/")[
                                                    -1],
                                                pdf_data)},
                                            headers=headers)
        logger.info(f"response_upload:{api_upload_file_ocr}{response_upload}", )


        if response_upload.status_code == 201:
            # get_file_id = response_upload.json().get('id', '')
            logger.info("Upload file success")

            return response_upload.json()
        return None
    except Exception as e:
        logger.exception("Exception", e)
        return None


def peel_field(path_document, callback_url):
    app_config = ApplicationConfiguration.objects.filter().first()
    username_ocr = app_config.username_ocr
    password_ocr = app_config.password_ocr
    api_login_ocr = settings.API_LOGIN_OCR
    api_refresh_ocr = settings.API_REFRESH_OCR
    refresh_token_ocr = cache.get("refresh_token_ocr", '')
    api_upload_file_ocr = settings.API_UPLOAD_FILE_OCR
    logger.info("peel-field--------------")
    response = upload_file(path_document=path_document,
                           callback_url=callback_url,
                           api_upload_file_ocr=api_upload_file_ocr,
                           username_ocr=username_ocr,
                           password_ocr=password_ocr,
                           api_login_ocr=api_login_ocr,
                           api_refresh_ocr=api_refresh_ocr,
                           refresh_token_ocr=refresh_token_ocr)
    return response
