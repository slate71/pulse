"""
Distributed tracing and request correlation.

Provides request tracing capabilities for debugging and performance analysis.
"""

import time
import uuid
import logging
import threading
from typing import Dict, Any, Optional, List, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Context variables for tracing
_trace_context: ContextVar[Optional['TraceContext']] = ContextVar('trace_context', default=None)

# Global trace storage (in production, this would be sent to a tracing system)
_active_traces: Dict[str, 'TraceContext'] = {}
_trace_lock = threading.Lock()


@dataclass
class TraceSpan:
    """Individual span within a trace."""
    
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ok"  # ok, error, timeout
    
    @property
    def duration(self) -> Optional[float]:
        """Get span duration in seconds."""
        if self.end_time is None:
            return None
        return self.end_time - self.start_time
    
    def finish(self, status: str = "ok"):
        """Mark span as finished."""
        self.end_time = time.time()
        self.status = status
    
    def add_tag(self, key: str, value: Any):
        """Add a tag to the span."""
        self.tags[key] = value
    
    def add_log(self, message: str, level: str = "info", **kwargs):
        """Add a log entry to the span."""
        self.logs.append({
            "timestamp": time.time(),
            "level": level,
            "message": message,
            **kwargs
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary for serialization."""
        return {
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "tags": self.tags,
            "logs": self.logs,
            "status": self.status
        }


@dataclass
class TraceContext:
    """Complete trace context containing multiple spans."""
    
    trace_id: str
    request_id: str
    user_id: Optional[str] = None
    spans: List[TraceSpan] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """Get total trace duration in seconds."""
        if self.end_time is None:
            return None
        return self.end_time - self.start_time
    
    @property
    def root_span(self) -> Optional[TraceSpan]:
        """Get the root span (span with no parent)."""
        for span in self.spans:
            if span.parent_span_id is None:
                return span
        return None
    
    def add_span(self, span: TraceSpan):
        """Add a span to this trace."""
        self.spans.append(span)
    
    def get_active_span(self) -> Optional[TraceSpan]:
        """Get the most recently started span that hasn't finished."""
        for span in reversed(self.spans):
            if span.end_time is None:
                return span
        return None
    
    def finish(self):
        """Mark trace as finished."""
        self.end_time = time.time()
        
        # Finish any unfinished spans
        for span in self.spans:
            if span.end_time is None:
                span.finish("aborted")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "user_id": self.user_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "metadata": self.metadata,
            "spans": [span.to_dict() for span in self.spans]
        }


class Tracer:
    """Tracer for creating and managing spans."""
    
    def __init__(self, service_name: str = "pulse-api"):
        self.service_name = service_name
    
    def start_trace(self, operation_name: str, request_id: str = None, user_id: str = None) -> TraceContext:
        """Start a new trace."""
        trace_id = str(uuid.uuid4())
        request_id = request_id or str(uuid.uuid4())
        
        context = TraceContext(
            trace_id=trace_id,
            request_id=request_id,
            user_id=user_id
        )
        
        # Create root span
        root_span = self.start_span(operation_name, context=context)
        root_span.add_tag("service.name", self.service_name)
        root_span.add_tag("trace.root", True)
        
        # Store in global registry
        with _trace_lock:
            _active_traces[trace_id] = context
        
        # Set in context
        _trace_context.set(context)
        
        return context
    
    def start_span(self, operation_name: str, context: TraceContext = None, parent_span: TraceSpan = None) -> TraceSpan:
        """Start a new span."""
        if context is None:
            context = _trace_context.get()
            if context is None:
                # Create a new trace if none exists
                context = self.start_trace(operation_name)
        
        span_id = str(uuid.uuid4())
        parent_span_id = None
        
        if parent_span:
            parent_span_id = parent_span.span_id
        else:
            # Use the currently active span as parent
            active_span = context.get_active_span()
            if active_span:
                parent_span_id = active_span.span_id
        
        span = TraceSpan(
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            start_time=time.time()
        )
        
        context.add_span(span)
        return span
    
    def finish_trace(self, trace_id: str = None):
        """Finish a trace and remove from active traces."""
        context = _trace_context.get()
        if context and (trace_id is None or context.trace_id == trace_id):
            context.finish()
            
            # Remove from active traces
            with _trace_lock:
                _active_traces.pop(context.trace_id, None)
            
            # Clear context
            _trace_context.set(None)
            
            logger.debug(f"Trace {context.trace_id} finished with {len(context.spans)} spans")


# Global tracer instance
_tracer = Tracer()


def get_tracer() -> Tracer:
    """Get the global tracer instance."""
    return _tracer


def setup_tracing(service_name: str = "pulse-api"):
    """Setup tracing with custom service name."""
    global _tracer
    _tracer = Tracer(service_name)
    logger.info(f"Tracing setup complete for service: {service_name}")


def get_current_trace() -> Optional[TraceContext]:
    """Get the current trace context."""
    return _trace_context.get()


def get_current_span() -> Optional[TraceSpan]:
    """Get the current active span."""
    context = _trace_context.get()
    if context:
        return context.get_active_span()
    return None


def trace_request(operation_name: str = None, tags: Dict[str, Any] = None):
    """
    Decorator to trace a function or method.
    
    Args:
        operation_name: Name of the operation (defaults to function name)
        tags: Additional tags to add to the span
    """
    def decorator(func: Callable) -> Callable:
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__qualname__}"
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            span = tracer.start_span(operation_name)
            
            # Add function information
            span.add_tag("function.name", func.__name__)
            span.add_tag("function.module", func.__module__)
            
            # Add custom tags
            if tags:
                for key, value in tags.items():
                    span.add_tag(key, value)
            
            try:
                result = await func(*args, **kwargs)
                span.add_tag("result.success", True)
                span.finish("ok")
                return result
            except Exception as e:
                span.add_tag("result.success", False)
                span.add_tag("error.type", type(e).__name__)
                span.add_tag("error.message", str(e))
                span.add_log(f"Exception occurred: {e}", level="error")
                span.finish("error")
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            span = tracer.start_span(operation_name)
            
            # Add function information
            span.add_tag("function.name", func.__name__)
            span.add_tag("function.module", func.__module__)
            
            # Add custom tags
            if tags:
                for key, value in tags.items():
                    span.add_tag(key, value)
            
            try:
                result = func(*args, **kwargs)
                span.add_tag("result.success", True)
                span.finish("ok")
                return result
            except Exception as e:
                span.add_tag("result.success", False)
                span.add_tag("error.type", type(e).__name__)
                span.add_tag("error.message", str(e))
                span.add_log(f"Exception occurred: {e}", level="error")
                span.finish("error")
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add tracing to HTTP requests.
    
    Creates a trace for each incoming request and adds relevant metadata.
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Extract request information
        method = request.method
        path = request.url.path
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Get or create request ID
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        
        # Start trace
        tracer = get_tracer()
        trace_context = tracer.start_trace(
            operation_name=f"{method} {path}",
            request_id=request_id
        )
        
        # Add request metadata to trace
        trace_context.metadata.update({
            "http.method": method,
            "http.url": str(request.url),
            "http.user_agent": user_agent,
            "http.remote_addr": request.client.host if request.client else "unknown"
        })
        
        # Add tags to root span
        root_span = trace_context.root_span
        if root_span:
            root_span.add_tag("http.method", method)
            root_span.add_tag("http.url", str(request.url))
            root_span.add_tag("http.user_agent", user_agent)
            root_span.add_tag("request.id", request_id)
        
        try:
            response = await call_next(request)
            
            # Add response information
            if root_span:
                root_span.add_tag("http.status_code", response.status_code)
                root_span.add_tag("response.success", response.status_code < 400)
            
            trace_context.metadata["http.status_code"] = response.status_code
            
            return response
            
        except Exception as e:
            # Add error information
            if root_span:
                root_span.add_tag("http.status_code", 500)
                root_span.add_tag("response.success", False)
                root_span.add_tag("error.type", type(e).__name__)
                root_span.add_tag("error.message", str(e))
                root_span.add_log(f"Request failed: {e}", level="error")
            
            trace_context.metadata["error"] = {
                "type": type(e).__name__,
                "message": str(e)
            }
            
            raise
        
        finally:
            # Finish trace
            tracer.finish_trace(trace_context.trace_id)


def get_active_traces() -> Dict[str, TraceContext]:
    """Get all currently active traces (for debugging)."""
    with _trace_lock:
        return _active_traces.copy()


def get_trace_by_id(trace_id: str) -> Optional[TraceContext]:
    """Get a specific trace by ID."""
    with _trace_lock:
        return _active_traces.get(trace_id)


def clear_old_traces(max_age_seconds: int = 300):
    """Clear traces older than specified age."""
    current_time = time.time()
    expired_trace_ids = []
    
    with _trace_lock:
        for trace_id, context in _active_traces.items():
            if context.end_time and (current_time - context.end_time) > max_age_seconds:
                expired_trace_ids.append(trace_id)
            elif (current_time - context.start_time) > max_age_seconds * 2:
                # Force cleanup of very old traces even if not finished
                expired_trace_ids.append(trace_id)
        
        for trace_id in expired_trace_ids:
            del _active_traces[trace_id]
    
    if expired_trace_ids:
        logger.debug(f"Cleaned up {len(expired_trace_ids)} old traces")