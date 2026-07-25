import logging

from django.conf import settings

from paperless.utils import describe_client_suffix

logger = logging.getLogger("paperless.auth")


# https://docs.djangoproject.com/en/4.1/ref/contrib/auth/#django.contrib.auth.signals.user_login_failed
def handle_failed_login(sender, credentials, request, **kwargs):
    username = credentials.get("username")
    log_output = (
        "No authentication provided"
        if username is None
        else f"Login failed for user `{username}`"
    )

    log_output += describe_client_suffix(request)

    logger.info(log_output)


# https://docs.djangoproject.com/en/4.1/ref/contrib/auth/#django.contrib.auth.signals.user_logged_in
def handle_successful_login(sender, request, user, **kwargs):
    if settings.AUTO_LOGIN_USERNAME:
        # Auto-login re-authenticates the fixed user on every request, so
        # this isn't a meaningful login event worth logging.
        return

    log_output = f"Login successful for user `{user.get_username()}`"
    log_output += describe_client_suffix(request)

    logger.info(log_output)


def handle_social_account_updated(sender, request, sociallogin, **kwargs):
    """
    Handle the social account update signal.
    """
    from django.contrib.auth.models import Group

    extra_data = sociallogin.account.extra_data or {}
    social_account_groups = extra_data.get(
        settings.SOCIAL_ACCOUNT_SYNC_GROUPS_CLAIM,
        [],
    )  # pre-allauth 65.11.0 structure

    if not social_account_groups:
        # allauth 65.11.0+ nests claims under `userinfo`/`id_token`
        social_account_groups = (
            extra_data.get("userinfo", {}).get(
                settings.SOCIAL_ACCOUNT_SYNC_GROUPS_CLAIM,
            )
            or extra_data.get("id_token", {}).get(
                settings.SOCIAL_ACCOUNT_SYNC_GROUPS_CLAIM,
            )
            or []
        )
    if settings.SOCIAL_ACCOUNT_SYNC_GROUPS and social_account_groups is not None:
        groups = Group.objects.filter(name__in=social_account_groups)
        logger.debug(
            f"Syncing groups for user `{sociallogin.user}`: {social_account_groups}",
        )
        sociallogin.user.groups.set(groups, clear=True)
