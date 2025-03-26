from urllib.parse import quote

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.forms import ValidationError
from django.urls import reverse


class CustomAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """
        Check whether the site is open for signups, which can be
        disabled via the ACCOUNT_ALLOW_SIGNUPS setting.
        """
        allow_signups = super().is_open_for_signup(request)
        # Override with setting, otherwise default to super.
        return getattr(settings, "ACCOUNT_ALLOW_SIGNUPS", allow_signups)

    def pre_authenticate(self, request, **credentials):
        """
        Called prior to calling the authenticate method on the
        authentication backend. If login is disabled using DISABLE_REGULAR_LOGIN,
        raise ValidationError to prevent the login.
        """
        if settings.DISABLE_REGULAR_LOGIN:
            raise ValidationError("Regular login is disabled")

        return super().pre_authenticate(request, **credentials)

    def is_safe_url(self, url):
        """
        Check if the URL is a safe URL.
        See https://github.com/paperless-ngx/paperless-ngx/issues/5780
        """
        from django.utils.http import url_has_allowed_host_and_scheme

        # get_host already validates the given host, so no need to check it again
        allowed_hosts = {context.request.get_host()} | set(settings.ALLOWED_HOSTS)

        if "*" in allowed_hosts:
            # dont allow wildcard to allow urls from any host
            allowed_hosts.remove("*")
            allowed_hosts.add(context.request.get_host())
            return url_has_allowed_host_and_scheme(url, allowed_hosts=allowed_hosts)

        return url_has_allowed_host_and_scheme(url, allowed_hosts=allowed_hosts)

    def get_reset_password_from_key_url(self, key):
        """
        Return the URL to reset a password e.g. in reset email.
        """
        if settings.PAPERLESS_URL is None:
            return super().get_reset_password_from_key_url(key)
        else:
            path = reverse(
                "account_reset_password_from_key",
                kwargs={"uidb36": "UID", "key": "KEY"},
            )
            path = path.replace("UID-KEY", quote(key))
            return settings.PAPERLESS_URL + path


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        """
        Check whether the site is open for signups via social account, which can be
        disabled via the SOCIALACCOUNT_ALLOW_SIGNUPS setting.
        """
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
        """
        Populate the user with data from the social account. Stub is kept in case
        global default permissions are implemented in the future.
        """
        # TODO: If default global permissions are implemented, should also be here
        return super().populate_user(request, sociallogin, data)  # pragma: no cover
