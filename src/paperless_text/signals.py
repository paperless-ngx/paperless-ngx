def get_parser(*args, **kwargs):
    from paperless.parsers.text import TextDocumentParser

    # TextDocumentParser accepts logging_group for constructor compatibility but
    # does not store or use it (no legacy DocumentParser base class).
    # progress_callback is also not used.  Both may arrive as a positional arg
    # (consumer) or a keyword arg (views); *args absorbs the positional form,
    # kwargs.pop handles the keyword form.  Phase 4 will replace this signal
    # path with the new ParserRegistry so the shim can be removed at that point.
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
