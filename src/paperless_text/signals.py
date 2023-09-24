def get_parser(*args, **kwargs):
    from paperless_text.parsers import TextDocumentParser

    return TextDocumentParser(*args, **kwargs)


def text_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 10,
        "mime_types": {
            "text/plain": ".txt",
            "text/csv": ".csv",
            "application/csv": ".csv",
        },
    }
