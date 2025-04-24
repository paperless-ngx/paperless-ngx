from unittest.mock import MagicMock
from unittest.mock import patch

from paperless.db_cache import CacheManager
from paperless.db_cache import _cache_key_prefix
from paperless.db_cache import custom_get_query_cache_key
from paperless.db_cache import custom_get_table_cache_key


@patch("paperless.db_cache.get_query_cache_key")
def test_custom_get_query_cache_key(mock_get_query_cache_key):
    mock_get_query_cache_key.return_value = "query_key"
    result = custom_get_query_cache_key(MagicMock())
    assert result == "pngx_cachalot_query_key"
    mock_get_query_cache_key.assert_called_once()


@patch("paperless.db_cache.get_table_cache_key")
def test_custom_get_table_cache_key(mock_get_table_cache_key):
    mock_get_table_cache_key.return_value = "table_key"
    db_alias = "default"
    table = "test_table"
    result = custom_get_table_cache_key(db_alias, table)
    assert result == "pngx_cachalot_table_key"
    mock_get_table_cache_key.assert_called_once_with(db_alias, table)


@patch("django.core.cache.cache.make_key")
def test_cache_key_prefix(mock_make_key):
    mock_make_key.return_value = "pngx_cachalot_"
    result = _cache_key_prefix()
    assert result == "pngx_cachalot_"


@patch("paperless.db_cache.redis.from_url")
@patch("paperless.db_cache.settings")
def test_cache_manager_init_with_cachalot(mock_settings, mock_redis_from_url):
    mock_settings.INSTALLED_APPS = ["cachalot"]
    mock_settings.CACHALOT_REDIS_URL = "redis://localhost:6379/0"
    mock_redis_instance = MagicMock()
    mock_redis_from_url.return_value = mock_redis_instance

    cache_manager = CacheManager()

    assert cache_manager.redis_instance == mock_redis_instance
    mock_redis_from_url.assert_called_once_with("redis://localhost:6379/0")


@patch("paperless.db_cache.redis.from_url")
@patch("paperless.db_cache.settings")
@patch("paperless.db_cache._cache_key_prefix")
def test_invalidate_cache(mock_cache_key_prefix, mock_settings, mock_redis_from_url):
    mock_settings.INSTALLED_APPS = ["cachalot"]
    mock_settings.CACHALOT_REDIS_URL = "redis://localhost:6379/0"
    mock_cache_key_prefix.return_value = "pngx_cachalot_"
    mock_redis_instance = MagicMock()
    mock_redis_instance.scan_iter.return_value = ["key1", "key2"]
    mock_redis_from_url.return_value = mock_redis_instance

    cache_manager = CacheManager()
    deleted_keys = cache_manager.invalidate_cache()

    assert deleted_keys == 2
    mock_redis_instance.delete.assert_any_call("key1")
    mock_redis_instance.delete.assert_any_call("key2")
