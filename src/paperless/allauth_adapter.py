import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger("paperless.handlers")


class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        return reverse("base")

    def is_open_for_signup(self, request):
        return getattr(settings, "ACCOUNT_ENABLE_SIGNUP", False)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        # True indicates a user should be automatically created on successful
        # login via configured external provider
        return getattr(settings, "SOCIALACCOUNT_ENABLE_SIGNUP", True)

    def authentication_error(
        self,
        request,
        provider_id,
        error=None,
        exception=None,
        extra_context=None,
    ):
        logger.error(f"Authentication error: {exception}")
        return super().authentication_error(
            request,
            provider_id,
            error,
            exception,
            extra_context,
        )
