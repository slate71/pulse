"""
Health check router with comprehensive health monitoring.
"""

import json
from typing import Dict, Any
from fastapi import APIRouter, Response, status
from health import get_health_checker

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check_endpoint() -> Dict[str, Any]:
    """
    Comprehensive health check endpoint.
    
    Returns detailed status for all system dependencies.
    """
    health_checker = get_health_checker()
    result = await health_checker.check_all()
    
    # Set appropriate HTTP status code based on health
    status_code = status.HTTP_200_OK
    if result["status"] == "unhealthy":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif result["status"] == "degraded":
        status_code = status.HTTP_200_OK  # Still functional
    
    return Response(
        content=json.dumps(result),
        status_code=status_code,
        media_type="application/json"
    )


@router.get("/health/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Kubernetes-style readiness probe.
    
    Checks if the application is ready to serve traffic.
    """
    health_checker = get_health_checker()
    result = await health_checker.check_readiness()
    
    status_code = status.HTTP_200_OK if result["ready"] else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return Response(
        content=json.dumps(result),
        status_code=status_code,
        media_type="application/json"
    )


@router.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """
    Kubernetes-style liveness probe.
    
    Simple check to verify the application is alive and responsive.
    """
    health_checker = get_health_checker()
    result = await health_checker.check_liveness()
    
    return result
