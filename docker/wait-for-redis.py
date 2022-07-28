#!/usr/bin/env python3
"""
Simple script which attempts to ping the Redis broker as set in the environment for
a certain number of times, waiting a little bit in between

"""
import os
import sys
import time
from typing import Final

from redis import Redis

if __name__ == "__main__":

    MAX_RETRY_COUNT: Final[int] = 5
    RETRY_SLEEP_SECONDS: Final[int] = 5

    REDIS_URL: Final[str] = os.getenv("PAPERLESS_REDIS", "redis://localhost:6379")

    print(f"Waiting for Redis: {REDIS_URL}", flush=True)

    attempt = 0
    with Redis.from_url(url=REDIS_URL) as client:
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
        print(f"Failed to connect to: {REDIS_URL}")
        sys.exit(os.EX_UNAVAILABLE)
    else:
        print(f"Connected to Redis broker: {REDIS_URL}")
        sys.exit(os.EX_OK)
