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

    print("Waiting for Redis...", flush=True)

    attempt = 0
    with Redis.from_url(url=REDIS_URL) as client:
        while attempt < MAX_RETRY_COUNT:
            try:
                client.ping()
                break
            except Exception as e:
                print(
                    f"Redis ping #{attempt} failed.\n"
                    f"Error: {e!s}.\n"
                    f"Waiting {RETRY_SLEEP_SECONDS}s",
                    flush=True,
                )
                time.sleep(RETRY_SLEEP_SECONDS)
                attempt += 1

    if attempt >= MAX_RETRY_COUNT:
        print("Failed to connect to redis using environment variable PAPERLESS_REDIS.")
        sys.exit(os.EX_UNAVAILABLE)
    else:
        print("Connected to Redis broker.")
        sys.exit(os.EX_OK)
