def get_parser(*args, **kwargs):
    from paperless_remote.parsers import RemoteDocumentParser

    return RemoteDocumentParser(*args, **kwargs)


def get_supported_mime_types():
    from paperless_remote.parsers import RemoteDocumentParser

    return RemoteDocumentParser(None).supported_mime_types()


def remote_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 5,
        "mime_types": get_supported_mime_types(),
    }
