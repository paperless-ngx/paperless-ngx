import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx
from celery import shared_task
from django.conf import settings

logger = logging.getLogger("paperless.workflows.webhooks")


class WebhookTransport(httpx.HTTPTransport):
    """
    Transport that resolves/validates hostnames and rewrites to a vetted IP
    while keeping Host/SNI as the original hostname.
    """

    def __init__(
        self,
        hostname: str,
        *args,
        allow_internal: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.hostname = hostname
        self.allow_internal = allow_internal

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        hostname = request.url.host

        if not hostname:
            raise httpx.ConnectError("No hostname in request URL")

        try:
            addr_info = socket.getaddrinfo(hostname, None)
        except socket.gaierror as e:
            raise httpx.ConnectError(f"Could not resolve hostname: {hostname}") from e

        ips = [info[4][0] for info in addr_info if info and info[4]]
        if not ips:
            raise httpx.ConnectError(f"Could not resolve hostname: {hostname}")

        if not self.allow_internal:
            for ip_str in ips:
                if not WebhookTransport.is_public_ip(ip_str):
                    raise httpx.ConnectError(
                        f"Connection blocked: {hostname} resolves to a non-public address",
                    )

        ip_str = ips[0]
        formatted_ip = self._format_ip_for_url(ip_str)

        new_headers = httpx.Headers(request.headers)
        if "host" in new_headers:
            del new_headers["host"]
        new_headers["Host"] = hostname
        new_url = request.url.copy_with(host=formatted_ip)

        request = httpx.Request(
            method=request.method,
            url=new_url,
            headers=new_headers,
            content=request.stream,
            extensions=request.extensions,
        )
        request.extensions["sni_hostname"] = hostname

        return super().handle_request(request)

    def _format_ip_for_url(self, ip: str) -> str:
        """
        Format IP address for use in URL (wrap IPv6 in brackets)
        """
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.version == 6:
                return f"[{ip}]"
            return ip
        except ValueError:
            return ip

    @staticmethod
    def is_public_ip(ip: str | int) -> bool:
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

    @staticmethod
    def resolve_first_ip(host: str) -> str | None:
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

    transport = WebhookTransport(
        hostname=p.hostname,
        allow_internal=settings.WEBHOOKS_ALLOW_INTERNAL_REQUESTS,
    )

    try:
        post_args = {
            "url": url,
            "headers": {
                k: v for k, v in (headers or {}).items() if k.lower() != "host"
            },
            "files": files or None,
        }
        if as_json:
            post_args["json"] = data
        elif isinstance(data, dict):
            post_args["data"] = data
        else:
            post_args["content"] = data

        with httpx.Client(
            transport=transport,
            timeout=5.0,
            follow_redirects=False,
        ) as client:
            client.post(
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
    finally:
        transport.close()
