import re

from .parsers import RasterisedDocumentParser


class ConsumerDeclaration(object):

    MATCHING_FILES = re.compile("^.*\.(pdf|jpe?g|gif|png|tiff?|pnm|bmp)$")

    @classmethod
    def handle(cls, sender, **kwargs):
        return cls.test

    @classmethod
    def test(cls, doc):

        if cls.MATCHING_FILES.match(doc.lower()):
            return {
                "parser": RasterisedDocumentParser,
                "weight": 0
            }

        return None
