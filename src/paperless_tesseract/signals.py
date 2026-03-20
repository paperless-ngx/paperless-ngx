from __future__ import annotations

from typing import Any


def get_parser(*args: Any, **kwargs: Any) -> Any:
    from paperless.parsers.tesseract import RasterisedDocumentParser

    # RasterisedDocumentParser accepts logging_group for constructor compatibility but
    # does not store or use it (no legacy DocumentParser base class).
    # progress_callback is also not used.  Both may arrive as a positional arg
    # (consumer) or a keyword arg (views); *args absorbs the positional form,
    # kwargs.pop handles the keyword form.  Phase 4 will replace this signal
    # path with the new ParserRegistry so the shim can be removed at that point.
    kwargs.pop("logging_group", None)
    kwargs.pop("progress_callback", None)
    return RasterisedDocumentParser(*args, **kwargs)


def tesseract_consumer_declaration(sender: Any, **kwargs: Any) -> dict[str, Any]:
    return {
        "parser": get_parser,
        "weight": 0,
        "mime_types": {
            "application/pdf": ".pdf",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/tiff": ".tif",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
            "image/webp": ".webp",
            "image/heic": ".heic",
        },
    }
