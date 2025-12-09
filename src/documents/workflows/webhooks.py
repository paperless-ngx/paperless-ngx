import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx
from celery import shared_task
from django.conf import settings

logger = logging.getLogger("paperless.workflows.webhooks")


def _is_public_ip(ip: str) -> bool:
    try:
        obj = ipaddress.ip_address(ip)
        return not (
            obj.is_private
            or obj.is_loopback
            or obj.is_link_local
            or obj.is_multicast
            or obj.is_unspecified
        )
    except ValueError:  # pragma: no cover
        return False


def _resolve_first_ip(host: str) -> str | None:
    try:
        info = socket.getaddrinfo(host, None)
        return info[0][4][0] if info else None
    except Exception:  # pragma: no cover
        return None


@shared_task(
    retry_backoff=True,
    autoretry_for=(httpx.HTTPStatusError,),
    max_retries=3,
    throws=(httpx.HTTPError,),
)
def send_webhook(
    url: str,
    data: str | dict,
    headers: dict,
    files: dict,
    *,
    as_json: bool = False,
):
    p = urlparse(url)
    if p.scheme.lower() not in settings.WEBHOOKS_ALLOWED_SCHEMES or not p.hostname:
        logger.warning("Webhook blocked: invalid scheme/hostname")
        raise ValueError("Invalid URL scheme or hostname.")

    port = p.port or (443 if p.scheme == "https" else 80)
    if (
        len(settings.WEBHOOKS_ALLOWED_PORTS) > 0
        and port not in settings.WEBHOOKS_ALLOWED_PORTS
    ):
        logger.warning("Webhook blocked: port not permitted")
        raise ValueError("Destination port not permitted.")

    ip = _resolve_first_ip(p.hostname)
    if not ip or (
        not _is_public_ip(ip) and not settings.WEBHOOKS_ALLOW_INTERNAL_REQUESTS
    ):
        logger.warning("Webhook blocked: destination not allowed")
        raise ValueError("Destination host is not allowed.")

    try:
        post_args = {
            "url": url,
            "headers": {
                k: v for k, v in (headers or {}).items() if k.lower() != "host"
            },
            "files": files or None,
            "timeout": 5.0,
            "follow_redirects": False,
        }
        if as_json:
            post_args["json"] = data
        elif isinstance(data, dict):
            post_args["data"] = data
        else:
            post_args["content"] = data

        httpx.post(
            **post_args,
        ).raise_for_status()
        logger.info(
            f"Webhook sent to {url}",
        )
    except Exception as e:
        logger.error(
            f"Failed attempt sending webhook to {url}: {e}",
        )
        raise e
