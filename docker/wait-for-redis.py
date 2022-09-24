#!/usr/bin/env python3
"""
Simple script which attempts to ping the Redis broker as set in the environment for
a certain number of times, waiting a little bit in between

"""
import os
import sys
import time
from typing import Final
from urllib.parse import parse_qs
from urllib.parse import urlparse

from redis import Redis
from redis import Sentinel

if __name__ == "__main__":

    MAX_RETRY_COUNT: Final[int] = 5
    RETRY_SLEEP_SECONDS: Final[int] = 5

    REDIS_URL: Final[str] = os.getenv("PAPERLESS_REDIS", "redis://localhost:6379")

    print(f"Waiting for Redis...", flush=True)

    url = urlparse(REDIS_URL)
    scheme_split = url.scheme.split("+")
    if "sentinel" in scheme_split:
        query = parse_qs(url.query)
        connection_kwargs = {
            "username": url.username,  # redis node username
            "password": url.password,  # redis node password
            "ssl": ("rediss" in scheme_split),
            "db": url.path[1:],
        }
        if "rediss" in scheme_split:
            connection_kwargs["ssl_cert_reqs"] = query.get(
                "ssl_cert_reqs",
                ["required"],
            )[0]

        sentinel = Sentinel(
            [(url.hostname, url.port)],
            sentinel_kwargs={
                "username": query.get("sentinelusername", [""])[0],
                "password": query.get("sentinelpassword", [""])[0],
                "ssl": ("rediss" in scheme_split),
                "ssl_cert_reqs": query.get("ssl_cert_reqs", ["required"])[0],
            },
            **connection_kwargs,
        )
        client = sentinel.master_for(query.get("mastername", ["mymaster"])[0])
    else:
        client = Redis.from_url(url=REDIS_URL)

    attempt = 0
    with client:
        while attempt < MAX_RETRY_COUNT:
            try:
                client.ping()
                break
            except Exception as e:
                print(
                    f"Redis ping #{attempt} failed.\n"
                    f"Error: {str(e)}.\n"
                    f"Waiting {RETRY_SLEEP_SECONDS}s",
                    flush=True,
                )
                time.sleep(RETRY_SLEEP_SECONDS)
                attempt += 1

    if attempt >= MAX_RETRY_COUNT:
        print(f"Failed to connect to redis using environment variable PAPERLESS_REDIS.")
        sys.exit(os.EX_UNAVAILABLE)
    else:
        print(f"Connected to Redis broker.")
        sys.exit(os.EX_OK)
