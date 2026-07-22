import logging

import httpx
from celery import shared_task
from django.conf import settings

from paperless.network import PinnedHostHTTPTransport
from paperless.network import validate_outbound_http_url

logger = logging.getLogger("paperless.workflows.webhooks")


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
        validate_outbound_http_url(
            url,
            allowed_schemes=settings.WEBHOOKS_ALLOWED_SCHEMES,
            allowed_ports=settings.WEBHOOKS_ALLOWED_PORTS,
            # Internal-address checks happen in transport to preserve ConnectError behavior.
            allow_internal=True,
        )
    except ValueError as e:
        logger.warning("Webhook blocked: %s", e)
        raise

    transport = PinnedHostHTTPTransport(
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
