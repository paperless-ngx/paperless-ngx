def get_parser(*args, **kwargs):
    from edoc_ocr_custom.parsers import RasterisedDocumentCustomParser

    return RasterisedDocumentCustomParser(*args, **kwargs)


def tesseract_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 1,
        "mime_types": {
            "application/pdf": ".pdf",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/tiff": ".tif",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
            "image/webp": ".webp",
        },
    }
