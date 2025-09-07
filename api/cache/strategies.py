"""
Caching strategies and policies.

Provides different caching strategies for various use cases.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CacheStrategy(ABC):
    """Abstract base class for caching strategies."""
    
    @abstractmethod
    async def should_cache(self, key: str, value: Any, context: Dict[str, Any] = None) -> bool:
        """Determine if value should be cached."""
        pass
    
    @abstractmethod
    def get_ttl(self, key: str, value: Any, context: Dict[str, Any] = None) -> int:
        """Get TTL for the cache entry."""
        pass
    
    @abstractmethod
    async def should_refresh(self, key: str, cached_value: Any, age: float, context: Dict[str, Any] = None) -> bool:
        """Determine if cached value should be refreshed."""
        pass


class TTLCacheStrategy(CacheStrategy):
    """
    Simple TTL-based caching strategy.
    
    Caches all values with a fixed or computed TTL.
    """
    
    def __init__(
        self,
        default_ttl: int = 3600,
        ttl_func: Optional[Callable[[str, Any], int]] = None,
        cache_condition: Optional[Callable[[str, Any], bool]] = None
    ):
        self.default_ttl = default_ttl
        self.ttl_func = ttl_func
        self.cache_condition = cache_condition
    
    async def should_cache(self, key: str, value: Any, context: Dict[str, Any] = None) -> bool:
        """Check if value should be cached."""
        if self.cache_condition:
            return self.cache_condition(key, value)
        
        # Don't cache None values by default
        return value is not None
    
    def get_ttl(self, key: str, value: Any, context: Dict[str, Any] = None) -> int:
        """Get TTL for cache entry."""
        if self.ttl_func:
            return self.ttl_func(key, value)
        return self.default_ttl
    
    async def should_refresh(self, key: str, cached_value: Any, age: float, context: Dict[str, Any] = None) -> bool:
        """TTL strategy doesn't do early refresh."""
        return False


class LRUCacheStrategy(CacheStrategy):
    """
    LRU-based caching strategy with size limits.
    
    Maintains a fixed cache size and evicts least recently used items.
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 3600,
        size_func: Optional[Callable[[Any], int]] = None
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.size_func = size_func or self._default_size_func
        self.current_size = 0
        self.access_order: Dict[str, float] = {}
    
    def _default_size_func(self, value: Any) -> int:
        """Default size calculation."""
        try:
            return len(str(value))
        except:
            return 1
    
    async def should_cache(self, key: str, value: Any, context: Dict[str, Any] = None) -> bool:
        """Check if value should be cached based on size constraints."""
        value_size = self.size_func(value)
        
        # Don't cache if value is too large
        if value_size > self.max_size / 2:
            return False
        
        return value is not None
    
    def get_ttl(self, key: str, value: Any, context: Dict[str, Any] = None) -> int:
        """Get TTL for cache entry."""
        return self.default_ttl
    
    async def should_refresh(self, key: str, cached_value: Any, age: float, context: Dict[str, Any] = None) -> bool:
        """LRU strategy doesn't do early refresh."""
        return False
    
    def track_access(self, key: str):
        """Track access for LRU ordering."""
        self.access_order[key] = time.time()
    
    def get_eviction_candidates(self, needed_space: int) -> list[str]:
        """Get keys to evict to make space."""
        candidates = []
        freed_space = 0
        
        # Sort by access time (oldest first)
        sorted_keys = sorted(self.access_order.items(), key=lambda x: x[1])
        
        for key, _ in sorted_keys:
            candidates.append(key)
            freed_space += self.size_func(None)  # Estimate
            
            if freed_space >= needed_space:
                break
        
        return candidates


class AdaptiveCacheStrategy(CacheStrategy):
    """
    Adaptive caching strategy that adjusts TTL based on access patterns.
    
    Uses hit rate, access frequency, and value computation cost to determine
    optimal caching behavior.
    """
    
    def __init__(
        self,
        min_ttl: int = 300,
        max_ttl: int = 7200,
        base_ttl: int = 3600,
        hit_rate_threshold: float = 0.5,
        access_count_threshold: int = 3
    ):
        self.min_ttl = min_ttl
        self.max_ttl = max_ttl
        self.base_ttl = base_ttl
        self.hit_rate_threshold = hit_rate_threshold
        self.access_count_threshold = access_count_threshold
        
        # Track statistics
        self.access_stats: Dict[str, AccessStats] = {}
    
    async def should_cache(self, key: str, value: Any, context: Dict[str, Any] = None) -> bool:
        """Adaptive caching based on access patterns."""
        if value is None:
            return False
        
        # Always cache on first access
        if key not in self.access_stats:
            return True
        
        stats = self.access_stats[key]
        
        # Cache if hit rate is good or access count is high
        if stats.hit_rate >= self.hit_rate_threshold:
            return True
        
        if stats.access_count >= self.access_count_threshold:
            return True
        
        return False
    
    def get_ttl(self, key: str, value: Any, context: Dict[str, Any] = None) -> int:
        """Adaptive TTL based on access patterns."""
        if key not in self.access_stats:
            return self.base_ttl
        
        stats = self.access_stats[key]
        
        # Increase TTL for frequently accessed items with high hit rate
        multiplier = 1.0
        
        if stats.hit_rate > 0.8:
            multiplier *= 1.5
        elif stats.hit_rate > 0.6:
            multiplier *= 1.2
        elif stats.hit_rate < 0.3:
            multiplier *= 0.7
        
        if stats.access_frequency > 1.0:  # More than once per hour
            multiplier *= 1.3
        elif stats.access_frequency < 0.1:  # Less than once per 10 hours
            multiplier *= 0.8
        
        # Get computation cost from context
        if context and 'computation_time' in context:
            comp_time = context['computation_time']
            if comp_time > 1.0:  # Expensive computation
                multiplier *= 1.4
            elif comp_time < 0.1:  # Cheap computation
                multiplier *= 0.9
        
        ttl = int(self.base_ttl * multiplier)
        return max(self.min_ttl, min(self.max_ttl, ttl))
    
    async def should_refresh(self, key: str, cached_value: Any, age: float, context: Dict[str, Any] = None) -> bool:
        """Determine if cached value should be refreshed early."""
        if key not in self.access_stats:
            return False
        
        stats = self.access_stats[key]
        ttl = self.get_ttl(key, cached_value, context)
        
        # Refresh early if:
        # 1. High access frequency and > 80% of TTL elapsed
        # 2. Very high hit rate and > 75% of TTL elapsed
        refresh_threshold = 0.9  # Default: refresh at 90% of TTL
        
        if stats.access_frequency > 2.0:  # More than twice per hour
            refresh_threshold = 0.8
        elif stats.hit_rate > 0.9:
            refresh_threshold = 0.75
        
        return age >= (ttl * refresh_threshold)
    
    def record_access(self, key: str, hit: bool):
        """Record access statistics."""
        if key not in self.access_stats:
            self.access_stats[key] = AccessStats(key)
        
        self.access_stats[key].record_access(hit)
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get summary of access statistics."""
        if not self.access_stats:
            return {"total_keys": 0}
        
        total_accesses = sum(stats.access_count for stats in self.access_stats.values())
        total_hits = sum(stats.hits for stats in self.access_stats.values())
        avg_hit_rate = total_hits / total_accesses if total_accesses > 0 else 0
        
        return {
            "total_keys": len(self.access_stats),
            "total_accesses": total_accesses,
            "total_hits": total_hits,
            "average_hit_rate": avg_hit_rate,
            "top_accessed": [
                {"key": key, "accesses": stats.access_count, "hit_rate": stats.hit_rate}
                for key, stats in sorted(
                    self.access_stats.items(),
                    key=lambda x: x[1].access_count,
                    reverse=True
                )[:10]
            ]
        }


@dataclass
class AccessStats:
    """Statistics for cache key access patterns."""
    
    key: str
    access_count: int = 0
    hits: int = 0
    misses: int = 0
    first_access: float = 0
    last_access: float = 0
    
    def __post_init__(self):
        if self.first_access == 0:
            self.first_access = time.time()
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        if self.access_count == 0:
            return 0.0
        return self.hits / self.access_count
    
    @property
    def access_frequency(self) -> float:
        """Calculate access frequency (accesses per hour)."""
        if self.first_access == 0:
            return 0.0
        
        duration_hours = (time.time() - self.first_access) / 3600
        if duration_hours == 0:
            return float('inf')
        
        return self.access_count / duration_hours
    
    def record_access(self, hit: bool):
        """Record an access event."""
        self.access_count += 1
        self.last_access = time.time()
        
        if hit:
            self.hits += 1
        else:
            self.misses += 1


class CacheWarmupStrategy:
    """
    Strategy for cache warming and preloading.
    
    Proactively loads frequently accessed data into cache.
    """
    
    def __init__(self, warmup_keys: list[str] = None, warmup_func: Optional[Callable] = None):
        self.warmup_keys = warmup_keys or []
        self.warmup_func = warmup_func
    
    async def warmup_cache(self, cache_client, strategy: CacheStrategy):
        """Warm up cache with predefined keys."""
        if not self.warmup_func:
            return
        
        warmed_count = 0
        
        for key in self.warmup_keys:
            try:
                # Check if already cached
                if await cache_client.exists(key):
                    continue
                
                # Generate value and cache it
                value = await self.warmup_func(key)
                if value is not None and await strategy.should_cache(key, value):
                    ttl = strategy.get_ttl(key, value)
                    await cache_client.set(key, value, ttl=ttl)
                    warmed_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to warm up cache key {key}: {e}")
        
        if warmed_count > 0:
            logger.info(f"Cache warmup completed: {warmed_count} keys loaded")


class CacheEvictionPolicy(Enum):
    """Cache eviction policies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    RANDOM = "random"  # Random eviction