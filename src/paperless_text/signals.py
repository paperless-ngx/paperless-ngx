import re

from .parsers import TextDocumentParser


class ConsumerDeclaration:

    MATCHING_FILES = re.compile(r"^.*\.(te?xt|md|csv)$")

    @classmethod
    def handle(cls, sender, **kwargs):
        return cls.test

    @classmethod
    def test(cls, doc):

        if cls.MATCHING_FILES.match(doc.lower()):
            return {
                "parser": TextDocumentParser,
                "weight": 10
            }

        return None
