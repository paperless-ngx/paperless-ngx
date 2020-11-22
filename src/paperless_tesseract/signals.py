from .parsers import RasterisedDocumentParser


def tesseract_consumer_declaration(sender, **kwargs):
    return {
        "parser": RasterisedDocumentParser,
        "weight": 0,
        "mime_types": [
            "application/pdf",
            "image/jpeg",
            "image/png"
        ]
    }
