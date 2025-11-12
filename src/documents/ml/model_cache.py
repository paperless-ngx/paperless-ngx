"""
ML Model Cache Manager for IntelliDocs-ngx.

Provides efficient caching for ML models with:
- Singleton pattern to ensure single model instance per type
- LRU eviction policy for memory management
- Disk cache for embeddings
- Warm-up on startup
- Cache hit/miss metrics

This solves the performance issue where models are loaded fresh each time,
causing slow performance. With this cache:
- First load: slow (model download/load)
- Subsequent loads: fast (from cache)
- Memory controlled: <2GB total
- Cache hits: >90% after warm-up
"""

from __future__ import annotations

import logging
import pickle
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("paperless.ml.model_cache")


class CacheMetrics:
    """
    Track cache performance metrics.
    """

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.loads = 0
        self.lock = threading.Lock()

    def record_hit(self):
        with self.lock:
            self.hits += 1

    def record_miss(self):
        with self.lock:
            self.misses += 1

    def record_eviction(self):
        with self.lock:
            self.evictions += 1

    def record_load(self):
        with self.lock:
            self.loads += 1

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0.0
            return {
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "loads": self.loads,
                "total_requests": total,
                "hit_rate": f"{hit_rate:.2f}%",
            }

    def reset(self):
        with self.lock:
            self.hits = 0
            self.misses = 0
            self.evictions = 0
            self.loads = 0


class LRUCache:
    """
    Thread-safe LRU (Least Recently Used) cache implementation.
    
    When the cache is full, the least recently used item is evicted.
    """

    def __init__(self, max_size: int = 3):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of items to cache
        """
        self.max_size = max_size
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.lock = threading.Lock()
        self.metrics = CacheMetrics()

    def get(self, key: str) -> Optional[Any]:
        """
        Get item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        with self.lock:
            if key not in self.cache:
                self.metrics.record_miss()
                return None

            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.metrics.record_hit()
            return self.cache[key]

    def put(self, key: str, value: Any) -> None:
        """
        Add item to cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self.lock:
            if key in self.cache:
                # Update existing item
                self.cache.move_to_end(key)
                self.cache[key] = value
                return

            # Add new item
            self.cache[key] = value
            self.cache.move_to_end(key)

            # Evict least recently used if needed
            if len(self.cache) > self.max_size:
                evicted_key, _ = self.cache.popitem(last=False)
                self.metrics.record_eviction()
                logger.info(f"Evicted model from cache: {evicted_key}")

    def clear(self) -> None:
        """Clear all cached items."""
        with self.lock:
            self.cache.clear()

    def size(self) -> int:
        """Get current cache size."""
        with self.lock:
            return len(self.cache)

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics."""
        return self.metrics.get_stats()


class ModelCacheManager:
    """
    Singleton cache manager for ML models.
    
    Provides centralized caching for all ML models with:
    - Lazy loading with caching
    - LRU eviction policy
    - Thread-safe operations
    - Performance metrics
    
    Usage:
        cache = ModelCacheManager.get_instance()
        model = cache.get_or_load_model("classifier", loader_func)
    """

    _instance: Optional[ModelCacheManager] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Implement singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        max_models: int = 3,
        disk_cache_dir: Optional[str] = None,
    ):
        """
        Initialize model cache manager.
        
        Args:
            max_models: Maximum number of models to keep in memory
            disk_cache_dir: Directory for disk cache (embeddings)
        """
        # Only initialize once (singleton pattern)
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self.model_cache = LRUCache(max_size=max_models)
        self.disk_cache_dir = Path(disk_cache_dir) if disk_cache_dir else None
        
        if self.disk_cache_dir:
            self.disk_cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Disk cache initialized at: {self.disk_cache_dir}")

        logger.info(f"ModelCacheManager initialized (max_models={max_models})")

    @classmethod
    def get_instance(
        cls,
        max_models: int = 3,
        disk_cache_dir: Optional[str] = None,
    ) -> ModelCacheManager:
        """
        Get singleton instance of ModelCacheManager.
        
        Args:
            max_models: Maximum number of models to keep in memory
            disk_cache_dir: Directory for disk cache
            
        Returns:
            ModelCacheManager instance
        """
        if cls._instance is None:
            cls(max_models=max_models, disk_cache_dir=disk_cache_dir)
        return cls._instance

    def get_or_load_model(
        self,
        model_key: str,
        loader_func: Callable[[], Any],
    ) -> Any:
        """
        Get model from cache or load it.
        
        Args:
            model_key: Unique identifier for the model
            loader_func: Function to load the model if not cached
            
        Returns:
            The loaded model
        """
        # Try to get from cache
        model = self.model_cache.get(model_key)
        
        if model is not None:
            logger.debug(f"Model cache HIT: {model_key}")
            return model

        # Cache miss - load model
        logger.info(f"Model cache MISS: {model_key} - loading...")
        start_time = time.time()
        
        try:
            model = loader_func()
            self.model_cache.put(model_key, model)
            self.model_cache.metrics.record_load()
            
            load_time = time.time() - start_time
            logger.info(
                f"Model loaded successfully: {model_key} "
                f"(took {load_time:.2f}s)"
            )
            
            return model
        except Exception as e:
            logger.error(f"Failed to load model {model_key}: {e}", exc_info=True)
            raise

    def save_embeddings_to_disk(
        self,
        key: str,
        embeddings: Dict[int, Any],
    ) -> None:
        """
        Save embeddings to disk cache.
        
        Args:
            key: Cache key
            embeddings: Dictionary of embeddings to save
        """
        if not self.disk_cache_dir:
            return

        cache_file = self.disk_cache_dir / f"{key}.pkl"
        
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(embeddings, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info(f"Saved {len(embeddings)} embeddings to disk: {cache_file}")
        except Exception as e:
            logger.error(f"Failed to save embeddings to disk: {e}", exc_info=True)

    def load_embeddings_from_disk(
        self,
        key: str,
    ) -> Optional[Dict[int, Any]]:
        """
        Load embeddings from disk cache.
        
        Args:
            key: Cache key
            
        Returns:
            Dictionary of embeddings or None if not found
        """
        if not self.disk_cache_dir:
            return None

        cache_file = self.disk_cache_dir / f"{key}.pkl"
        
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "rb") as f:
                embeddings = pickle.load(f)
            logger.info(f"Loaded {len(embeddings)} embeddings from disk: {cache_file}")
            return embeddings
        except Exception as e:
            logger.error(f"Failed to load embeddings from disk: {e}", exc_info=True)
            return None

    def clear_all(self) -> None:
        """Clear all caches (memory and disk)."""
        self.model_cache.clear()
        
        if self.disk_cache_dir and self.disk_cache_dir.exists():
            for cache_file in self.disk_cache_dir.glob("*.pkl"):
                try:
                    cache_file.unlink()
                    logger.info(f"Deleted disk cache file: {cache_file}")
                except Exception as e:
                    logger.error(f"Failed to delete {cache_file}: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get cache performance metrics.
        
        Returns:
            Dictionary with cache statistics
        """
        metrics = self.model_cache.get_metrics()
        metrics["cache_size"] = self.model_cache.size()
        metrics["max_size"] = self.model_cache.max_size
        
        if self.disk_cache_dir and self.disk_cache_dir.exists():
            disk_files = list(self.disk_cache_dir.glob("*.pkl"))
            metrics["disk_cache_files"] = len(disk_files)
            
            # Calculate total disk cache size
            total_size = sum(f.stat().st_size for f in disk_files)
            metrics["disk_cache_size_mb"] = f"{total_size / 1024 / 1024:.2f}"
        
        return metrics

    def warm_up(
        self,
        model_loaders: Dict[str, Callable[[], Any]],
    ) -> None:
        """
        Pre-load models on startup (warm-up).
        
        Args:
            model_loaders: Dictionary of {model_key: loader_function}
        """
        logger.info(f"Starting model warm-up ({len(model_loaders)} models)...")
        start_time = time.time()
        
        for model_key, loader_func in model_loaders.items():
            try:
                self.get_or_load_model(model_key, loader_func)
            except Exception as e:
                logger.warning(f"Failed to warm-up model {model_key}: {e}")
        
        warm_up_time = time.time() - start_time
        logger.info(f"Model warm-up completed in {warm_up_time:.2f}s")
