"""
metadata_cache.py — Cache for file metadata to avoid redundant operations.

Entries are keyed on (path, size, mtime) so a cached value is invalidated
automatically as soon as the file changes on disk, and every cache is a
bounded LRU so long sessions (e.g. duplicate scans of huge folders) can't
grow memory without limit.
"""

from __future__ import annotations
import time
import os
import threading
from collections import OrderedDict
from functools import wraps
from typing import Any, Optional


class MetadataCache:
    """Thread-safe, size-bounded, time-based LRU cache."""

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 2048):
        self._cache: OrderedDict = OrderedDict()
        self._ttl = ttl_seconds
        self._max = max_entries
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            value, timestamp = entry
            if time.time() - timestamp >= self._ttl:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any):
        """Set cached value with current timestamp."""
        with self._lock:
            self._cache[key] = (value, time.time())
            self._cache.move_to_end(key)
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)

    def clear(self):
        """Clear all cached data."""
        with self._lock:
            self._cache.clear()

    def cleanup(self):
        """Remove expired entries."""
        current_time = time.time()
        with self._lock:
            expired_keys = [
                key for key, (_, timestamp) in self._cache.items()
                if current_time - timestamp >= self._ttl
            ]
            for key in expired_keys:
                del self._cache[key]

    def __len__(self) -> int:
        return len(self._cache)


# Global cache instances
_file_info_cache = MetadataCache(ttl_seconds=600, max_entries=256)     # 10 minutes
_hash_cache = MetadataCache(ttl_seconds=3600, max_entries=20_000)      # 1 hour
_entropy_cache = MetadataCache(ttl_seconds=1800, max_entries=1024)     # 30 minutes


def file_signature(path: str) -> str:
    """
    Identity of a file's current contents: path + size + mtime (ns).
    Any write to the file changes the signature, invalidating cache entries.
    """
    try:
        st = os.stat(path)
        return f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}"
    except OSError:
        return f"{path}|?"


def cached_file_info(func):
    """Decorator to cache file info results."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        sig = file_signature(args[0]) if args else ""
        key = f"{func.__name__}:{sig}:{args[1:]!r}:{sorted(kwargs.items())!r}"
        cached = _file_info_cache.get(key)
        if cached is not None:
            return cached

        result = func(*args, **kwargs)
        _file_info_cache.set(key, result)
        return result
    return wrapper


def cached_hash(func):
    """Decorator to cache hash results."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not args:
            return func(*args, **kwargs)
        hash_type = kwargs.get('hash_type', args[1] if len(args) > 1 else 'sha256')
        key = f"hash:{hash_type}:{file_signature(args[0])}"
        cached = _hash_cache.get(key)
        if cached is not None:
            return cached

        result = func(*args, **kwargs)
        _hash_cache.set(key, result)
        return result
    return wrapper


def cached_entropy(func):
    """Decorator to cache entropy results."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not args:
            return func(*args, **kwargs)
        sample = kwargs.get('sample_size', args[1] if len(args) > 1 else None)
        key = f"entropy:{sample}:{file_signature(args[0])}"
        cached = _entropy_cache.get(key)
        if cached is not None:
            return cached

        result = func(*args, **kwargs)
        _entropy_cache.set(key, result)
        return result
    return wrapper


def get_cached_hashes(path: str) -> dict[str, str]:
    """Return every hash already computed for the current contents of `path`."""
    sig = file_signature(path)
    found = {}
    for algo in ("md5", "sha1", "sha256", "sha512", "blake2"):
        val = _hash_cache.get(f"hash:{algo}:{sig}")
        if val is not None:
            found[algo] = val
    return found


def store_hashes(path: str, hashes: dict[str, str]):
    """Remember freshly computed digests for the current contents of `path`."""
    sig = file_signature(path)
    for algo, digest in hashes.items():
        _hash_cache.set(f"hash:{algo}:{sig}", digest)


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
