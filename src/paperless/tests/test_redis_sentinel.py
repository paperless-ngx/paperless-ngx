"""
Tests for Redis Sentinel configuration and functionality.
"""

import os
from unittest.mock import Mock
from unittest.mock import patch

from django.test import TestCase
from django.test import override_settings

from paperless.settings import _get_celery_broker_config
from paperless.settings import _get_channel_layers_config
from paperless.settings import _get_redis_connection
from paperless.settings import _parse_redis_sentinel_config
from paperless.settings import _parse_redis_url


class RedisSentinelTestMixin:
    """Mixin providing common cleanup for Redis Sentinel tests."""

    def _cleanup_sentinel_env_vars(self):
        """Clean up Redis Sentinel environment variables."""
        sentinel_vars = [
            "PAPERLESS_REDIS_SENTINEL_HOSTS",
            "PAPERLESS_REDIS_SENTINEL_SERVICE_NAME",
            "PAPERLESS_REDIS_SENTINEL_PASSWORD",
            "PAPERLESS_REDIS_SENTINEL_USERNAME",
            "PAPERLESS_REDIS_SENTINEL_DB",
            "PAPERLESS_REDIS_PASSWORD",
            "PAPERLESS_REDIS",
        ]
        for var in sentinel_vars:
            if var in os.environ:
                del os.environ[var]

    def tearDown(self):  # NOSONAR
        """Clean up environment variables after each test."""
        self._cleanup_sentinel_env_vars()
        super().tearDown()


class RedisSentinelConfigTest(RedisSentinelTestMixin, TestCase):
    """Test Redis Sentinel configuration parsing."""

    def test_no_sentinel_config(self):
        """Test that None is returned when no Sentinel config is present."""
        config = _parse_redis_sentinel_config()
        self.assertIsNone(config)

    def test_basic_sentinel_config(self):
        """Test basic Sentinel configuration parsing."""
        os.environ["PAPERLESS_REDIS_SENTINEL_HOSTS"] = "sentinel1:26379,sentinel2:26379"

        config = _parse_redis_sentinel_config()

        expected = {
            "hosts": [("sentinel1", 26379), ("sentinel2", 26379)],
            "service_name": "mymaster",  # default
            "password": None,
            "db": 0,  # default
            "username": None,
        }
        self.assertEqual(config, expected)

    def test_full_sentinel_config(self):
        """Test Sentinel configuration with all options."""
        os.environ.update(
            {
                "PAPERLESS_REDIS_SENTINEL_HOSTS": "s1:26379,s2:26380,s3:26381",
                "PAPERLESS_REDIS_SENTINEL_SERVICE_NAME": "myredis",
                "PAPERLESS_REDIS_SENTINEL_PASSWORD": "sentinel_pass",  # NOSONAR
                "PAPERLESS_REDIS_SENTINEL_USERNAME": "redis_user",
                "PAPERLESS_REDIS_SENTINEL_DB": "2",
            },
        )

        config = _parse_redis_sentinel_config()

        expected = {
            "hosts": [("s1", 26379), ("s2", 26380), ("s3", 26381)],
            "service_name": "myredis",
            "password": "sentinel_pass",  # NOSONAR
            "db": 2,
            "username": "redis_user",
        }
        self.assertEqual(config, expected)

    def test_sentinel_hosts_without_ports(self):
        """Test Sentinel hosts without explicit ports use default."""
        os.environ["PAPERLESS_REDIS_SENTINEL_HOSTS"] = (
            "sentinel1,sentinel2:26380,sentinel3"
        )

        config = _parse_redis_sentinel_config()

        expected_hosts = [
            ("sentinel1", 26379),
            ("sentinel2", 26380),
            ("sentinel3", 26379),
        ]
        self.assertEqual(config["hosts"], expected_hosts)

    def test_sentinel_hosts_with_spaces(self):
        """Test Sentinel hosts parsing handles spaces correctly."""
        os.environ["PAPERLESS_REDIS_SENTINEL_HOSTS"] = (
            " sentinel1:26379 , sentinel2:26380 "
        )

        config = _parse_redis_sentinel_config()

        expected_hosts = [("sentinel1", 26379), ("sentinel2", 26380)]
        self.assertEqual(config["hosts"], expected_hosts)


class RedisUrlParsingTest(RedisSentinelTestMixin, TestCase):
    """Test Redis URL parsing with Sentinel support."""

    def test_parse_redis_url_with_sentinel(self):
        """Test Redis URL parsing when Sentinel is configured."""
        os.environ.update(
            {
                "PAPERLESS_REDIS_SENTINEL_HOSTS": "s1:26379,s2:26379",
                "PAPERLESS_REDIS_SENTINEL_SERVICE_NAME": "mymaster",
                "PAPERLESS_REDIS_SENTINEL_DB": "1",
            },
        )

        celery_url, channels_url = _parse_redis_url(None)

        self.assertEqual(celery_url, "sentinel://s1:26379,s2:26379/mymaster")
        self.assertEqual(channels_url, "redis://s1:26379/1")

    def test_parse_redis_url_without_sentinel(self):
        """Test Redis URL parsing fallback when no Sentinel config."""
        celery_url, channels_url = _parse_redis_url("redis://localhost:6379/2")

        self.assertEqual(celery_url, "redis://localhost:6379/2")
        self.assertEqual(channels_url, "redis://localhost:6379/2")

    def test_parse_redis_url_default_fallback(self):
        """Test Redis URL parsing with default fallback."""
        celery_url, channels_url = _parse_redis_url(None)

        self.assertEqual(celery_url, "redis://localhost:6379")
        self.assertEqual(channels_url, "redis://localhost:6379")

    def test_parse_redis_url_unix_socket(self):
        """Test Redis URL parsing with Unix socket."""
        celery_url, channels_url = _parse_redis_url("unix:///tmp/redis.sock")

        self.assertEqual(celery_url, "redis+socket:///tmp/redis.sock")
        self.assertEqual(channels_url, "unix:///tmp/redis.sock")


class CeleryBrokerConfigTest(RedisSentinelTestMixin, TestCase):
    """Test Celery broker configuration with Sentinel."""

    def test_celery_config_with_sentinel(self):
        """Test Celery broker configuration with Sentinel."""
        os.environ.update(
            {
                "PAPERLESS_REDIS_SENTINEL_HOSTS": "s1:26379,s2:26379",
                "PAPERLESS_REDIS_SENTINEL_SERVICE_NAME": "mymaster",
                "PAPERLESS_REDIS_SENTINEL_PASSWORD": "sentinel_pass",  # NOSONAR
                "PAPERLESS_REDIS_PASSWORD": "redis_pass",  # NOSONAR
                "PAPERLESS_REDIS_SENTINEL_USERNAME": "redis_user",
                "PAPERLESS_REDIS_SENTINEL_DB": "1",
            },
        )

        broker_url, transport_options = _get_celery_broker_config()

        self.assertEqual(broker_url, "redis://sentinel")
        expected_transport = {
            "master_name": "mymaster",
            "sentinels": [("s1", 26379), ("s2", 26379)],
            "global_keyprefix": "",  # Default empty prefix
            "sentinel_kwargs": {"password": "sentinel_pass"},  # NOSONAR
            "password": "redis_pass",  # NOSONAR
            "username": "redis_user",
            "db": 1,
        }
        self.assertEqual(transport_options, expected_transport)

    @override_settings(_REDIS_KEY_PREFIX="test_")
    def test_celery_config_with_prefix(self):
        """Test Celery broker configuration includes prefix."""
        os.environ.update(
            {
                "PAPERLESS_REDIS_SENTINEL_HOSTS": "s1:26379",
                "PAPERLESS_REDIS_SENTINEL_SERVICE_NAME": "mymaster",
            },
        )

        with patch("paperless.settings._REDIS_KEY_PREFIX", "test_"):
            _broker_url, transport_options = _get_celery_broker_config()

        self.assertEqual(transport_options["global_keyprefix"], "test_")

    def test_celery_config_without_sentinel(self):
        """Test Celery broker configuration without Sentinel."""
        with patch("paperless.settings._CELERY_REDIS_URL", "redis://localhost:6379"):
            broker_url, transport_options = _get_celery_broker_config()

        self.assertEqual(broker_url, "redis://localhost:6379")
        self.assertEqual(transport_options, {"global_keyprefix": ""})


class ChannelLayersConfigTest(RedisSentinelTestMixin, TestCase):
    """Test Django Channels configuration with Sentinel."""

    def test_channel_layers_with_sentinel(self):
        """Test channel layers configuration with Sentinel."""
        os.environ.update(
            {
                "PAPERLESS_REDIS_SENTINEL_HOSTS": "s1:26379,s2:26379",
                "PAPERLESS_REDIS_SENTINEL_SERVICE_NAME": "mymaster",
                "PAPERLESS_REDIS_SENTINEL_PASSWORD": "sentinel_pass",  # NOSONAR
                "PAPERLESS_REDIS_PASSWORD": "redis_pass",  # NOSONAR
                "PAPERLESS_REDIS_SENTINEL_USERNAME": "redis_user",
                "PAPERLESS_REDIS_SENTINEL_DB": "2",
            },
        )

        config = _get_channel_layers_config()

        self.assertEqual(
            config["default"]["BACKEND"],
            "channels_redis.pubsub.RedisPubSubChannelLayer",
        )

        expected_sentinel = {
            "sentinels": [("s1", 26379), ("s2", 26379)],
            "service_name": "mymaster",
            "sentinel_kwargs": {"password": "sentinel_pass"},  # NOSONAR
        }
        self.assertEqual(config["default"]["CONFIG"]["sentinel"], expected_sentinel)

        expected_connection = {
            "db": 2,
            "password": "redis_pass",  # NOSONAR
            "username": "redis_user",
        }
        self.assertEqual(
            config["default"]["CONFIG"]["connection_kwargs"],
            expected_connection,
        )

    def test_channel_layers_without_sentinel(self):
        """Test channel layers configuration without Sentinel."""
        with patch("paperless.settings._CHANNELS_REDIS_URL", "redis://localhost:6379"):
            config = _get_channel_layers_config()

        self.assertEqual(
            config["default"]["BACKEND"],
            "channels_redis.pubsub.RedisPubSubChannelLayer",
        )
        self.assertEqual(
            config["default"]["CONFIG"]["hosts"],
            ["redis://localhost:6379"],
        )
        self.assertNotIn("sentinel", config["default"]["CONFIG"])


class RedisConnectionTest(RedisSentinelTestMixin, TestCase):
    """Test Redis connection helper function."""

    @patch("redis.sentinel.Sentinel")
    def test_get_redis_connection_with_sentinel(self, mock_sentinel_class):
        """Test getting Redis connection via Sentinel."""
        os.environ.update(
            {
                "PAPERLESS_REDIS_SENTINEL_HOSTS": "s1:26379,s2:26379",
                "PAPERLESS_REDIS_SENTINEL_SERVICE_NAME": "mymaster",
                "PAPERLESS_REDIS_SENTINEL_PASSWORD": "sentinel_pass",  # NOSONAR
                "PAPERLESS_REDIS_PASSWORD": "redis_pass",  # NOSONAR
                "PAPERLESS_REDIS_SENTINEL_USERNAME": "redis_user",
                "PAPERLESS_REDIS_SENTINEL_DB": "1",
            },
        )

        mock_sentinel = Mock()
        mock_sentinel_class.return_value = mock_sentinel
        mock_master = Mock()
        mock_sentinel.master_for.return_value = mock_master

        connection = _get_redis_connection()

        # Verify Sentinel was created with correct parameters
        mock_sentinel_class.assert_called_once_with(
            [("s1", 26379), ("s2", 26379)],
            password="sentinel_pass",  # NOSONAR
        )

        # Verify master_for was called with correct parameters
        mock_sentinel.master_for.assert_called_once_with(
            "mymaster",
            username="redis_user",
            password="redis_pass",  # NOSONAR
            db=1,
        )

        self.assertEqual(connection, mock_master)

    @patch("redis.Redis")
    def test_get_redis_connection_without_sentinel(self, mock_redis_class):
        """Test getting Redis connection without Sentinel."""
        os.environ["PAPERLESS_REDIS"] = "redis://localhost:6379/2"

        mock_redis = Mock()
        mock_redis_class.from_url.return_value = mock_redis

        connection = _get_redis_connection()

        mock_redis_class.from_url.assert_called_once_with("redis://localhost:6379/2")
        self.assertEqual(connection, mock_redis)

    @patch("redis.Redis")
    def test_get_redis_connection_default_fallback(self, mock_redis_class):
        """Test getting Redis connection with default fallback."""
        mock_redis = Mock()
        mock_redis_class.from_url.return_value = mock_redis

        connection = _get_redis_connection()

        mock_redis_class.from_url.assert_called_once_with("redis://localhost:6379")
        self.assertEqual(connection, mock_redis)
