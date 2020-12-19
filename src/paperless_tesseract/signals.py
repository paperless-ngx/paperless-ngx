from .parsers import RasterisedDocumentParser


def tesseract_consumer_declaration(sender, **kwargs):
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
        }
    }
