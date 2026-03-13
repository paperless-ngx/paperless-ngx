from __future__ import annotations

from typing import Any


def get_parser(*args: Any, **kwargs: Any) -> Any:
    from paperless.parsers.text import TextDocumentParser

    # The new TextDocumentParser does not accept the progress_callback
    # kwarg injected by the old signal-based consumer.  logging_group is
    # forwarded as a positional arg.
    # Phase 4 will replace this signal path with the new ParserRegistry.
    kwargs.pop("progress_callback", None)
    return TextDocumentParser(*args, **kwargs)


def text_consumer_declaration(sender: Any, **kwargs: Any) -> dict[str, Any]:
    return {
        "parser": get_parser,
        "weight": 10,
        "mime_types": {
            "text/plain": ".txt",
            "text/csv": ".csv",
            "application/csv": ".csv",
        },
    }
