"""
Settings for the Mistral OCR module.
"""

import os
from django.conf import settings

# Default Mistral OCR settings
MISTRAL_API_KEY = os.getenv("PAPERLESS_MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("PAPERLESS_MISTRAL_MODEL", "mistral-ocr-latest")

# Validation
if not MISTRAL_API_KEY:
    import logging

    logging.getLogger("paperless.parsing.mistral_ocr").warning(
        "Mistral OCR API key not set. OCR with Mistral will not work. "
        "Set PAPERLESS_MISTRAL_API_KEY environment variable."
    )
