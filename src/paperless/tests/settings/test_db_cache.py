import os
import time
from unittest.mock import patch

import pytest
from cachalot.settings import cachalot_settings
from django.conf import settings
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from documents.models import Tag
from paperless.db_cache import invalidate_db_cache
from paperless.settings import _parse_cachalot_settings
from paperless.settings import _parse_caches


def test_all_redis_caches_have_same_custom_prefix(monkeypatch) -> None:
    """
    Check that when setting a custom Redis prefix,
    it is set for both the Django default cache and the read cache.
    """
    from paperless import settings

    monkeypatch.setattr(settings, "_REDIS_KEY_PREFIX", "test_a_custom_key_prefix")
    caches = _parse_caches()
    assert caches["read-cache"]["KEY_PREFIX"] == "test_a_custom_key_prefix"
    assert caches["default"]["KEY_PREFIX"] == "test_a_custom_key_prefix"


class TestDbCacheSettings:
    def test_cachalot_default_settings(self) -> None:
        # Cachalot must be installed even if disabled,
        # so the cache can be invalidated anytime
        assert "cachalot" not in settings.INSTALLED_APPS
        cachalot_settings = _parse_cachalot_settings()
        caches = _parse_caches()

        # Default settings
        assert not cachalot_settings["CACHALOT_ENABLED"]
        assert cachalot_settings["CACHALOT_TIMEOUT"] == 3600
        assert caches["read-cache"]["KEY_PREFIX"] == ""
        assert caches["read-cache"]["LOCATION"] == "redis://localhost:6379"

        # Fixed settings
        assert cachalot_settings["CACHALOT_CACHE"] == "read-cache"
        assert (
            cachalot_settings["CACHALOT_QUERY_KEYGEN"]
            == "paperless.db_cache.custom_get_query_cache_key"
        )
        assert (
            cachalot_settings["CACHALOT_TABLE_KEYGEN"]
            == "paperless.db_cache.custom_get_table_cache_key"
        )
        assert cachalot_settings["CACHALOT_FINAL_SQL_CHECK"] is True

    @patch.dict(
        os.environ,
        {
            "PAPERLESS_DB_READ_CACHE_ENABLED": "true",
            "PAPERLESS_READ_CACHE_REDIS_URL": "redis://localhost:6380/7",
            "PAPERLESS_READ_CACHE_TTL": "7200",
        },
    )
    def test_cachalot_custom_settings(self) -> None:
        settings = _parse_cachalot_settings()

        assert settings["CACHALOT_ENABLED"]
        assert settings["CACHALOT_TIMEOUT"] == 7200
        assert settings["CACHALOT_CACHE"] == "read-cache"
        assert (
            settings["CACHALOT_QUERY_KEYGEN"]
            == "paperless.db_cache.custom_get_query_cache_key"
        )
        assert (
            settings["CACHALOT_TABLE_KEYGEN"]
            == "paperless.db_cache.custom_get_table_cache_key"
        )
        assert settings["CACHALOT_FINAL_SQL_CHECK"] is True

    @pytest.mark.parametrize(
        ("env_var_ttl", "expected_cachalot_timeout"),
        [
            # 0 or less will be ignored, and the default TTL will be set
            ("0", 3600),
            ("-1", 3600),
            ("-500000", 3600),
            # Any positive value will be set, for a maximum of one year
            ("1", 1),
            ("7524", 7524),
            ("99999999999999", 31536000),
        ],
    )
    def test_cachalot_ttl_parsing(
        self,
        env_var_ttl: int,
        expected_cachalot_timeout: int,
    ) -> None:
        with patch.dict(os.environ, {"PAPERLESS_READ_CACHE_TTL": f"{env_var_ttl}"}):
            cachalot_timeout = _parse_cachalot_settings()["CACHALOT_TIMEOUT"]
            assert cachalot_timeout == expected_cachalot_timeout


@override_settings(
    CACHALOT_ENABLED=True,
    CACHALOT_TIMEOUT=1,
)
@pytest.mark.django_db(transaction=True)
def test_cache_hit_when_enabled() -> None:
    cachalot_settings.reload()

    assert cachalot_settings.CACHALOT_ENABLED
    assert cachalot_settings.CACHALOT_TIMEOUT == 1
    assert settings.CACHALOT_TIMEOUT == 1

    # Read a table to populate the cache
    list(list(Tag.objects.values_list("id", flat=True)))

    # Invalidate the cache then read the database, there should be DB hit
    invalidate_db_cache()
    with CaptureQueriesContext(connection) as ctx:
        list(list(Tag.objects.values_list("id", flat=True)))
    assert len(ctx)

    # Doing the same request again should hit the cache, not the DB
    with CaptureQueriesContext(connection) as ctx:
        list(list(Tag.objects.values_list("id", flat=True)))
    assert not len(ctx)

    # Wait the end of TTL
    # Redis expire accuracy should be between 0 and 1 ms
    time.sleep(1.002)

    # Read the DB again. The DB should be hit because the cache has expired
    with CaptureQueriesContext(connection) as ctx:
        list(list(Tag.objects.values_list("id", flat=True)))
    assert len(ctx)

    # Invalidate the cache at the end of test
    invalidate_db_cache()


@pytest.mark.django_db(transaction=True)
def test_cache_is_disabled_by_default() -> None:
    cachalot_settings.reload()
    # Invalidate the cache just in case
    invalidate_db_cache()

    # Read the table multiple times: the DB should always be hit without cache
    for _ in range(3):
        with CaptureQueriesContext(connection) as ctx:
            list(list(Tag.objects.values_list("id", flat=True)))
        assert len(ctx)

    # Invalidate the cache at the end of test
    invalidate_db_cache()
