"""
Monitoring and observability endpoints.

Provides comprehensive monitoring, metrics, and debugging endpoints
for production observability.
"""

import time
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Query, HTTPException, status, Depends
from fastapi.responses import PlainTextResponse

from monitoring import (
    get_metrics_registry,
    get_metrics_text,
    get_metrics_content_type,
    get_tracer,
    get_active_traces,
    get_profiler,
    get_performance_stats,
    get_all_profiles
)
from monitoring.circuit_breaker import get_circuit_breaker_registry, CircuitBreakerHealthCheck
from cache import get_cache_client, get_memory_cache
from config import get_settings
from middleware.authentication import require_api_key

router = APIRouter(tags=["monitoring"], prefix="/monitoring")

logger = logging.getLogger(__name__)


@router.get("/metrics", response_class=PlainTextResponse)
async def get_prometheus_metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format for scraping.
    """
    try:
        metrics_text = get_metrics_text()
        return PlainTextResponse(
            content=metrics_text,
            media_type=get_metrics_content_type()
        )
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate metrics"
        )


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check with all system components.
    
    Provides comprehensive health information including circuit breakers,
    cache status, and system metrics.
    """
    from health import get_health_checker
    
    health_checker = get_health_checker()
    health_result = await health_checker.check_all()
    
    # Add circuit breaker health
    cb_health_check = CircuitBreakerHealthCheck()
    circuit_health = cb_health_check.check_health()
    
    # Add cache health
    cache_health = await _get_cache_health()
    
    # Combine all health information
    detailed_health = {
        **health_result,
        "circuit_breakers": circuit_health,
        "cache": cache_health,
        "monitoring": {
            "tracing_enabled": True,
            "metrics_enabled": True,
            "profiling_enabled": get_profiler().enabled
        }
    }
    
    # Determine overall status
    if (health_result["status"] == "unhealthy" or 
        circuit_health["status"] == "failed" or
        cache_health["redis"]["status"] == "failed"):
        detailed_health["status"] = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif (health_result["status"] == "degraded" or
          circuit_health["status"] == "degraded" or
          cache_health["redis"]["status"] == "degraded"):
        detailed_health["status"] = "degraded"
        status_code = status.HTTP_200_OK
    else:
        detailed_health["status"] = "healthy"
        status_code = status.HTTP_200_OK
    
    return detailed_health


@router.get("/traces")
async def get_traces(
    limit: int = Query(10, ge=1, le=100),
    trace_id: Optional[str] = Query(None)
):
    """
    Get active traces for debugging.
    
    Args:
        limit: Maximum number of traces to return
        trace_id: Specific trace ID to retrieve
    """
    if trace_id:
        from monitoring.tracing import get_trace_by_id
        trace = get_trace_by_id(trace_id)
        if not trace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trace not found"
            )
        return {"trace": trace.to_dict()}
    
    active_traces = get_active_traces()
    
    # Sort by start time (most recent first) and limit
    sorted_traces = sorted(
        active_traces.values(),
        key=lambda x: x.start_time,
        reverse=True
    )[:limit]
    
    return {
        "traces": [trace.to_dict() for trace in sorted_traces],
        "total_active": len(active_traces)
    }


@router.post("/traces/cleanup")
async def cleanup_old_traces(
    max_age_seconds: int = Query(300, ge=60, le=3600)
):
    """
    Cleanup old traces to free memory.
    
    Args:
        max_age_seconds: Maximum age of traces to keep
    """
    from monitoring.tracing import clear_old_traces
    
    clear_old_traces(max_age_seconds)
    
    return {"message": f"Cleaned up traces older than {max_age_seconds} seconds"}


@router.get("/profiling/stats")
async def get_profiling_stats():
    """Get profiling statistics and recent profiles."""
    return get_performance_stats()


@router.get("/profiling/profiles")
async def get_profiles(
    limit: int = Query(10, ge=1, le=50),
    profile_id: Optional[str] = Query(None)
):
    """
    Get profiling data.
    
    Args:
        limit: Maximum number of profiles to return
        profile_id: Specific profile ID to retrieve
    """
    if profile_id:
        profiler = get_profiler()
        profile = profiler.get_profile(profile_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        return {"profile": profile.to_dict()}
    
    all_profiles = get_all_profiles()
    
    # Sort by start time and limit
    sorted_profiles = dict(
        sorted(all_profiles.items(), key=lambda x: x[1].get('start_time', 0), reverse=True)[:limit]
    )
    
    return {
        "profiles": sorted_profiles,
        "total_profiles": len(all_profiles)
    }


@router.post("/profiling/enable")
async def enable_profiling():
    """Enable profiling globally."""
    profiler = get_profiler()
    profiler.enable()
    return {"message": "Profiling enabled"}


@router.post("/profiling/disable") 
async def disable_profiling():
    """Disable profiling globally."""
    profiler = get_profiler()
    profiler.disable()
    return {"message": "Profiling disabled"}


@router.post("/profiling/cleanup")
async def cleanup_old_profiles(
    max_age_seconds: int = Query(3600, ge=300, le=86400)
):
    """
    Cleanup old profiling data.
    
    Args:
        max_age_seconds: Maximum age of profiles to keep
    """
    profiler = get_profiler()
    profiler.clear_old_profiles(max_age_seconds)
    
    return {"message": f"Cleaned up profiles older than {max_age_seconds} seconds"}


@router.get("/circuit-breakers")
async def get_circuit_breaker_status():
    """Get status of all circuit breakers."""
    registry = get_circuit_breaker_registry()
    return registry.get_all_states()


@router.post("/circuit-breakers/{name}/reset")
async def reset_circuit_breaker(name: str):
    """
    Reset a specific circuit breaker.
    
    Args:
        name: Circuit breaker name
    """
    registry = get_circuit_breaker_registry()
    breaker = registry.get(name)
    
    if not breaker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Circuit breaker not found"
        )
    
    breaker.reset()
    return {"message": f"Circuit breaker '{name}' reset"}


@router.post("/circuit-breakers/reset-all")
async def reset_all_circuit_breakers():
    """Reset all circuit breakers."""
    registry = get_circuit_breaker_registry()
    registry.reset_all()
    return {"message": "All circuit breakers reset"}


@router.get("/cache/status")
async def get_cache_status():
    """Get cache status and statistics."""
    return await _get_cache_health()


@router.get("/cache/redis/info")
async def get_redis_cache_info():
    """Get detailed Redis cache information."""
    cache_client = get_cache_client()
    
    if not cache_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis cache not available"
        )
    
    return await cache_client.get_info()


@router.get("/cache/memory/stats")
async def get_memory_cache_stats():
    """Get memory cache statistics."""
    memory_cache = get_memory_cache()
    return memory_cache.get_stats()


@router.post("/cache/redis/clear")
async def clear_redis_cache(
    pattern: str = Query("*", description="Pattern to match keys for clearing")
):
    """
    Clear Redis cache entries matching pattern.
    
    Args:
        pattern: Pattern to match cache keys
    """
    from cache import invalidate_cache
    
    cleared_count = await invalidate_cache(pattern)
    
    return {
        "message": f"Cleared {cleared_count} cache entries",
        "pattern": pattern
    }


@router.post("/cache/memory/clear")
async def clear_memory_cache():
    """Clear all memory cache entries."""
    memory_cache = get_memory_cache()
    cleared_count = memory_cache.clear()
    
    return {"message": f"Cleared {cleared_count} memory cache entries"}


@router.get("/system/info")
async def get_system_info():
    """Get system information and resource usage."""
    try:
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        system_info = {
            "process": {
                "pid": os.getpid(),
                "memory_rss": memory_info.rss,
                "memory_vms": memory_info.vms,
                "cpu_percent": process.cpu_percent(),
                "threads": process.num_threads(),
                "open_files": len(process.open_files()),
                "connections": len(process.connections())
            },
            "system": {
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total,
                "memory_available": psutil.virtual_memory().available,
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": {
                    "total": psutil.disk_usage("/").total,
                    "used": psutil.disk_usage("/").used,
                    "free": psutil.disk_usage("/").free
                }
            },
            "uptime": time.time() - process.create_time()
        }
        
        return system_info
        
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System monitoring not available (psutil not installed)"
        )


@router.get("/debug/config")
async def get_debug_config():
    """Get application configuration for debugging (sensitive data removed)."""
    settings = get_settings()
    
    # Create safe config view (no secrets)
    safe_config = {
        "app": {
            "title": settings.app.title,
            "version": settings.app.version,
            "environment": settings.app.environment.value,
            "debug": settings.app.debug,
            "host": settings.app.host,
            "port": settings.app.port,
            "log_level": settings.app.log_level.value
        },
        "database": {
            "min_connections": settings.database.min_connections,
            "max_connections": settings.database.max_connections,
            "command_timeout": settings.database.command_timeout
        },
        "security": {
            "cors_origins": settings.security.cors_origins,
            "rate_limit_requests": settings.security.rate_limit_requests,
            "rate_limit_window": settings.security.rate_limit_window
        },
        "external_apis": {
            "github_enabled": settings.external_apis.github_enabled,
            "linear_enabled": settings.external_apis.linear_enabled,
            "openai_enabled": settings.external_apis.openai_enabled
        }
    }
    
    return safe_config


async def _get_cache_health() -> Dict[str, Any]:
    """Get cache health status."""
    cache_health = {
        "redis": {
            "status": "disabled",
            "connected": False,
            "stats": {}
        },
        "memory": {
            "status": "healthy",
            "stats": {}
        }
    }
    
    # Redis cache status
    cache_client = get_cache_client()
    if cache_client:
        if cache_client.connected:
            cache_health["redis"]["status"] = "healthy"
            cache_health["redis"]["connected"] = True
            try:
                cache_health["redis"]["stats"] = await cache_client.get_info()
            except Exception:
                cache_health["redis"]["status"] = "degraded"
        else:
            cache_health["redis"]["status"] = "failed"
    
    # Memory cache status
    memory_cache = get_memory_cache()
    cache_health["memory"]["stats"] = memory_cache.get_stats()
    
    return cache_health