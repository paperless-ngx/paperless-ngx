import logging

from django.conf import settings
from ipware import IpWare

logger = logging.getLogger("paperless.auth")


# https://docs.djangoproject.com/en/4.1/ref/contrib/auth/#django.contrib.auth.signals.user_login_failed
def handle_failed_login(sender, credentials, request, **kwargs):
    ipware = IpWare(proxy_trusted_list=settings.TRUSTED_PROXIES)
    client_ip, _ = ipware.get_client_ip(
        meta=request.META,
    )
    username = credentials.get("username") or "anonymous"

    if client_ip is None:
        logger.info(
            f"Login failed for user `{username}`. Unable to determine IP address.",
        )
    else:
        if client_ip.is_global:
            # We got the client's IP address
            logger.info(
                f"Login failed for user `{username}` from IP `{client_ip}.`",
            )
        else:
            # The client's IP address is private
            logger.info(
                f"Login failed for user `{username}`"
                f" from private IP `{client_ip}.`",
            )
