import re

from .parsers import RasterisedDocumentParser


def tesseract_consumer_declaration(sender, **kwargs):
    return {
        "parser": RasterisedDocumentParser,
        "weight": 0,
        "test": tesseract_consumer_test
    }


MATCHING_FILES = re.compile(r"^.*\.(pdf|jpe?g|gif|png|tiff?|pnm|bmp)$")


def tesseract_consumer_test(doc):
    return MATCHING_FILES.match(doc.lower())
