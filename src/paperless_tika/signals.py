def get_parser(*args, **kwargs):
    from paperless.parsers.tika import TikaDocumentParser

    # TikaDocumentParser accepts logging_group for constructor compatibility but
    # does not store or use it (no legacy DocumentParser base class).
    # progress_callback is also not used.  Both may arrive as a positional arg
    # (consumer) or a keyword arg (views); *args absorbs the positional form,
    # kwargs.pop handles the keyword form.  Phase 4 will replace this signal
    # path with the new ParserRegistry so the shim can be removed at that point.
    kwargs.pop("logging_group", None)
    kwargs.pop("progress_callback", None)
    return TikaDocumentParser()


def tika_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 10,
        "mime_types": {
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/vnd.ms-excel": ".xls",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
            "application/vnd.ms-powerpoint": ".ppt",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.slideshow": ".ppsx",
            "application/vnd.oasis.opendocument.presentation": ".odp",
            "application/vnd.oasis.opendocument.spreadsheet": ".ods",
            "application/vnd.oasis.opendocument.text": ".odt",
            "application/vnd.oasis.opendocument.graphics": ".odg",
            "text/rtf": ".rtf",
        },
    }
