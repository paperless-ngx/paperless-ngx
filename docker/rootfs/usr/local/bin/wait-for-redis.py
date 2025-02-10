#!/usr/bin/env python3
"""
Simple script which attempts to ping the Redis broker as set in the environment for
a certain number of times, waiting a little bit in between

"""

import os
import sys
import time

import click
from redis import Redis


@click.command(context_settings={"show_default": True})
@click.option(
    "--retry-count",
    default=5,
    type=int,
    help="Count of times to retry the Redis connection",
)
@click.option(
    "--retry-sleep",
    default=5,
    type=int,
    help="Seconds to wait between Redis connection retries",
)
@click.argument(
    "redis_url",
    type=str,
    envvar="PAPERLESS_REDIS",
    default="redis://localhost:6379",
)
def wait(redis_url: str, retry_count: int, retry_sleep: int) -> None:
    click.echo("Waiting for Redis...")

    attempt = 0
    with Redis.from_url(url=redis_url) as client:
        while attempt < retry_count:
            try:
                client.ping()
                break
            except Exception as e:
                click.echo(
                    f"Redis ping #{attempt} failed.\n"
                    f"Error: {e!s}.\n"
                    f"Waiting {retry_sleep}s",
                )
                time.sleep(retry_sleep)
                attempt += 1

    if attempt >= retry_count:
        click.echo(
            "Failed to connect to redis using environment variable PAPERLESS_REDIS.",
        )
        sys.exit(os.EX_UNAVAILABLE)
    else:
        click.echo("Connected to Redis broker.")
        sys.exit(os.EX_OK)


if __name__ == "__main__":
    wait()
