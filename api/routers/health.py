"""
Health check router.
"""

from fastapi import APIRouter
from models.schemas import HealthResponse
from db import health_check

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check_endpoint():
    # Check database connectivity
    db_status = await health_check()

    return HealthResponse(
        status="healthy" if db_status["status"] == "healthy" else "degraded",
        version="1.0.0",
        database=db_status
    )