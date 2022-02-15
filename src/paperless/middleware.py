from django.conf import settings

from paperless import version


class ApiVersionMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            versions = settings.REST_FRAMEWORK['ALLOWED_VERSIONS']
            response['X-Api-Version'] = versions[len(versions)-1]
            response['X-Version'] = ".".join(
                [str(_) for _ in version.__version__]
            )

        return response
