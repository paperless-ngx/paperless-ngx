import logging
from urllib.parse import quote

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context
from allauth.headless.tokens.strategies.sessions import SessionTokenStrategy
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.forms import ValidationError
from django.http import HttpRequest
from django.urls import reverse
from rest_framework.authtoken.models import Token

from documents.models import Document
from paperless.signals import handle_social_account_updated

logger = logging.getLogger("paperless.auth")


class CustomAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """
        Check whether the site is open for signups, which can be
        disabled via the ACCOUNT_ALLOW_SIGNUPS setting.
        """
        if (
            User.objects.exclude(username__in=["consumer", "AnonymousUser"]).count()
            == 0
            and Document.global_objects.count() == 0
        ):
            # I.e. a fresh install, allow signups
            return True
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

    def save_user(self, request, user, form, commit=True):  # noqa: FBT002
        """
        Save the user instance. Default groups are assigned to the user, if
        specified in the settings.
        """

        if (
            User.objects.exclude(username__in=["consumer", "AnonymousUser"]).count()
            == 0
            and Document.global_objects.count() == 0
        ):
            # I.e. a fresh install, make the user a superuser
            logger.debug(f"Creating initial superuser `{user}`")
            user.is_superuser = True
            user.is_staff = True

        user: User = super().save_user(request, user, form, commit)
        group_names: list[str] = settings.ACCOUNT_DEFAULT_GROUPS
        if len(group_names) > 0:
            groups = Group.objects.filter(name__in=group_names)
            logger.debug(f"Adding default groups to user `{user}`: {group_names}")
            user.groups.add(*groups)
            user.save()
        return user


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

    def save_user(self, request, sociallogin, form=None):
        """
        Save the user instance. Default groups are assigned to the user, if
        specified in the settings.
        """
        # save_user also calls account_adapter save_user which would set ACCOUNT_DEFAULT_GROUPS
        user: User = super().save_user(request, sociallogin, form)
        group_names: list[str] = settings.SOCIAL_ACCOUNT_DEFAULT_GROUPS
        if len(group_names) > 0:
            groups = Group.objects.filter(name__in=group_names)
            logger.debug(
                f"Adding default social groups to user `{user}`: {group_names}",
            )
            user.groups.add(*groups)
            user.save()
        handle_social_account_updated(None, request, sociallogin)
        return user

    def on_authentication_error(
        self,
        request,
        provider,
        error=None,
        exception=None,
        extra_context=None,
    ):
        """
        Just log errors and pass them along.
        """
        logger.warning(
            f"Social authentication error for provider `{provider!s}`: {error!s} ({exception!s})",
        )
        return super().on_authentication_error(
            request,
            provider,
            error,
            exception,
            extra_context,
        )


class DrfTokenStrategy(SessionTokenStrategy):
    def create_access_token(self, request: HttpRequest) -> str | None:
        if not request.user.is_authenticated:
            return None
        token, _ = Token.objects.get_or_create(user=request.user)
        return token.key
