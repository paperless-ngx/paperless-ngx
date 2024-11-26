from django.conf import settings
from django.utils import translation

from paperless import version


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

class LoginLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/accounts/login/'):
            language = request.COOKIES.get('django_language')
            print(language)
            if language:
                translation.activate(language)
            else:
                translation.activate('vi')
                request.LANGUAGE_CODE = 'vi'
        response = self.get_response(request)
        return response
