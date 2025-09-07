"""
Logging and monitoring middleware.
"""

import json
import logging
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from contextvars import ContextVar

# Context variable for request ID
request_id_context: ContextVar[str] = ContextVar("request_id", default="")

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add unique request IDs to all requests.
    
    Adds X-Request-ID header and makes it available in context.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or use existing request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Set in context for use in other parts of the application
        request_id_context.set(request_id)
        
        # Add to request state for access in route handlers
        request.state.request_id = request_id
        
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_context.get("")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured request/response logging.
    
    Logs all HTTP requests and responses with timing, status codes, and other metadata.
    """
    
    def __init__(self, app, structured: bool = False, log_bodies: bool = False):
        super().__init__(app)
        self.structured = structured
        self.log_bodies = log_bodies
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Log incoming request
        await self._log_request(request, request_id)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response
            await self._log_response(request, response, request_id, process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            
            # Log error
            await self._log_error(request, e, request_id, process_time)
            
            # Re-raise the exception
            raise
    
    async def _log_request(self, request: Request, request_id: str) -> None:
        """Log incoming request details."""
        
        if self.structured:
            log_data = {
                "event": "request_started",
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "headers": dict(request.headers),
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent", "")
            }
            
            if self.log_bodies and request.method in ["POST", "PUT", "PATCH"]:
                try:
                    body = await request.body()
                    if body:
                        # Try to parse as JSON, fall back to string
                        try:
                            log_data["body"] = json.loads(body.decode())
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            log_data["body"] = body.decode("utf-8", errors="replace")[:1000]
                except Exception:
                    log_data["body"] = "<unable to read body>"
            
            logger.info(json.dumps(log_data))
        else:
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} - "
                f"Client: {self._get_client_ip(request)}"
            )
    
    async def _log_response(self, request: Request, response: Response, 
                           request_id: str, process_time: float) -> None:
        """Log response details."""
        
        if self.structured:
            log_data = {
                "event": "request_completed",
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time": round(process_time, 4),
                "response_headers": dict(response.headers)
            }
            
            if self.log_bodies and hasattr(response, "body"):
                try:
                    # This is tricky with streaming responses, so be careful
                    log_data["response_size"] = len(getattr(response, "body", b""))
                except Exception:
                    log_data["response_size"] = "unknown"
            
            logger.info(json.dumps(log_data))
        else:
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} - "
                f"{response.status_code} - {process_time:.4f}s"
            )
    
    async def _log_error(self, request: Request, error: Exception, 
                        request_id: str, process_time: float) -> None:
        """Log error details."""
        
        if self.structured:
            log_data = {
                "event": "request_failed",
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "process_time": round(process_time, 4),
                "client_ip": self._get_client_ip(request)
            }
            logger.error(json.dumps(log_data))
        else:
            logger.error(
                f"[{request_id}] {request.method} {request.url.path} - "
                f"ERROR: {type(error).__name__}: {str(error)} - {process_time:.4f}s"
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers (when behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct client
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"


class RequestContextFilter(logging.Filter):
    """
    Logging filter to add request context to log records.
    
    Adds request ID to all log messages during request processing.
    """
    
    def filter(self, record):
        request_id = get_request_id()
        if request_id:
            record.request_id = request_id
            # Modify the message to include request ID
            if not hasattr(record, 'getMessage'):
                return True
            
            message = record.getMessage()
            if not message.startswith(f"[{request_id}]"):
                record.msg = f"[{request_id}] {record.msg}"
        
        return True