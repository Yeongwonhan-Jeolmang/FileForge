"""
metadata_cache.py — Cache for file metadata to avoid redundant operations.
"""

from __future__ import annotations
import time
import os
from typing import Any, Optional
from functools import lru_cache


class MetadataCache:
    """Time-based cache for file metadata."""

    def __init__(self, ttl_seconds: int = 300):
        self._cache = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any):
        """Set cached value with current timestamp."""
        self._cache[key] = (value, time.time())

    def clear(self):
        """Clear all cached data."""
        self._cache.clear()

    def cleanup(self):
        """Remove expired entries."""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp >= self._ttl
        ]
        for key in expired_keys:
            del self._cache[key]


# Global cache instances
_file_info_cache = MetadataCache(ttl_seconds=600)  # 10 minutes
_hash_cache = MetadataCache(ttl_seconds=3600)      # 1 hour
_entropy_cache = MetadataCache(ttl_seconds=1800)   # 30 minutes


def cached_file_info(func):
    """Decorator to cache file info results."""
    def wrapper(*args, **kwargs):
        # Create cache key from function name and arguments
        key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
        cached = _file_info_cache.get(key)
        if cached is not None:
            return cached

        result = func(*args, **kwargs)
        _file_info_cache.set(key, result)
        return result
    return wrapper


def cached_hash(func):
    """Decorator to cache hash results."""
    def wrapper(*args, **kwargs):
        # Create cache key from file path and hash type
        if args and len(args) > 0:
            file_path = args[0]
            hash_type = kwargs.get('hash_type', 'sha256')
            key = f"hash:{hash_type}:{file_path}"
            cached = _hash_cache.get(key)
            if cached is not None:
                return cached

        result = func(*args, **kwargs)

        # Cache the result
        if args and len(args) > 0:
            file_path = args[0]
            hash_type = kwargs.get('hash_type', 'sha256')
            key = f"hash:{hash_type}:{file_path}"
            _hash_cache.set(key, result)

        return result
    return wrapper


def cached_entropy(func):
    """Decorator to cache entropy results."""
    def wrapper(*args, **kwargs):
        if args and len(args) > 0:
            file_path = args[0]
            key = f"entropy:{file_path}"
            cached = _entropy_cache.get(key)
            if cached is not None:
                return cached

        result = func(*args, **kwargs)

        # Cache the result
        if args and len(args) > 0:
            file_path = args[0]
            key = f"entropy:{file_path}"
            _entropy_cache.set(key, result)

        return result
    return wrapper


def clear_all_caches():
    """Clear all metadata caches."""
    _file_info_cache.clear()
    _hash_cache.clear()
    _entropy_cache.clear()


def cleanup_expired_cache():
    """Clean up expired entries from all caches."""
    _file_info_cache.cleanup()
    _hash_cache.cleanup()
    _entropy_cache.cleanup()