"""
Tests for ML model caching functionality.
"""

import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase

from documents.ml.model_cache import CacheMetrics
from documents.ml.model_cache import LRUCache
from documents.ml.model_cache import ModelCacheManager


class TestCacheMetrics(TestCase):
    """Test cache metrics tracking."""

    def test_record_hit(self):
        """Test recording cache hits."""
        metrics = CacheMetrics()
        self.assertEqual(metrics.hits, 0)

        metrics.record_hit()
        self.assertEqual(metrics.hits, 1)

        metrics.record_hit()
        self.assertEqual(metrics.hits, 2)

    def test_record_miss(self):
        """Test recording cache misses."""
        metrics = CacheMetrics()
        self.assertEqual(metrics.misses, 0)

        metrics.record_miss()
        self.assertEqual(metrics.misses, 1)

    def test_get_stats(self):
        """Test getting cache statistics."""
        metrics = CacheMetrics()

        # Initial stats
        stats = metrics.get_stats()
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)
        self.assertEqual(stats["hit_rate"], "0.00%")

        # After some hits and misses
        metrics.record_hit()
        metrics.record_hit()
        metrics.record_hit()
        metrics.record_miss()

        stats = metrics.get_stats()
        self.assertEqual(stats["hits"], 3)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["total_requests"], 4)
        self.assertEqual(stats["hit_rate"], "75.00%")

    def test_reset(self):
        """Test resetting metrics."""
        metrics = CacheMetrics()
        metrics.record_hit()
        metrics.record_miss()

        metrics.reset()

        stats = metrics.get_stats()
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)


class TestLRUCache(TestCase):
    """Test LRU cache implementation."""

    def test_put_and_get(self):
        """Test basic cache operations."""
        cache = LRUCache(max_size=2)

        cache.put("key1", "value1")
        cache.put("key2", "value2")

        self.assertEqual(cache.get("key1"), "value1")
        self.assertEqual(cache.get("key2"), "value2")

    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = LRUCache(max_size=2)

        result = cache.get("nonexistent")
        self.assertIsNone(result)

    def test_lru_eviction(self):
        """Test LRU eviction policy."""
        cache = LRUCache(max_size=2)

        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")  # Should evict key1

        self.assertIsNone(cache.get("key1"))  # Evicted
        self.assertEqual(cache.get("key2"), "value2")
        self.assertEqual(cache.get("key3"), "value3")

    def test_lru_update_access_order(self):
        """Test that accessing an item updates its position."""
        cache = LRUCache(max_size=2)

        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.get("key1")  # Access key1, making it most recent
        cache.put("key3", "value3")  # Should evict key2, not key1

        self.assertEqual(cache.get("key1"), "value1")
        self.assertIsNone(cache.get("key2"))  # Evicted
        self.assertEqual(cache.get("key3"), "value3")

    def test_cache_size(self):
        """Test cache size tracking."""
        cache = LRUCache(max_size=3)

        self.assertEqual(cache.size(), 0)

        cache.put("key1", "value1")
        self.assertEqual(cache.size(), 1)

        cache.put("key2", "value2")
        self.assertEqual(cache.size(), 2)

    def test_clear(self):
        """Test clearing cache."""
        cache = LRUCache(max_size=2)

        cache.put("key1", "value1")
        cache.put("key2", "value2")

        cache.clear()

        self.assertEqual(cache.size(), 0)
        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))


class TestModelCacheManager(TestCase):
    """Test model cache manager."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset singleton instance for each test
        ModelCacheManager._instance = None

    def test_singleton_pattern(self):
        """Test that ModelCacheManager is a singleton."""
        instance1 = ModelCacheManager.get_instance()
        instance2 = ModelCacheManager.get_instance()

        self.assertIs(instance1, instance2)

    def test_get_or_load_model_first_time(self):
        """Test loading a model for the first time (cache miss)."""
        cache_manager = ModelCacheManager.get_instance()

        # Mock loader function
        mock_model = mock.Mock()
        loader = mock.Mock(return_value=mock_model)

        # Load model
        result = cache_manager.get_or_load_model("test_model", loader)

        # Verify loader was called
        loader.assert_called_once()
        self.assertIs(result, mock_model)

    def test_get_or_load_model_cached(self):
        """Test loading a model from cache (cache hit)."""
        cache_manager = ModelCacheManager.get_instance()

        # Mock loader function
        mock_model = mock.Mock()
        loader = mock.Mock(return_value=mock_model)

        # Load model first time
        cache_manager.get_or_load_model("test_model", loader)

        # Load model second time (should be cached)
        result = cache_manager.get_or_load_model("test_model", loader)

        # Verify loader was only called once
        loader.assert_called_once()
        self.assertIs(result, mock_model)

    def test_disk_cache_embeddings(self):
        """Test saving and loading embeddings to/from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_manager = ModelCacheManager.get_instance(
                disk_cache_dir=tmpdir,
            )

            # Create test embeddings
            embeddings = {
                1: "embedding1",
                2: "embedding2",
                3: "embedding3",
            }

            # Save to disk
            cache_manager.save_embeddings_to_disk("test_embeddings", embeddings)

            # Verify file was created
            cache_file = Path(tmpdir) / "test_embeddings.pkl"
            self.assertTrue(cache_file.exists())

            # Load from disk
            loaded = cache_manager.load_embeddings_from_disk("test_embeddings")

            # Verify embeddings match
            self.assertEqual(loaded, embeddings)

    def test_get_metrics(self):
        """Test getting cache metrics."""
        cache_manager = ModelCacheManager.get_instance()

        # Mock loader
        loader = mock.Mock(return_value=mock.Mock())

        # Generate some cache activity
        cache_manager.get_or_load_model("model1", loader)
        cache_manager.get_or_load_model("model1", loader)  # Cache hit
        cache_manager.get_or_load_model("model2", loader)

        # Get metrics
        metrics = cache_manager.get_metrics()

        # Verify metrics structure
        self.assertIn("hits", metrics)
        self.assertIn("misses", metrics)
        self.assertIn("cache_size", metrics)
        self.assertIn("max_size", metrics)

        # Verify hit/miss counts
        self.assertEqual(metrics["hits"], 1)  # One cache hit
        self.assertEqual(metrics["misses"], 2)  # Two cache misses

    def test_clear_all(self):
        """Test clearing all caches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_manager = ModelCacheManager.get_instance(
                disk_cache_dir=tmpdir,
            )

            # Add some models to cache
            loader = mock.Mock(return_value=mock.Mock())
            cache_manager.get_or_load_model("model1", loader)

            # Add embeddings to disk
            embeddings = {1: "embedding1"}
            cache_manager.save_embeddings_to_disk("test", embeddings)

            # Clear all
            cache_manager.clear_all()

            # Verify memory cache is cleared
            self.assertEqual(cache_manager.model_cache.size(), 0)

            # Verify disk cache is cleared
            cache_file = Path(tmpdir) / "test.pkl"
            self.assertFalse(cache_file.exists())

    def test_warm_up(self):
        """Test model warm-up functionality."""
        cache_manager = ModelCacheManager.get_instance()

        # Create mock loaders
        model1 = mock.Mock()
        model2 = mock.Mock()

        loaders = {
            "model1": mock.Mock(return_value=model1),
            "model2": mock.Mock(return_value=model2),
        }

        # Warm up
        cache_manager.warm_up(loaders)

        # Verify all loaders were called
        for loader in loaders.values():
            loader.assert_called_once()

        # Verify models are cached
        self.assertEqual(cache_manager.model_cache.size(), 2)
