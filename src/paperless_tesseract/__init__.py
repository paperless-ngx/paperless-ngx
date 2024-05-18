# this is here so that django finds the checks.
from paperless_tesseract.checks import check_default_language_available
from paperless_tesseract.checks import get_tesseract_langs

__all__ = ["get_tesseract_langs", "check_default_language_available"]
