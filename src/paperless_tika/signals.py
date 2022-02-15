def get_parser(*args, **kwargs):
    from .parsers import TikaDocumentParser

    return TikaDocumentParser(*args, **kwargs)


def tika_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 10,
        "mime_types": {
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",  # NOQA: E501
            "application/vnd.ms-excel": ".xls",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",  # NOQA: E501
            "application/vnd.ms-powerpoint": ".ppt",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",  # NOQA: E501
            "application/vnd.openxmlformats-officedocument.presentationml.slideshow": ".ppsx",  # NOQA: E501
            "application/vnd.oasis.opendocument.presentation": ".odp",
            "application/vnd.oasis.opendocument.spreadsheet": ".ods",
            "application/vnd.oasis.opendocument.text": ".odt",
            "text/rtf": ".rtf",
        },
    }
