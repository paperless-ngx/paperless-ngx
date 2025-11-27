"""
Integration tests for Redis Sentinel functionality.
"""

import os
from unittest.mock import Mock, patch
from django.test import TestCase


class RedisSentinelIntegrationTest(TestCase):
    """Integration tests for Redis Sentinel functionality."""

    def tearDown(self):
        """Clean up environment variables after each test."""
        sentinel_vars = [
            "PAPERLESS_REDIS_SENTINEL_HOSTS",
            "PAPERLESS_REDIS_SENTINEL_SERVICE_NAME",
            "PAPERLESS_REDIS_SENTINEL_PASSWORD",
            "PAPERLESS_REDIS_SENTINEL_USERNAME",
            "PAPERLESS_REDIS_SENTINEL_DB",
            "PAPERLESS_REDIS_PASSWORD",
        ]
        for var in sentinel_vars:
            if var in os.environ:
                del os.environ[var]

    def test_settings_import_with_sentinel_config(self):
        """Test that settings can be imported with Sentinel configuration."""
        os.environ.update({
            "PAPERLESS_REDIS_SENTINEL_HOSTS": "s1:26379,s2:26379",
            "PAPERLESS_REDIS_SENTINEL_SERVICE_NAME": "mymaster",
        })
        
        # Re-import settings to pick up the new environment
        import importlib
        import paperless.settings
        importlib.reload(paperless.settings)
        
        # Verify Sentinel config is parsed correctly
        from paperless.settings import _parse_redis_sentinel_config
        config = _parse_redis_sentinel_config()
        
        self.assertIsNotNone(config)
        self.assertEqual(config["service_name"], "mymaster")
        self.assertEqual(len(config["hosts"]), 2)

    def test_settings_import_without_sentinel_config(self):
        """Test that settings can be imported without Sentinel configuration."""
        # Make sure no Sentinel config is set
        from paperless.settings import _parse_redis_sentinel_config
        config = _parse_redis_sentinel_config()
        
        self.assertIsNone(config)

    @patch('redis.Redis.from_url')
    def test_system_status_with_mocked_redis(self, mock_redis):
        """Test that system status works with mocked Redis."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        from paperless.settings import _get_redis_connection
        
        client = _get_redis_connection()
        result = client.ping()
        
        self.assertTrue(result)
        mock_redis.assert_called_once()

    def test_configuration_precedence(self):
        """Test that Sentinel configuration takes precedence over regular Redis URL."""
        os.environ.update({
            "PAPERLESS_REDIS": "redis://localhost:6379/1",
            "PAPERLESS_REDIS_SENTINEL_HOSTS": "s1:26379",
            "PAPERLESS_REDIS_SENTINEL_SERVICE_NAME": "mymaster",
        })
        
        from paperless.settings import _parse_redis_url
        celery_url, channels_url = _parse_redis_url("redis://localhost:6379/1")
        
        # Should use Sentinel configuration, not the regular Redis URL
        self.assertTrue(celery_url.startswith("sentinel://"))
        self.assertIn("s1:26379", celery_url)
        self.assertIn("mymaster", celery_url)

    def test_environment_variable_validation(self):
        """Test validation of environment variable formats."""
        # Test invalid port number
        os.environ["PAPERLESS_REDIS_SENTINEL_HOSTS"] = "sentinel1:invalid_port"
        
        from paperless.settings import _parse_redis_sentinel_config
        
        # Should raise an error for invalid port
        with self.assertRaises(ValueError):
            _parse_redis_sentinel_config()

    def test_db_number_parsing(self):
        """Test that database numbers are parsed correctly."""
        os.environ.update({
            "PAPERLESS_REDIS_SENTINEL_HOSTS": "s1:26379",
            "PAPERLESS_REDIS_SENTINEL_DB": "5",
        })
        
        from paperless.settings import _parse_redis_sentinel_config
        config = _parse_redis_sentinel_config()
        
        self.assertEqual(config["db"], 5)

    def test_empty_sentinel_hosts(self):
        """Test behavior with empty Sentinel hosts."""
        os.environ["PAPERLESS_REDIS_SENTINEL_HOSTS"] = ""
        
        from paperless.settings import _parse_redis_sentinel_config
        config = _parse_redis_sentinel_config()
        
        self.assertIsNone(config)

    def test_malformed_sentinel_hosts(self):
        """Test behavior with malformed Sentinel hosts."""
        os.environ["PAPERLESS_REDIS_SENTINEL_HOSTS"] = "s1:26379,,s2:26379"
        
        from paperless.settings import _parse_redis_sentinel_config
        config = _parse_redis_sentinel_config()
        
        # Should handle empty entries gracefully
        self.assertEqual(len(config["hosts"]), 2)
        self.assertEqual(config["hosts"][0], ("s1", 26379))
        self.assertEqual(config["hosts"][1], ("s2", 26379))