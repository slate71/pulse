"""
In-memory caching implementation as fallback.

Provides local caching when Redis is not available or for temporary data.
"""

import time
import threading
from typing import Any, Dict, Optional, Callable
from collections import OrderedDict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with value and metadata."""
    value: Any
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl: Optional[float] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.ttl is None:
            return False
        return time.time() > (self.created_at + self.ttl)
    
    def touch(self):
        """Update access information."""
        self.last_accessed = time.time()
        self.access_count += 1


class MemoryCache:
    """
    Thread-safe in-memory cache with TTL and LRU eviction.
    
    Provides caching when Redis is not available or for temporary data
    that doesn't need to be shared across instances.
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expired_evictions = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self.misses += 1
                return None
            
            if entry.is_expired:
                del self._cache[key]
                self.expired_evictions += 1
                self.misses += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self.hits += 1
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        with self._lock:
            ttl = ttl or self.default_ttl
            
            # Create cache entry
            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                last_accessed=time.time(),
                ttl=ttl
            )
            
            # Remove existing entry if present
            if key in self._cache:
                del self._cache[key]
            
            # Add new entry
            self._cache[key] = entry
            self._cache.move_to_end(key)
            
            # Evict if over capacity
            self._evict_if_needed()
            
            return True
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            
            if entry.is_expired:
                del self._cache[key]
                self.expired_evictions += 1
                return False
            
            return True
    
    def clear(self) -> int:
        """Clear all entries from cache."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count
    
    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)
    
    def _evict_if_needed(self):
        """Evict entries if cache is over capacity."""
        while len(self._cache) > self.max_size:
            # Remove least recently used item
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self.evictions += 1
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count."""
        with self._lock:
            expired_keys = []
            current_time = time.time()
            
            for key, entry in self._cache.items():
                if entry.ttl and current_time > (entry.created_at + entry.ttl):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
            
            self.expired_evictions += len(expired_keys)
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "evictions": self.evictions,
                "expired_evictions": self.expired_evictions,
                "total_requests": total_requests
            }
    
    def get_keys(self) -> list[str]:
        """Get all cache keys."""
        with self._lock:
            return list(self._cache.keys())
    
    def get_entries_info(self, limit: int = 10) -> list[Dict[str, Any]]:
        """Get information about cache entries."""
        with self._lock:
            entries = []
            for key, entry in list(self._cache.items())[:limit]:
                entries.append({
                    "key": key,
                    "size_estimate": len(str(entry.value)),
                    "created_at": entry.created_at,
                    "last_accessed": entry.last_accessed,
                    "access_count": entry.access_count,
                    "ttl": entry.ttl,
                    "is_expired": entry.is_expired
                })
            return entries


# Global memory cache instance
_memory_cache: Optional[MemoryCache] = None
_cache_lock = threading.Lock()


def get_memory_cache() -> MemoryCache:
    """Get or create the global memory cache instance."""
    global _memory_cache
    
    if _memory_cache is None:
        with _cache_lock:
            if _memory_cache is None:
                _memory_cache = MemoryCache()
                logger.info("Memory cache initialized")
    
    return _memory_cache


def setup_memory_cache(max_size: int = 1000, default_ttl: int = 3600) -> MemoryCache:
    """Setup memory cache with custom parameters."""
    global _memory_cache
    
    with _cache_lock:
        _memory_cache = MemoryCache(max_size=max_size, default_ttl=default_ttl)
        logger.info(f"Memory cache setup complete (max_size={max_size}, default_ttl={default_ttl})")
    
    return _memory_cache


def memory_cache_decorator(key_func: Optional[Callable] = None, ttl: int = 3600):
    """
    Decorator to cache function results in memory.
    
    Args:
        key_func: Function to generate cache key from args
        ttl: Time to live in seconds
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            cache = get_memory_cache()
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                import hashlib
                func_name = f"{func.__module__}.{func.__qualname__}"
                arg_hash = hashlib.md5(str((args, kwargs)).encode()).hexdigest()
                cache_key = f"mem_func:{func_name}:{arg_hash}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


class MemoryCacheManager:
    """Manager for periodic memory cache maintenance."""
    
    def __init__(self, cleanup_interval: int = 300):
        self.cleanup_interval = cleanup_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start background cleanup thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._thread.start()
        logger.info("Memory cache cleanup manager started")
    
    def stop(self):
        """Stop background cleanup thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Memory cache cleanup manager stopped")
    
    def _cleanup_loop(self):
        """Background cleanup loop."""
        while self._running:
            try:
                cache = get_memory_cache()
                expired_count = cache.cleanup_expired()
                
                if expired_count > 0:
                    logger.debug(f"Cleaned up {expired_count} expired cache entries")
                
                # Sleep for cleanup interval
                for _ in range(self.cleanup_interval):
                    if not self._running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in cache cleanup loop: {e}")
                time.sleep(60)  # Wait a minute before retrying


# Global cleanup manager
_cleanup_manager: Optional[MemoryCacheManager] = None


def start_memory_cache_cleanup(cleanup_interval: int = 300):
    """Start periodic memory cache cleanup."""
    global _cleanup_manager
    
    if _cleanup_manager is None:
        _cleanup_manager = MemoryCacheManager(cleanup_interval)
    
    _cleanup_manager.start()


def stop_memory_cache_cleanup():
    """Stop periodic memory cache cleanup."""
    global _cleanup_manager
    
    if _cleanup_manager:
        _cleanup_manager.stop()