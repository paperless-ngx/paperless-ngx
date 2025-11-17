"""
Advanced OCR module for IntelliDocs-ngx.

This module provides enhanced OCR capabilities including:
- Table detection and extraction
- Handwriting recognition
- Form field detection
- Layout analysis

Lazy imports are used to avoid loading heavy dependencies unless needed.
"""

__all__ = [
    "FormFieldDetector",
    "HandwritingRecognizer",
    "TableExtractor",
]


def __getattr__(name):
    """Lazy import to avoid loading heavy ML models on startup."""
    if name == "TableExtractor":
        from .table_extractor import TableExtractor

        return TableExtractor
    elif name == "HandwritingRecognizer":
        from .handwriting import HandwritingRecognizer

        return HandwritingRecognizer
    elif name == "FormFieldDetector":
        from .form_detector import FormFieldDetector

        return FormFieldDetector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
