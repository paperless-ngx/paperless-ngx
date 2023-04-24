import logging

from django.conf import settings
from ipware import get_client_ip

logger = logging.getLogger("paperless.auth")


# https://docs.djangoproject.com/en/4.1/ref/contrib/auth/#django.contrib.auth.signals.user_login_failed
def handle_failed_login(sender, credentials, request, **kwargs):
    client_ip, is_routable = get_client_ip(
        request,
        proxy_trusted_ips=settings.TRUSTED_PROXIES,
    )
    if client_ip is None:
        logger.info(
            f"Login failed for user `{credentials['username']}`."
            " Unable to determine IP address.",
        )
    else:
        if is_routable:
            # We got the client's IP address
            logger.info(
                f"Login failed for user `{credentials['username']}`"
                f" from IP `{client_ip}.`",
            )
        else:
            # The client's IP address is private
            logger.info(
                f"Login failed for user `{credentials['username']}`"
                f" from private IP `{client_ip}.`",
            )
