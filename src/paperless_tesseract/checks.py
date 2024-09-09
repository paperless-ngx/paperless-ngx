import shutil
import subprocess

from django.conf import settings
from django.core.checks import Error
from django.core.checks import Warning
from django.core.checks import register


def get_tesseract_langs():
    proc = subprocess.run(
        [shutil.which("tesseract"), "--list-langs"],
        capture_output=True,
    )

    # Decode bytes to string, split on newlines, trim out the header
    proc_lines = proc.stdout.decode("utf8", errors="ignore").strip().split("\n")[1:]

    return [x.strip() for x in proc_lines]


@register()
def check_default_language_available(app_configs, **kwargs):
    errs = []

    if not settings.OCR_LANGUAGE:
        errs.append(
            Warning(
                "No OCR language has been specified with PAPERLESS_OCR_LANGUAGE. "
                "This means that tesseract will fallback to english.",
            ),
        )
        return errs

    # binaries_check in paperless will check and report if this doesn't exist
    # So skip trying to do anything here and let that handle missing binaries
    if shutil.which("tesseract") is not None:
        installed_langs = get_tesseract_langs()

        specified_langs = [x.strip() for x in settings.OCR_LANGUAGE.split("+")]

        for lang in specified_langs:
            if lang not in installed_langs:
                errs.append(
                    Error(
                        f"The selected ocr language {lang} is "
                        f"not installed. Paperless cannot OCR your documents "
                        f"without it. Please fix PAPERLESS_OCR_LANGUAGE.",
                    ),
                )

    return errs
