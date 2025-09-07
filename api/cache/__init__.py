"""
Caching system for the Pulse API.
"""

from .redis_cache import (
    setup_cache,
    get_cache_client,
    CacheClient,
    cache_result,
    invalidate_cache,
    CacheMiddleware
)
from .memory_cache import (
    MemoryCache,
    get_memory_cache
)
from .strategies import (
    CacheStrategy,
    TTLCacheStrategy,
    LRUCacheStrategy,
    AdaptiveCacheStrategy
)

__all__ = [
    "setup_cache",
    "get_cache_client", 
    "CacheClient",
    "cache_result",
    "invalidate_cache",
    "CacheMiddleware",
    "MemoryCache",
    "get_memory_cache",
    "CacheStrategy",
    "TTLCacheStrategy",
    "LRUCacheStrategy", 
    "AdaptiveCacheStrategy",
]