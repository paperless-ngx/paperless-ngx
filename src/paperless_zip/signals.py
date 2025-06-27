def get_parser(*args, **kwargs):
    from paperless_zip.parsers import ZipDocumentParser

    return ZipDocumentParser(*args, **kwargs)


def zip_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 10,
        "mime_types": {
            "application/zip": ".zip",
        },
    }
