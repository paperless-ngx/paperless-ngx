from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import StreamingHttpResponse


def read_streaming_response(response: StreamingHttpResponse) -> bytes:
    """Consume a StreamingHttpResponse/FileResponse and close it."""
    content = b"".join(response.streaming_content)
    response.close()
    return content
