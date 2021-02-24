import subprocess

from django.conf import settings
from django.core.checks import Error, Warning, register


def get_tesseract_langs():
    with subprocess.Popen(['tesseract', '--list-langs'],
                          stdout=subprocess.PIPE) as p:
        stdout, stderr = p.communicate()

    return stdout.decode().strip().split("\n")[1:]


@register()
def check_default_language_available(app_configs, **kwargs):
    installed_langs = get_tesseract_langs()

    if not settings.OCR_LANGUAGE:
        return [Warning(
            "No OCR language has been specified with PAPERLESS_OCR_LANGUAGE. "
            "This means that tesseract will fallback to english."
        )]

    specified_langs = settings.OCR_LANGUAGE.split("+")

    for lang in specified_langs:
        if lang not in installed_langs:
            return [Error(
                f"The selected ocr language {lang} is "
                f"not installed. Paperless cannot OCR your documents "
                f"without it. Please fix PAPERLESS_OCR_LANGUAGE.")]

    return []
