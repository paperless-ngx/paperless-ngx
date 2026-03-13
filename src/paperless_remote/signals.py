from __future__ import annotations

from typing import Any


def get_parser(logging_group: object = None) -> Any:
    from paperless.parsers.remote import RemoteDocumentParser

    return RemoteDocumentParser(logging_group)


def get_supported_mime_types() -> dict[str, str]:
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


def remote_consumer_declaration(sender: Any, **kwargs: Any) -> dict[str, Any]:
    return {
        "parser": get_parser,
        "weight": 5,
        "mime_types": get_supported_mime_types(),
    }
