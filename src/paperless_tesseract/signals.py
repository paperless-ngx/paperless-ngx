def get_parser(*args, **kwargs):
    from paperless_tesseract.parsers import RasterisedDocumentParser

    return RasterisedDocumentParser(*args, **kwargs)


def tesseract_consumer_declaration(sender, **kwargs):
    from paperless_tesseract.parsers import RasterisedDocumentParser

    return {
        "parser": RasterisedDocumentParser,
        "weight": 0,
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
