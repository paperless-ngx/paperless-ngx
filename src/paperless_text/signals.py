from .parsers import TextDocumentParser


def text_consumer_declaration(sender, **kwargs):
    return {
        "parser": TextDocumentParser,
        "weight": 10,
        "mime_types": {
            "text/plain": ".txt",
            "text/csv": ".csv",
        }
    }
