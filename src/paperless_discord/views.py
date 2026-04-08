import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import RedirectView

from .auth import DiscordAuthenticationBackend
from .client import (
    build_authorization_url,
    exchange_code_for_token,
    get_discord_guild_member,
    get_discord_user,
    has_discord_configuration,
)
from .consts import (
    DISCORD_AUTHENTICATION_BACKEND,
    DISCORD_LOGIN_ERROR_ATTR,
    DISCORD_NEXT_URL_SESSION_KEY,
    DISCORD_STATE_SESSION_KEY,
    ERROR_DISCORD_ACCESS_FAILED,
    ERROR_DISCORD_AUTH_FAILED,
    ERROR_DISCORD_INVALID_STATE,
    ERROR_DISCORD_MEMBER_REQUIRED,
    ERROR_DISCORD_MISSING_CONFIGURATION,
    ERROR_DISCORD_PROFILE_FAILED,
    ERROR_DISCORD_TOKEN_FAILED,
    LOGIN_ROUTE_NAME,
)


def _store_next_url(request):
    next_url = request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        request.session[DISCORD_NEXT_URL_SESSION_KEY] = next_url
    else:
        request.session.pop(DISCORD_NEXT_URL_SESSION_KEY, None)


def _get_post_login_redirect(request):
    next_url = request.session.pop(DISCORD_NEXT_URL_SESSION_KEY, None)
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return resolve_url(settings.LOGIN_REDIRECT_URL)


class DiscordSignInView(RedirectView):
    """Redirect the browser to the Discord authorization endpoint."""

    permanent = False
    query_string = False

    def get_redirect_url(self, *args, **kwargs):
        if not has_discord_configuration():
            messages.error(self.request, str(ERROR_DISCORD_MISSING_CONFIGURATION))
            return resolve_url(LOGIN_ROUTE_NAME)

        _store_next_url(self.request)
        state = secrets.token_urlsafe(32)
        self.request.session[DISCORD_STATE_SESSION_KEY] = state
        return build_authorization_url(self.request, state)


class DiscordCallbackView(View):
    """Handle the Discord OAuth callback and log the user in."""

    def get(self, request, *args, **kwargs):
        if request.GET.get("error"):
            messages.error(request, str(ERROR_DISCORD_ACCESS_FAILED))
            return redirect(LOGIN_ROUTE_NAME)

        if not self._has_valid_state(request):
            messages.error(request, str(ERROR_DISCORD_INVALID_STATE))
            return redirect(LOGIN_ROUTE_NAME)

        code = request.GET.get("code")
        access_token = exchange_code_for_token(request, code)
        if not access_token:
            messages.error(request, str(ERROR_DISCORD_TOKEN_FAILED))
            return redirect(LOGIN_ROUTE_NAME)

        base_user_data = get_discord_user(access_token)
        if not base_user_data:
            messages.error(request, str(ERROR_DISCORD_PROFILE_FAILED))
            return redirect(LOGIN_ROUTE_NAME)

        # Guild member check is optional — only when DISCORD_GUILD_ID is set
        guild_member = get_discord_guild_member(access_token)
        if getattr(settings, "DISCORD_GUILD_ID", None) and not guild_member:
            messages.error(request, str(ERROR_DISCORD_MEMBER_REQUIRED))
            return redirect(LOGIN_ROUTE_NAME)

        payload = self._build_payload(base_user_data, guild_member)
        backend = DiscordAuthenticationBackend()
        user = backend.authenticate(request, discord_user=payload)
        if not user:
            error_msg = str(getattr(request, DISCORD_LOGIN_ERROR_ATTR, ERROR_DISCORD_AUTH_FAILED))
            messages.error(request, error_msg)
            return redirect(LOGIN_ROUTE_NAME)

        login(request, user, backend=DISCORD_AUTHENTICATION_BACKEND)
        return redirect(_get_post_login_redirect(request))

    @staticmethod
    def _build_payload(base_user_data, guild_member):
        return {
            "id": base_user_data.get("id"),
            "username": base_user_data.get("username"),
            "email": base_user_data.get("email"),
            "global_name": base_user_data.get("global_name"),
            "nick": (guild_member or {}).get("nick"),
            "roles": (guild_member or {}).get("roles", []),
            "avatar": base_user_data.get("avatar"),
        }

    @staticmethod
    def _has_valid_state(request):
        expected = request.session.pop(DISCORD_STATE_SESSION_KEY, None)
        received = request.GET.get("state")
        if not expected or not received:
            return False
        return secrets.compare_digest(received, expected)
