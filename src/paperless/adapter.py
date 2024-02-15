from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.urls import reverse


class CustomAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        allow_signups = super().is_open_for_signup(request)
        # Override with setting, otherwise default to super.
        return getattr(settings, "ACCOUNT_ALLOW_SIGNUPS", allow_signups)

    def is_safe_url(self, url):
        # see https://github.com/paperless-ngx/paperless-ngx/issues/5780
        from django.utils.http import url_has_allowed_host_and_scheme

        # get_host already validates the given host, so no need to check it again
        allowed_hosts = {context.request.get_host()} | set(settings.ALLOWED_HOSTS)

        if "*" in allowed_hosts:
            # dont allow wildcard to allow urls from any host
            allowed_hosts.remove("*")
            allowed_hosts.add(context.request.get_host())
            return url_has_allowed_host_and_scheme(url, allowed_hosts=allowed_hosts)

        return url_has_allowed_host_and_scheme(url, allowed_hosts=allowed_hosts)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        allow_signups = super().is_open_for_signup(request, sociallogin)
        # Override with setting, otherwise default to super.
        return getattr(settings, "SOCIALACCOUNT_ALLOW_SIGNUPS", allow_signups)

    def get_connect_redirect_url(self, request, socialaccount):
        """
        Returns the default URL to redirect to after successfully
        connecting a social account.
        """
        url = reverse("base")
        return url

    def populate_user(self, request, sociallogin, data):
        # TODO: If default global permissions are implemented, should also be here
        return super().populate_user(request, sociallogin, data)  # pragma: no cover
