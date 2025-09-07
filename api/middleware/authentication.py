"""
Authentication middleware and utilities.
"""

import logging
from typing import Callable, Optional, Set
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from config import get_security_settings

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API key authentication.
    
    Validates API keys for protected endpoints. Can be configured to protect
    all endpoints or specific paths only.
    """
    
    def __init__(
        self,
        app,
        protected_paths: Optional[Set[str]] = None,
        exclude_paths: Optional[Set[str]] = None,
        settings=None
    ):
        super().__init__(app)
        self.settings = settings or get_security_settings()
        
        # Default protected paths (empty means no API key protection)
        self.protected_paths = protected_paths or set()
        
        # Paths to always exclude from API key checks
        self.exclude_paths = exclude_paths or {
            "/health",
            "/docs", 
            "/openapi.json",
            "/redoc"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip API key check if no valid keys configured
        if not self.settings.valid_api_keys:
            return await call_next(request)
        
        # Check if path should be protected
        if not self._should_protect_path(request.url.path):
            return await call_next(request)
        
        # Validate API key
        api_key = self._extract_api_key(request)
        if not api_key or api_key not in self.settings.valid_api_keys:
            logger.warning(
                f"Invalid or missing API key for {request.method} {request.url.path} "
                f"from {self._get_client_ip(request)}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
                headers={"WWW-Authenticate": "ApiKey"}
            )
        
        # Add API key validation info to request state
        request.state.api_key_valid = True
        request.state.api_key = api_key
        
        return await call_next(request)
    
    def _should_protect_path(self, path: str) -> bool:
        """Determine if a path should be protected by API key."""
        
        # Always exclude certain paths
        if path in self.exclude_paths:
            return False
        
        # If no protected paths specified, don't protect anything
        if not self.protected_paths:
            return False
        
        # Check if path is in protected list
        return path in self.protected_paths or any(
            path.startswith(protected) for protected in self.protected_paths
        )
    
    def _extract_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from request headers."""
        
        # Try header first
        api_key = request.headers.get(self.settings.api_key_header)
        if api_key:
            return api_key
        
        # Try Authorization header as fallback
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix
        
        # Try query parameter as last resort (less secure)
        return request.query_params.get("api_key")
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"


def require_api_key(request: Request) -> str:
    """
    Dependency to require valid API key in route handlers.
    
    Usage:
        @app.get("/protected")
        async def protected_endpoint(api_key: str = Depends(require_api_key)):
            return {"message": "Access granted"}
    """
    if not hasattr(request.state, "api_key_valid") or not request.state.api_key_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid API key required",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    return getattr(request.state, "api_key", "")


class UserContext:
    """
    User context for authenticated requests.
    
    This is a foundation for future user authentication systems.
    Currently just tracks API key usage.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        user_id: Optional[str] = None,
        permissions: Optional[Set[str]] = None
    ):
        self.api_key = api_key
        self.user_id = user_id
        self.permissions = permissions or set()
        self.is_authenticated = bool(api_key or user_id)
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission."""
        return permission in self.permissions
    
    @classmethod
    def from_request(cls, request: Request) -> "UserContext":
        """Create user context from request state."""
        return cls(
            api_key=getattr(request.state, "api_key", None),
            user_id=getattr(request.state, "user_id", None),
            permissions=getattr(request.state, "permissions", set())
        )


def get_current_user(request: Request) -> UserContext:
    """
    Dependency to get current user context.
    
    Usage:
        @app.get("/me")
        async def get_user_info(user: UserContext = Depends(get_current_user)):
            return {"authenticated": user.is_authenticated}
    """
    return UserContext.from_request(request)