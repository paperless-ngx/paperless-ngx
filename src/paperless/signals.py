import logging

from django.conf import settings
from python_ipware import IpWare

logger = logging.getLogger("paperless.auth")


# https://docs.djangoproject.com/en/4.1/ref/contrib/auth/#django.contrib.auth.signals.user_login_failed
def handle_failed_login(sender, credentials, request, **kwargs):
    ipware = IpWare(proxy_list=settings.TRUSTED_PROXIES)
    client_ip, _ = ipware.get_client_ip(
        meta=request.META,
    )
    username = credentials.get("username")
    log_output = (
        "No authentication provided"
        if username is None
        else f"Login failed for user `{username}`"
    )

    if client_ip is None:
        log_output += ". Unable to determine IP address."
    else:
        if client_ip.is_global:
            # We got the client's IP address
            log_output += f" from IP `{client_ip}`."
        else:
            # The client's IP address is private
            log_output += f" from private IP `{client_ip}`."

    logger.info(log_output)


def handle_social_account_updated(sender, request, sociallogin, **kwargs):
    """
    Handle the social account update signal.
    """
    from django.contrib.auth.models import Group

    if not sociallogin.user.is_active:
        # allauth looks up and updates the social account, firing this
        # signal, before checking if the user is allowed to actually log
        # in. Syncing groups/roles here would arm a deactivated account
        # with permissions it never exercised, which would silently take
        # effect if the account is later reactivated for an unrelated
        # reason.
        logger.debug(
            f"Skipping social account sync for inactive user `{sociallogin.user}`",
        )
        return

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

    user_modified = False
    if (
        settings.SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP
        and social_account_groups is not None
    ):
        is_superuser = (
            settings.SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP in social_account_groups
        )
        if sociallogin.user.is_superuser != is_superuser:
            sociallogin.user.is_superuser = is_superuser
            user_modified = True

    if settings.SOCIAL_ACCOUNT_SYNC_STAFF_GROUP and social_account_groups is not None:
        is_staff = (
            settings.SOCIAL_ACCOUNT_SYNC_STAFF_GROUP in social_account_groups
        ) or sociallogin.user.is_superuser
        if sociallogin.user.is_staff != is_staff:
            sociallogin.user.is_staff = is_staff
            user_modified = True
    elif (
        settings.SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP
        and social_account_groups is not None
    ):
        is_staff = sociallogin.user.is_superuser or sociallogin.user.is_staff
        if sociallogin.user.is_staff != is_staff:
            sociallogin.user.is_staff = is_staff
            user_modified = True

    if user_modified:
        logger.debug(
            f"Syncing roles for user `{sociallogin.user}`: superuser={sociallogin.user.is_superuser}, staff={sociallogin.user.is_staff}",
        )
        sociallogin.user.save(update_fields=["is_superuser", "is_staff"])
