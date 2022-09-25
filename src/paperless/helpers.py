from urllib.parse import parse_qs
from urllib.parse import urlparse

from redis import Redis
from redis.sentinel import Sentinel


def build_redis_client(
    paperless_redis: str,
    paperless_redis_sentinel: str = "",
) -> Redis:
    redis_urls = list(map(str.strip, paperless_redis.split(";")))

    if len(redis_urls) == 1 and redis_urls[0][:8] != "sentinel":
        return Redis.from_url(url=redis_urls[0])

    if any(r[:8] != "sentinel" for r in redis_urls):
        raise ValueError(
            "when providing multiple redis urls, "
            "all of them need to follow sentinel:// scheme",
        )

    sentinels = []
    for redis_url in redis_urls:
        url = urlparse(redis_url)
        sentinels.append((url.hostname, url.port))

    query = parse_qs(paperless_redis_sentinel)
    ssl = query.get("ssl", ["true"])[0] != "false"

    connection_kwargs = {
        "username": query.get("redis_username", [""])[0],
        "password": query.get("redis_password", [""])[0],
        "ssl": ssl,
        "db": url.path[1:],
    }

    sentinel_kwargs = {
        "username": query.get("sentinel_username", [""])[0],
        "password": query.get("sentinel_password", [""])[0],
        "ssl": ssl,
    }

    if ssl:
        ssl_cert_reqs = query.get("ssl_cert_reqs", ["required"])[0]
        connection_kwargs["ssl_cert_reqs"] = ssl_cert_reqs
        sentinel_kwargs["ssl_cert_reqs"] = ssl_cert_reqs

    sentinel = Sentinel(
        sentinels,
        sentinel_kwargs=sentinel_kwargs,
        **connection_kwargs,
    )
    return sentinel.master_for(query.get("master_name", ["mymaster"])[0])
