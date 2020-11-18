import re

from .parsers import TextDocumentParser


def text_consumer_declaration(sender, **kwargs):
    return {
        "parser": TextDocumentParser,
        "weight": 10,
        "test": text_consumer_test
    }


MATCHING_FILES = re.compile(r"^.*\.(te?xt|md|csv)$")


def text_consumer_test(doc):
    return MATCHING_FILES.match(doc.lower())
