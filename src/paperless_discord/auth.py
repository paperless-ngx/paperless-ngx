from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

from .consts import (
    DISCORD_LOGIN_ERROR_ATTR,
    ERROR_DISCORD_ALLOWED_ROLES_MISSING,
    ERROR_DISCORD_INVALID_IDENTIFIER,
    ERROR_DISCORD_ROLE_REQUIRED,
)

User = get_user_model()


def _normalize_roles(roles):
    """Return a set of lowercase, stripped role identifiers."""
    return {str(r).lower().strip() for r in roles if r}


class DiscordAuthenticationBackend(BaseBackend):
    """Authenticate a Discord user, optionally restricted to guild roles."""

    def authenticate(self, request, discord_user=None, **kwargs):
        if request and hasattr(request, DISCORD_LOGIN_ERROR_ATTR):
            delattr(request, DISCORD_LOGIN_ERROR_ATTR)

        if not discord_user:
            return None

        user_id = str(discord_user.get("id") or "").strip()
        if not user_id:
            if request:
                setattr(request, DISCORD_LOGIN_ERROR_ATTR, ERROR_DISCORD_INVALID_IDENTIFIER)
            return None

        # Role check — only if DISCORD_ALLOWED_ROLES is configured and non-empty
        allowed_roles = _normalize_roles(getattr(settings, "DISCORD_ALLOWED_ROLES", []))
        if allowed_roles:
            roles = _normalize_roles(discord_user.get("roles", []))
            if not roles.intersection(allowed_roles):
                if request:
                    setattr(request, DISCORD_LOGIN_ERROR_ATTR, ERROR_DISCORD_ROLE_REQUIRED)
                return None

        return self._get_or_create_user(discord_user)

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    @staticmethod
    def _get_or_create_user(discord_user):
        """Return the local user linked to this Discord account, creating it if needed."""
        discord_id = str(discord_user["id"])
        username = f"discord_{discord_id}"
        email = discord_user.get("email") or f"{discord_id}@discord.invalid"
        display_name = (
            discord_user.get("nick")
            or discord_user.get("global_name")
            or discord_user.get("username")
            or username
        )
        first_name = display_name[:30]

        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "first_name": first_name},
        )
        # Keep email/name in sync on every login
        changed = False
        if user.email != email:
            user.email = email
            changed = True
        if user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if changed:
            user.save(update_fields=["email", "first_name"])

        return user
