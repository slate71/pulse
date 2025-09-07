"""
Security middleware for adding security headers and protection.
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from config import get_security_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Adds headers like HSTS, CSP, X-Frame-Options, etc. for better security posture.
    """
    
    def __init__(self, app, settings=None):
        super().__init__(app)
        self.settings = settings or get_security_settings()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Security headers
        self._add_security_headers(response)
        
        return response
    
    def _add_security_headers(self, response: Response) -> None:
        """Add security headers to response."""
        
        # HSTS (HTTP Strict Transport Security)
        response.headers["Strict-Transport-Security"] = (
            f"max-age={self.settings.hsts_max_age}; includeSubDomains; preload"
        )
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.settings.csp_policy
        
        # X-Frame-Options to prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # X-Content-Type-Options to prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-XSS-Protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=(), "
            "accelerometer=(), ambient-light-sensor=()"
        )
        
        # Remove server information
        if "server" in response.headers:
            del response.headers["server"]
        
        # Add custom security headers
        response.headers["X-Content-Security-Policy"] = self.settings.csp_policy
        response.headers["X-WebKit-CSP"] = self.settings.csp_policy


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit request size for security.
    """
    
    def __init__(self, app, max_size: int = 16 * 1024 * 1024):  # 16MB default
        super().__init__(app)
        self.max_size = max_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check content length if available
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return Response(
                content="Request too large",
                status_code=413,
                headers={"Content-Type": "text/plain"}
            )
        
        return await call_next(request)


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request timeout handling.
    """
    
    def __init__(self, app, timeout: int = 300):  # 5 minutes default
        super().__init__(app)
        self.timeout = timeout
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Add timing header
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # Check if it's a timeout (this is a basic implementation)
            process_time = time.time() - start_time
            if process_time > self.timeout:
                return Response(
                    content="Request timeout",
                    status_code=408,
                    headers={"Content-Type": "text/plain"}
                )
            raise e