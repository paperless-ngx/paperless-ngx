# this is here so that django finds the checks.
from paperless_tesseract.checks import check_default_language_available
from paperless_tesseract.checks import get_tesseract_langs

__all__ = ["check_default_language_available", "get_tesseract_langs"]
