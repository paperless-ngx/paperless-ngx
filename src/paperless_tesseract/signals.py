import re

from .parsers import RasterisedDocumentParser


class ConsumerDeclaration(object):

    MATCHING_FILES = re.compile("^.*\.(pdf|jpg|gif|png|tiff|pnm|bmp)$")

    @classmethod
    def handle(cls, sender, **kwargs):
        return cls.test

    @classmethod
    def test(cls, doc):

        if cls.MATCHING_FILES.match(doc):
            return {
                "parser": RasterisedDocumentParser,
                "weight": 0
            }

        return None
