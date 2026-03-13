def get_parser(*args, **kwargs):
    from paperless.parsers.remote import RemoteDocumentParser

    return RemoteDocumentParser(*args, **kwargs)


def get_supported_mime_types():
    from django.conf import settings

    from paperless.parsers.remote import RemoteDocumentParser
    from paperless.parsers.remote import RemoteEngineConfig

    config = RemoteEngineConfig(
        engine=settings.REMOTE_OCR_ENGINE,
        api_key=settings.REMOTE_OCR_API_KEY,
        endpoint=settings.REMOTE_OCR_ENDPOINT,
    )
    if not config.engine_is_valid():
        return {}
    return RemoteDocumentParser.supported_mime_types()


def remote_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 5,
        "mime_types": get_supported_mime_types(),
    }
