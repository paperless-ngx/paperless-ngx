"""
Shared utilities for Redis Sentinel configuration parsing.
"""

import os


def parse_redis_sentinel_config() -> dict | None:
    """
    Parse Redis Sentinel configuration from environment variables.

    Returns a dict with sentinel configuration or None if not configured.
    """
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
