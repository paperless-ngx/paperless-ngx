def get_parser(*args, **kwargs):
    from paperless.parsers.tika import TikaDocumentParser

    # The new TikaDocumentParser does not accept the legacy logging_group /
    # progress_callback kwargs injected by the old signal-based consumer.
    # These are dropped here; Phase 4 will replace this signal path with the
    # new ParserRegistry so the shim can be removed at that point.
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
