"""Database caching utilities."""

import redis
from cachalot.utils import get_query_cache_key
from cachalot.utils import get_table_cache_key
from django.core.cache import cache

from paperless import settings

PREFIX = "cachalot_"


def custom_get_query_cache_key(compiler):
    return PREFIX + get_query_cache_key(compiler)


def custom_get_table_cache_key(db_alias, table):
    return PREFIX + get_table_cache_key(db_alias, table)


def _cache_key_prefix():
    return cache.make_key(PREFIX)


class CacheManager:
    def __init__(self):
        if "cachalot" in settings.INSTALLED_APPS:
            self.redis_instance = redis.from_url(settings.CACHALOT_REDIS_URL)
        else:
            self.redis_instance = None

    def invalidate_cache(self, prefix=_cache_key_prefix(), chunk_size=1000) -> int:
        deleted_keys = 0
        if self.redis_instance:
            # Delete all Redis keys related to Cachalot
            for key in self.redis_instance.scan_iter(f"{prefix}*", count=chunk_size):
                self.redis_instance.delete(key)
                deleted_keys += 1

        return deleted_keys
