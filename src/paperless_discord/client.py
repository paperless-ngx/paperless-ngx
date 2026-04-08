from urllib.parse import urlencode, urlparse

import httpx
from django.conf import settings
from django.urls import reverse

from .consts import (
    DISCORD_API_TIMEOUT,
    DISCORD_GUILD_MEMBER_PATH,
    DISCORD_REDIRECT_ROUTE_NAME,
    DISCORD_TOKEN_PATH,
    DISCORD_USER_PATH,
    LOCAL_DEV_HOSTS,
)


def has_discord_configuration():
    """Return whether the required Discord OAuth settings are available."""
    return bool(
        getattr(settings, "DISCORD_CLIENT_ID", None)
        and getattr(settings, "DISCORD_CLIENT_SECRET", None)
        and getattr(settings, "DISCORD_SCOPES", None)
    )


def get_redirect_uri(request):
    """Return the configured redirect URI or build it from the current request."""
    callback_uri = request.build_absolute_uri(reverse(DISCORD_REDIRECT_ROUTE_NAME))
    configured = getattr(settings, "DISCORD_REDIRECT_URI", None)
    if not configured:
        return callback_uri

    configured_parsed = urlparse(configured)
    request_parsed = urlparse(callback_uri)

    if configured_parsed.hostname in LOCAL_DEV_HOSTS and configured_parsed.netloc != request_parsed.netloc:
        return callback_uri

    return configured


def build_authorization_url(request, state):
    """Build the Discord authorization URL for the current request."""
    params = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "redirect_uri": get_redirect_uri(request),
        "response_type": getattr(settings, "DISCORD_RESPONSE_TYPE", "code"),
        "scope": " ".join(getattr(settings, "DISCORD_SCOPES", ["identify", "email"])),
        "state": state,
    }
    auth_url = getattr(settings, "DISCORD_AUTH_URL", "https://discord.com/oauth2/authorize")
    return f"{auth_url}?{urlencode(params)}"


def exchange_code_for_token(request, code):
    """Exchange the Discord authorization code for an access token."""
    if not code:
        return None

    data = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "client_secret": settings.DISCORD_CLIENT_SECRET,
        "grant_type": getattr(settings, "DISCORD_GRANT_TYPE", "authorization_code"),
        "code": code,
        "redirect_uri": get_redirect_uri(request),
        "scope": " ".join(getattr(settings, "DISCORD_SCOPES", ["identify", "email"])),
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    api_url = getattr(settings, "DISCORD_API_URL", "https://discord.com/api")

    try:
        response = httpx.post(
            f"{api_url}{DISCORD_TOKEN_PATH}",
            data=data,
            headers=headers,
            timeout=DISCORD_API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("access_token")
    except (httpx.HTTPError, ValueError):
        return None


def get_discord_guild_member(access_token):
    """Return the Discord guild member payload for the configured guild."""
    guild_id = getattr(settings, "DISCORD_GUILD_ID", None)
    if not access_token or not guild_id:
        return None

    api_url = getattr(settings, "DISCORD_API_URL", "https://discord.com/api")
    try:
        response = httpx.get(
            f"{api_url}{DISCORD_GUILD_MEMBER_PATH.format(guild_id=guild_id)}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=DISCORD_API_TIMEOUT,
        )
        if response.status_code in {401, 403, 404}:
            return None
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return None


def get_discord_user(access_token):
    """Return the authenticated Discord user profile."""
    if not access_token:
        return None

    api_url = getattr(settings, "DISCORD_API_URL", "https://discord.com/api")
    try:
        response = httpx.get(
            f"{api_url}{DISCORD_USER_PATH}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=DISCORD_API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return None
