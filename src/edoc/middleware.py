from django.utils import translation

from edoc import version


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
            if language:
                translation.activate(language)
            else:
                translation.activate('vi')
                request.LANGUAGE_CODE = 'vi'
        response = self.get_response(request)
        return response


from django.utils.timezone import now
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.conf import settings


class LicenseExpiryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path_login = '/accounts/login/'
        path_expired = '/expired/'

        # Cho phép truy cập login và trang thông báo
        if not request.path.startswith(
            path_login) or not request.path.startswith(path_expired):

            # Kiểm tra xem request có thuộc tính user không
            if hasattr(request, 'user') and request.user.is_authenticated:
                expiration_date = getattr(settings, "LICENSE_EXPIRATION_DATE",
                                          None)
                if expiration_date and expiration_date < now():
                    logout(request)
                    return redirect(path_expired)

        return self.get_response(request)
