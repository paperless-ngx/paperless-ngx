import subprocess

from django.conf import settings
from django.core.checks import Error, register


def get_tesseract_langs():
    with subprocess.Popen(['tesseract', '--list-langs'], stdout=subprocess.PIPE) as p:
        stdout, stderr = p.communicate()

    return stdout.decode().strip().split("\n")[1:]


@register()
def check_default_language_available(app_configs, **kwargs):
    langs = get_tesseract_langs()

    if not settings.OCR_LANGUAGE in langs:
        return [Error(
            f"The default ocr language {settings.OCR_LANGUAGE} is "
            f"not installed. Paperless cannot OCR your documents "
            f"without it. Please fix PAPERLESS_OCR_LANGUAGE.")]
    else:
        return []
