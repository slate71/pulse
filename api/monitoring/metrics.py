"""
Prometheus metrics collection and monitoring.

Provides comprehensive application metrics for monitoring performance,
errors, and system health.
"""

import time
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from prometheus_client import (
    Counter, Histogram, Gauge, Info, CollectorRegistry, 
    generate_latest, CONTENT_TYPE_LATEST, start_http_server
)
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings

logger = logging.getLogger(__name__)

# Global metrics registry
_registry: Optional[CollectorRegistry] = None

# Application info
APP_INFO = Info("pulse_api_info", "Application information")

# Request metrics
REQUEST_COUNT = Counter(
    "pulse_api_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status_code"]
)

REQUEST_DURATION = Histogram(
    "pulse_api_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

# Error metrics
ERROR_COUNT = Counter(
    "pulse_api_errors_total",
    "Total number of API errors",
    ["method", "endpoint", "error_type"]
)

EXCEPTION_COUNT = Counter(
    "pulse_api_exceptions_total",
    "Total number of unhandled exceptions",
    ["exception_type", "endpoint"]
)

# Database metrics
DB_QUERY_DURATION = Histogram(
    "pulse_api_db_query_duration_seconds",
    "Database query duration in seconds",
    ["query_type", "table"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)
)

DB_CONNECTIONS_ACTIVE = Gauge(
    "pulse_api_db_connections_active",
    "Number of active database connections"
)

DB_CONNECTIONS_IDLE = Gauge(
    "pulse_api_db_connections_idle", 
    "Number of idle database connections"
)

ACTIVE_CONNECTIONS = Gauge(
    "pulse_api_active_connections",
    "Number of active HTTP connections"
)

# External API metrics
EXTERNAL_API_DURATION = Histogram(
    "pulse_api_external_duration_seconds",
    "External API call duration in seconds",
    ["service", "endpoint", "status_code"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 60.0)
)

EXTERNAL_API_ERRORS = Counter(
    "pulse_api_external_errors_total",
    "Total external API errors",
    ["service", "error_type"]
)

# System metrics
MEMORY_USAGE = Gauge(
    "pulse_api_memory_usage_bytes",
    "Memory usage in bytes"
)

CPU_USAGE = Gauge(
    "pulse_api_cpu_usage_percent",
    "CPU usage percentage"
)

# Business metrics
PRIORITY_RECOMMENDATIONS_GENERATED = Counter(
    "pulse_api_priority_recommendations_total",
    "Total priority recommendations generated",
    ["context_type", "model_used"]
)

FEEDBACK_SUBMISSIONS = Counter(
    "pulse_api_feedback_submissions_total",
    "Total feedback submissions",
    ["recommendation_type", "feedback_score"]
)

EVENTS_INGESTED = Counter(
    "pulse_api_events_ingested_total",
    "Total events ingested",
    ["source", "event_type"]
)


def setup_metrics(settings=None) -> CollectorRegistry:
    """
    Initialize Prometheus metrics collection.
    
    Args:
        settings: Application settings
        
    Returns:
        CollectorRegistry: Configured metrics registry
    """
    global _registry
    
    if _registry is not None:
        return _registry
    
    _registry = CollectorRegistry()
    
    # Register all metrics with custom registry
    metrics = [
        APP_INFO, REQUEST_COUNT, REQUEST_DURATION, ERROR_COUNT, EXCEPTION_COUNT,
        DB_QUERY_DURATION, DB_CONNECTIONS_ACTIVE, DB_CONNECTIONS_IDLE, ACTIVE_CONNECTIONS,
        EXTERNAL_API_DURATION, EXTERNAL_API_ERRORS, MEMORY_USAGE, CPU_USAGE,
        PRIORITY_RECOMMENDATIONS_GENERATED, FEEDBACK_SUBMISSIONS, EVENTS_INGESTED
    ]
    
    for metric in metrics:
        _registry.register(metric)
    
    # Set application info
    if settings:
        settings = settings or get_settings()
        APP_INFO.info({
            "version": settings.app.version,
            "environment": settings.app.environment.value,
            "python_version": "3.12"
        })
    
    logger.info("Prometheus metrics initialized")
    return _registry


def get_metrics_registry() -> CollectorRegistry:
    """Get the metrics registry, initializing if necessary."""
    if _registry is None:
        return setup_metrics()
    return _registry


def track_db_query(query_type: str, table: str = "unknown"):
    """
    Decorator to track database query performance.
    
    Args:
        query_type: Type of query (select, insert, update, delete)
        table: Database table name
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(query_type=query_type, table=table).observe(duration)
        return wrapper
    return decorator


def track_external_api(service: str, endpoint: str = "unknown"):
    """
    Decorator to track external API call performance.
    
    Args:
        service: Service name (github, linear, openai)
        endpoint: API endpoint
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status_code = "unknown"
            try:
                result = await func(*args, **kwargs)
                # Try to extract status code from result
                if hasattr(result, 'status_code'):
                    status_code = str(result.status_code)
                elif isinstance(result, dict) and 'status_code' in result:
                    status_code = str(result['status_code'])
                else:
                    status_code = "200"  # Assume success if no status available
                return result
            except Exception as e:
                status_code = "error"
                EXTERNAL_API_ERRORS.labels(service=service, error_type=type(e).__name__).inc()
                raise
            finally:
                duration = time.time() - start_time
                EXTERNAL_API_DURATION.labels(
                    service=service, 
                    endpoint=endpoint, 
                    status_code=status_code
                ).observe(duration)
        return wrapper
    return decorator


def update_system_metrics():
    """Update system resource metrics."""
    try:
        import psutil
        import os
        
        # Memory usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        MEMORY_USAGE.set(memory_info.rss)
        
        # CPU usage
        cpu_percent = process.cpu_percent()
        CPU_USAGE.set(cpu_percent)
        
    except ImportError:
        logger.warning("psutil not available, skipping system metrics")
    except Exception as e:
        logger.error(f"Failed to update system metrics: {e}")


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect HTTP request metrics.
    
    Tracks request count, duration, and errors for all API endpoints.
    """
    
    def __init__(self, app, update_system_metrics_interval: int = 30):
        super().__init__(app)
        self.update_system_metrics_interval = update_system_metrics_interval
        self._last_system_update = 0
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract endpoint info
        method = request.method
        path = request.url.path
        
        # Normalize path for metrics (remove IDs, etc.)
        endpoint = self._normalize_path(path)
        
        # Track active connections
        ACTIVE_CONNECTIONS.inc()
        
        start_time = time.time()
        status_code = "500"  # Default to error
        
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            return response
            
        except Exception as e:
            # Track unhandled exceptions
            EXCEPTION_COUNT.labels(
                exception_type=type(e).__name__,
                endpoint=endpoint
            ).inc()
            
            # Track as error
            ERROR_COUNT.labels(
                method=method,
                endpoint=endpoint,
                error_type=type(e).__name__
            ).inc()
            
            raise
            
        finally:
            # Track request metrics
            duration = time.time() - start_time
            
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            # Track errors (4xx and 5xx)
            if status_code.startswith(('4', '5')):
                ERROR_COUNT.labels(
                    method=method,
                    endpoint=endpoint,
                    error_type=f"http_{status_code}"
                ).inc()
            
            ACTIVE_CONNECTIONS.dec()
            
            # Periodically update system metrics
            current_time = time.time()
            if current_time - self._last_system_update > self.update_system_metrics_interval:
                update_system_metrics()
                self._last_system_update = current_time
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalize URL path for metrics to avoid cardinality explosion.
        
        Replaces dynamic segments with placeholders.
        """
        # Common patterns to normalize
        import re
        
        # Replace UUIDs
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{uuid}', path)
        
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        
        # Replace alphanumeric IDs (common in APIs)
        path = re.sub(r'/[a-zA-Z0-9_-]{8,}', '/{id}', path)
        
        return path


def get_metrics_text() -> str:
    """Get Prometheus metrics in text format."""
    registry = get_metrics_registry()
    return generate_latest(registry).decode('utf-8')


def get_metrics_content_type() -> str:
    """Get the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST