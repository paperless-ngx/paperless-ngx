from cachalot.api import invalidate as cachalot_invalidate
from cachalot.utils import get_query_cache_key
from cachalot.utils import get_table_cache_key

PREFIX = "pngx_cachalot_"


def custom_get_query_cache_key(compiler):
    return PREFIX + get_query_cache_key(compiler)


def custom_get_table_cache_key(db_alias, table):
    return PREFIX + get_table_cache_key(db_alias, table)


def invalidate_db_cache() -> None:
    return cachalot_invalidate(cache_alias="read-cache")
