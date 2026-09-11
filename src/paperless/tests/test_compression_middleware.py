from django.http import HttpResponse
from django.http import StreamingHttpResponse
from django.test import RequestFactory
from django.test import TestCase

from paperless.middleware import StreamAwareCompressionMiddleware


class TestStreamAwareCompressionMiddleware(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.factory = RequestFactory()
        self.middleware = StreamAwareCompressionMiddleware(lambda request: None)

    def _request(self):
        return self.factory.get(
            "/api/documents/chat/",
            HTTP_ACCEPT_ENCODING="gzip, deflate, br, zstd",
        )

    def test_event_stream_is_not_compressed(self) -> None:
        """
        GIVEN:
            - A server-sent event response produced chunk by chunk
        WHEN:
            - The compression middleware processes it
        THEN:
            - It is passed through unencoded, one wire chunk per source chunk
        """
        chunks = [f"token{i} ".encode() for i in range(40)]
        response = StreamingHttpResponse(
            iter(chunks),
            content_type="text/event-stream",
        )

        response = self.middleware.process_response(self._request(), response)

        assert not response.has_header("Content-Encoding")
        assert list(response.streaming_content) == chunks

    def test_regular_response_is_still_compressed(self) -> None:
        """
        GIVEN:
            - An ordinary response large enough to be worth compressing
        WHEN:
            - The compression middleware processes it
        THEN:
            - It is compressed as before
        """
        response = HttpResponse(b"a" * 5000, content_type="application/json")

        response = self.middleware.process_response(self._request(), response)

        assert response.has_header("Content-Encoding")
