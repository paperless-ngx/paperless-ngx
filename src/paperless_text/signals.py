def get_parser(*args, **kwargs):
    from paperless.parsers.text import TextDocumentParser

    # The new TextDocumentParser does not accept the legacy logging_group /
    # progress_callback kwargs injected by the old signal-based consumer.
    # These are dropped here; Phase 4 will replace this signal path with the
    # new ParserRegistry so the shim can be removed at that point.
    kwargs.pop("logging_group", None)
    kwargs.pop("progress_callback", None)
    return TextDocumentParser()


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
