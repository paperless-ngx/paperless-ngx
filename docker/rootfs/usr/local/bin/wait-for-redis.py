#!/usr/bin/env python3
"""
Simple script which attempts to ping the Redis broker as set in the environment for
a certain number of times, waiting a little bit in between

Supports both regular Redis connections and Redis Sentinel configurations.
"""

import os
import sys
import time

import click
from redis import Redis
from redis.sentinel import Sentinel


def parse_sentinel_config():
    """Parse Redis Sentinel configuration from environment variables."""
    sentinel_hosts = os.getenv("PAPERLESS_REDIS_SENTINEL_HOSTS")
    sentinel_service = os.getenv("PAPERLESS_REDIS_SENTINEL_SERVICE_NAME", "mymaster")
    
    if not sentinel_hosts:
        return None
    
    # Parse hosts in format "host1:port1,host2:port2"
    hosts = []
    for host_port in sentinel_hosts.split(","):
        host_port = host_port.strip()
        if not host_port:  # Skip empty entries
            continue
        if ":" in host_port:
            host, port = host_port.split(":")
            hosts.append((host.strip(), int(port.strip())))
        else:
            hosts.append((host_port.strip(), 26379))  # Default Sentinel port
    
    return {
        "hosts": hosts,
        "service_name": sentinel_service,
        "password": os.getenv("PAPERLESS_REDIS_SENTINEL_PASSWORD"),
        "db": int(os.getenv("PAPERLESS_REDIS_SENTINEL_DB", "0")),
        "username": os.getenv("PAPERLESS_REDIS_SENTINEL_USERNAME"),
    }


def get_redis_client(redis_url: str = None):
    """Get a Redis client, either direct or via Sentinel."""
    sentinel_config = parse_sentinel_config()
    
    if sentinel_config:
        click.echo(f"Using Redis Sentinel with service: {sentinel_config['service_name']}")
        click.echo(f"Sentinel hosts: {sentinel_config['hosts']}")
        
        sentinel = Sentinel(
            sentinel_config["hosts"],
            password=sentinel_config["password"],
        )
        return sentinel.master_for(
            sentinel_config["service_name"],
            username=sentinel_config["username"],
            password=os.getenv("PAPERLESS_REDIS_PASSWORD"),
            db=sentinel_config["db"],
        )
    else:
        click.echo(f"Using direct Redis connection: {redis_url}")
        return Redis.from_url(redis_url)


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
    required=False,
)
def wait(redis_url: str, retry_count: int, retry_sleep: int) -> None:
    click.echo("Waiting for Redis...")

    attempt = 0
    client = None
    
    try:
        client = get_redis_client(redis_url)
        
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
                "Failed to connect to redis using environment configuration.",
            )
            sys.exit(os.EX_UNAVAILABLE)
        else:
            click.echo("Connected to Redis broker.")
            sys.exit(os.EX_OK)
            
    except Exception as e:
        click.echo(f"Failed to create Redis connection: {e}")
        sys.exit(os.EX_UNAVAILABLE)
    finally:
        if client and hasattr(client, 'close'):
            client.close()


if __name__ == "__main__":
    wait()
