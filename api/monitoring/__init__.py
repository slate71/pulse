"""
Monitoring and observability components for the Pulse API.
"""

from .metrics import (
    setup_metrics,
    get_metrics_registry,
    REQUEST_COUNT,
    REQUEST_DURATION,
    ERROR_COUNT,
    DB_QUERY_DURATION,
    EXTERNAL_API_DURATION,
    ACTIVE_CONNECTIONS
)
from .tracing import (
    setup_tracing,
    get_tracer,
    trace_request,
    TraceContext
)
from .profiling import (
    setup_profiling,
    ProfilerMiddleware,
    get_performance_stats
)

__all__ = [
    "setup_metrics",
    "get_metrics_registry", 
    "REQUEST_COUNT",
    "REQUEST_DURATION",
    "ERROR_COUNT",
    "DB_QUERY_DURATION",
    "EXTERNAL_API_DURATION",
    "ACTIVE_CONNECTIONS",
    "setup_tracing",
    "get_tracer",
    "trace_request",
    "TraceContext",
    "setup_profiling",
    "ProfilerMiddleware",
    "get_performance_stats",
]