import logging

import httpx
from celery import shared_task
from django.conf import settings

from paperless.network import format_host_for_url
from paperless.network import is_public_ip
from paperless.network import resolve_hostname_ips
from paperless.network import validate_outbound_http_url

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
            ips = resolve_hostname_ips(hostname)
        except ValueError as e:
            raise httpx.ConnectError(str(e)) from e

        if not self.allow_internal:
            for ip_str in ips:
                if not is_public_ip(ip_str):
                    raise httpx.ConnectError(
                        f"Connection blocked: {hostname} resolves to a non-public address",
                    )

        ip_str = ips[0]
        formatted_ip = format_host_for_url(ip_str)

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
    try:
        parsed = validate_outbound_http_url(
            url,
            allowed_schemes=settings.WEBHOOKS_ALLOWED_SCHEMES,
            allowed_ports=settings.WEBHOOKS_ALLOWED_PORTS,
            # Internal-address checks happen in transport to preserve ConnectError behavior.
            allow_internal=True,
        )
    except ValueError as e:
        logger.warning("Webhook blocked: %s", e)
        raise

    hostname = parsed.hostname
    if hostname is None:  # pragma: no cover
        raise ValueError("Invalid URL scheme or hostname.")

    transport = WebhookTransport(
        hostname=hostname,
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
