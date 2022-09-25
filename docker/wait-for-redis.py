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

for path in [
    "/usr/src/paperless",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
]:
    helpers_lib = path + "/src/paperless/helpers.py"
    if os.path.exists(helpers_lib):
        with open(helpers_lib, "rb") as source_file:
            code = compile(source_file.read(), helpers_lib, "exec")
        exec(code)
        break

if __name__ == "__main__":

    MAX_RETRY_COUNT: Final[int] = 5
    RETRY_SLEEP_SECONDS: Final[int] = 5

    PAPERLESS_REDIS: Final[str] = os.getenv("PAPERLESS_REDIS", "redis://localhost:6379")
    PAPERLESS_REDIS_SENTINEL: Final[str] = os.getenv(
        "PAPERLESS_REDIS_SENTINEL",
        "master_name=mymaster",
    )

    print(f"Waiting for Redis...", flush=True)

    client = build_redis_client(PAPERLESS_REDIS, PAPERLESS_REDIS_SENTINEL)

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
