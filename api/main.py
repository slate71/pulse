"""
Pulse API - Main application module.

AI-powered engineering radar API with priority recommendations.
Enhanced with security hardening and production-ready features.
"""

import logging
import signal
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from middleware import (
    SecurityHeadersMiddleware, 
    LoggingMiddleware, 
    RequestIDMiddleware,
    RequestSizeMiddleware,
    RequestTimeoutMiddleware
)
from monitoring import (
    setup_metrics,
    setup_tracing,
    setup_profiling,
    MetricsMiddleware,
    TracingMiddleware,
    ProfilerMiddleware
)
from cache import setup_cache, start_memory_cache_cleanup
from routers import health, ingest, priority, report, monitoring
from db import close_pool

# Initialize settings and configure logging
settings = get_settings()
settings.configure_logging()
settings.validate_configuration()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    
    # Startup
    logger.info(f"Starting Pulse API v{settings.app.version}")
    logger.info(f"Environment: {settings.app.environment.value}")
    
    # Setup monitoring and observability
    setup_metrics(settings)
    setup_tracing("pulse-api")
    setup_profiling(enabled=settings.app.debug)
    
    # Setup caching
    await setup_cache()
    start_memory_cache_cleanup()
    
    logger.info("Monitoring and caching systems initialized")
    
    try:
        yield
    finally:
        # Shutdown
        logger.info("Shutting down Pulse API")
        
        # Close database connections
        await close_pool()
        
        # Stop cache cleanup
        from cache.memory_cache import stop_memory_cache_cleanup
        stop_memory_cache_cleanup()
        
        # Close cache connections
        from cache import get_cache_client
        cache_client = get_cache_client()
        if cache_client:
            await cache_client.disconnect()
        
        logger.info("All connections closed and cleanup completed")


# Create FastAPI application with lifespan management
app = FastAPI(
    title=settings.app.title,
    description=settings.app.description,
    version=settings.app.version,
    debug=settings.app.debug,
    lifespan=lifespan
)

# Add monitoring and security middleware (order matters!)
# Request ID should be first for proper logging context
app.add_middleware(RequestIDMiddleware)

# Tracing middleware should be early to capture full request lifecycle
app.add_middleware(TracingMiddleware)

# Metrics middleware for monitoring
app.add_middleware(MetricsMiddleware)

# Profiling middleware (only active when profiling is enabled)
app.add_middleware(ProfilerMiddleware, profile_slow_requests=True, slow_threshold=1.0)

# Logging middleware should be early to capture all requests
app.add_middleware(
    LoggingMiddleware, 
    structured=settings.app.structured_logging,
    log_bodies=settings.app.debug
)

# Security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeMiddleware, max_size=settings.app.max_request_size)
app.add_middleware(RequestTimeoutMiddleware, timeout=settings.app.request_timeout)

# CORS configuration based on settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=settings.security.cors_credentials,
    allow_methods=settings.security.cors_methods,
    allow_headers=settings.security.cors_headers,
)

# Include routers
app.include_router(health.router)
app.include_router(monitoring.router)
app.include_router(ingest.router)
app.include_router(report.router)
app.include_router(priority.router)


def setup_signal_handlers():
    """Setup graceful shutdown signal handlers."""
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        # The lifespan handler will take care of cleanup
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


if __name__ == "__main__":
    import uvicorn
    
    setup_signal_handlers()
    
    logger.info(f"Starting server on {settings.app.host}:{settings.app.port}")
    
    uvicorn.run(
        app, 
        host=settings.app.host, 
        port=settings.app.port,
        reload=settings.app.is_development,
        log_level=settings.app.log_level.value.lower(),
        access_log=settings.app.debug
    )
