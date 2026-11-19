from asgiref.sync import iscoroutinefunction
from asgiref.sync import markcoroutinefunction
from compression_middleware.middleware import CompressionMiddleware
from django.conf import settings

from paperless import version


class StreamAwareCompressionMiddleware(CompressionMiddleware):
    """
    Bypasses compression for server-sent streams (text/event-stream).

    See https://github.com/friedelwolff/django-compression-middleware/pull/7
    """

    def process_response(self, request, response):
        content_type = response.headers.get("Content-Type", "")
        if content_type.startswith("text/event-stream"):
            return response
        return super().process_response(request, response)


class ApiVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            versions = settings.REST_FRAMEWORK["ALLOWED_VERSIONS"]
            response["X-Api-Version"] = versions[len(versions) - 1]
            response["X-Version"] = version.__full_version_str__

        return response


class FileMoveMiddleware:
    """
    Open a document file move scope around each request, so every document the
    request changes is moved once, after its writes have committed, before the
    response is returned.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response) -> None:
        self.get_response = get_response
        self.async_mode = iscoroutinefunction(get_response)
        if self.async_mode:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self.async_mode:
            return self.__acall__(request)

        from documents.file_moves import defer_file_moves

        with defer_file_moves():
            return self.get_response(request)

    async def __acall__(self, request):
        from documents.file_moves import adefer_file_moves

        async with adefer_file_moves():
            return await self.get_response(request)
