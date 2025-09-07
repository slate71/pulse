"""
Redis-based caching implementation.

Provides distributed caching capabilities for expensive operations
and API response caching.
"""

import json
import time
import hashlib
import logging
from typing import Any, Dict, Optional, Union, Callable, List
from functools import wraps
import asyncio

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings

logger = logging.getLogger(__name__)

# Global cache client
_cache_client: Optional['CacheClient'] = None


class CacheClient:
    """Redis-based cache client with async support."""
    
    def __init__(
        self,
        redis_url: str = None,
        default_ttl: int = 3600,
        key_prefix: str = "pulse_api",
        max_retries: int = 3
    ):
        self.redis_url = redis_url or "redis://localhost:6379"
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self.max_retries = max_retries
        self.redis_client: Optional[redis.Redis] = None
        self.connected = False
        
        # Metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_errors = 0
    
    async def connect(self) -> bool:
        """Connect to Redis server."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, caching will be disabled")
            return False
        
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            self.connected = True
            logger.info(f"Connected to Redis at {self.redis_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Redis server."""
        if self.redis_client:
            await self.redis_client.close()
            self.connected = False
            logger.info("Disconnected from Redis")
    
    def _make_key(self, key: str) -> str:
        """Create a prefixed cache key."""
        return f"{self.key_prefix}:{key}"
    
    def _serialize_value(self, value: Any) -> str:
        """Serialize value for caching."""
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize cache value: {e}")
            return json.dumps(str(value))
    
    def _deserialize_value(self, value: str) -> Any:
        """Deserialize value from cache."""
        try:
            return json.loads(value)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to deserialize cache value: {e}")
            return value
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.connected:
            return None
        
        cache_key = self._make_key(key)
        
        for attempt in range(self.max_retries):
            try:
                value = await self.redis_client.get(cache_key)
                if value is not None:
                    self.cache_hits += 1
                    return self._deserialize_value(value)
                else:
                    self.cache_misses += 1
                    return None
                    
            except Exception as e:
                self.cache_errors += 1
                logger.warning(f"Cache get error (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    return None
                await asyncio.sleep(0.1 * (attempt + 1))
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            nx: Only set if key doesn't exist
            xx: Only set if key exists
        """
        if not self.connected:
            return False
        
        cache_key = self._make_key(key)
        serialized_value = self._serialize_value(value)
        ttl = ttl or self.default_ttl
        
        for attempt in range(self.max_retries):
            try:
                result = await self.redis_client.set(
                    cache_key,
                    serialized_value,
                    ex=ttl,
                    nx=nx,
                    xx=xx
                )
                return bool(result)
                
            except Exception as e:
                self.cache_errors += 1
                logger.warning(f"Cache set error (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    return False
                await asyncio.sleep(0.1 * (attempt + 1))
        
        return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if not self.connected:
            return False
        
        cache_key = self._make_key(key)
        
        try:
            result = await self.redis_client.delete(cache_key)
            return result > 0
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.connected:
            return False
        
        cache_key = self._make_key(key)
        
        try:
            result = await self.redis_client.exists(cache_key)
            return result > 0
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache exists error: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> Optional[int]:
        """Increment a numeric value in cache."""
        if not self.connected:
            return None
        
        cache_key = self._make_key(key)
        
        try:
            # Use pipeline for atomic operation
            pipe = self.redis_client.pipeline()
            pipe.incr(cache_key, amount)
            if ttl:
                pipe.expire(cache_key, ttl)
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache increment error: {e}")
            return None
    
    async def get_pattern(self, pattern: str) -> List[str]:
        """Get keys matching a pattern."""
        if not self.connected:
            return []
        
        cache_pattern = self._make_key(pattern)
        
        try:
            keys = await self.redis_client.keys(cache_pattern)
            # Remove prefix from keys
            return [key.replace(f"{self.key_prefix}:", "", 1) for key in keys]
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache pattern search error: {e}")
            return []
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern."""
        if not self.connected:
            return 0
        
        keys = await self.get_pattern(pattern)
        if not keys:
            return 0
        
        try:
            cache_keys = [self._make_key(key) for key in keys]
            result = await self.redis_client.delete(*cache_keys)
            return result
        except Exception as e:
            self.cache_errors += 1
            logger.warning(f"Cache pattern clear error: {e}")
            return 0
    
    async def get_info(self) -> Dict[str, Any]:
        """Get cache client information and stats."""
        info = {
            "connected": self.connected,
            "redis_url": self.redis_url,
            "key_prefix": self.key_prefix,
            "default_ttl": self.default_ttl,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_errors": self.cache_errors,
            "hit_rate": self.cache_hits / max(self.cache_hits + self.cache_misses, 1)
        }
        
        if self.connected and self.redis_client:
            try:
                redis_info = await self.redis_client.info()
                info["redis_memory"] = redis_info.get("used_memory_human", "unknown")
                info["redis_connected_clients"] = redis_info.get("connected_clients", 0)
                info["redis_total_commands"] = redis_info.get("total_commands_processed", 0)
            except Exception as e:
                logger.warning(f"Failed to get Redis info: {e}")
        
        return info


async def setup_cache(redis_url: str = None, **kwargs) -> Optional[CacheClient]:
    """
    Setup Redis cache client.
    
    Args:
        redis_url: Redis connection URL
        **kwargs: Additional CacheClient arguments
    """
    global _cache_client
    
    settings = get_settings()
    redis_url = redis_url or getattr(settings.external_apis, 'redis_url', None)
    
    if not redis_url and not REDIS_AVAILABLE:
        logger.warning("Redis caching disabled: no Redis URL and redis library not available")
        return None
    
    _cache_client = CacheClient(redis_url=redis_url, **kwargs)
    
    if await _cache_client.connect():
        logger.info("Redis caching enabled")
        return _cache_client
    else:
        logger.warning("Redis caching disabled: connection failed")
        _cache_client = None
        return None


def get_cache_client() -> Optional[CacheClient]:
    """Get the global cache client."""
    return _cache_client


def cache_result(
    key_func: Optional[Callable] = None,
    ttl: int = 3600,
    skip_cache_condition: Optional[Callable] = None
):
    """
    Decorator to cache function results.
    
    Args:
        key_func: Function to generate cache key from args
        ttl: Time to live in seconds
        skip_cache_condition: Function to determine if cache should be skipped
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_client = get_cache_client()
            if not cache_client or not cache_client.connected:
                return await func(*args, **kwargs)
            
            # Check if caching should be skipped
            if skip_cache_condition and skip_cache_condition(*args, **kwargs):
                return await func(*args, **kwargs)
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                func_name = f"{func.__module__}.{func.__qualname__}"
                arg_hash = hashlib.md5(str((args, kwargs)).encode()).hexdigest()
                cache_key = f"func:{func_name}:{arg_hash}"
            
            # Try to get from cache
            cached_result = await cache_client.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_client.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


async def invalidate_cache(pattern: str) -> int:
    """
    Invalidate cache entries matching a pattern.
    
    Args:
        pattern: Pattern to match cache keys
        
    Returns:
        Number of keys invalidated
    """
    cache_client = get_cache_client()
    if not cache_client:
        return 0
    
    return await cache_client.clear_pattern(pattern)


class CacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware for HTTP response caching.
    
    Caches GET responses based on URL and headers.
    """
    
    def __init__(
        self,
        app,
        default_ttl: int = 300,
        cache_get_only: bool = True,
        cache_private: bool = False,
        vary_headers: List[str] = None
    ):
        super().__init__(app)
        self.default_ttl = default_ttl
        self.cache_get_only = cache_get_only
        self.cache_private = cache_private
        self.vary_headers = vary_headers or ["Accept", "Accept-Encoding"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if request should be cached
        if not self._should_cache_request(request):
            return await call_next(request)
        
        cache_client = get_cache_client()
        if not cache_client or not cache_client.connected:
            return await call_next(request)
        
        # Generate cache key
        cache_key = self._generate_cache_key(request)
        
        # Try to get cached response
        cached_response = await cache_client.get(cache_key)
        if cached_response:
            return Response(
                content=cached_response["body"],
                status_code=cached_response["status_code"],
                headers=cached_response["headers"],
                media_type=cached_response.get("media_type")
            )
        
        # Execute request
        response = await call_next(request)
        
        # Cache response if appropriate
        if self._should_cache_response(response):
            await self._cache_response(cache_client, cache_key, response)
        
        return response
    
    def _should_cache_request(self, request: Request) -> bool:
        """Determine if request should be cached."""
        # Only cache GET requests by default
        if self.cache_get_only and request.method != "GET":
            return False
        
        # Don't cache if user explicitly disables caching
        if request.headers.get("Cache-Control") == "no-cache":
            return False
        
        # Don't cache private requests unless explicitly enabled
        if not self.cache_private and request.headers.get("Authorization"):
            return False
        
        return True
    
    def _should_cache_response(self, response: Response) -> bool:
        """Determine if response should be cached."""
        # Only cache successful responses
        if response.status_code >= 400:
            return False
        
        # Don't cache if response explicitly disables caching
        cache_control = response.headers.get("Cache-Control", "")
        if "no-cache" in cache_control or "private" in cache_control:
            return False
        
        return True
    
    def _generate_cache_key(self, request: Request) -> str:
        """Generate cache key for request."""
        # Base key from method and path
        base_key = f"{request.method}:{request.url.path}"
        
        # Add query parameters
        if request.url.query:
            base_key += f"?{request.url.query}"
        
        # Add vary headers
        vary_parts = []
        for header in self.vary_headers:
            value = request.headers.get(header, "")
            vary_parts.append(f"{header}:{value}")
        
        if vary_parts:
            base_key += f"|{','.join(vary_parts)}"
        
        # Hash the key to keep it manageable
        key_hash = hashlib.md5(base_key.encode()).hexdigest()
        return f"http_cache:{key_hash}"
    
    async def _cache_response(self, cache_client: CacheClient, cache_key: str, response: Response):
        """Cache the response."""
        try:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # Prepare cacheable response data
            cache_data = {
                "body": body.decode("utf-8", errors="replace"),
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type
            }
            
            # Cache the response
            await cache_client.set(cache_key, cache_data, ttl=self.default_ttl)
            
            # Recreate response with body
            response.body_iterator = iter([body])
            
        except Exception as e:
            logger.warning(f"Failed to cache response: {e}")