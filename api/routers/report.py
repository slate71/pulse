"""
Report and analysis router.
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from models.schemas import AnalyzeResponse, ReportResponse, PublicReportResponse
from db import fetch
from metrics import compute_48h_metrics, filter_recent_events
from report import get_public_report
from rate_limiter import rate_limiter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["report"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_metrics():
    """
    Analyze metrics from recent events.

    Queries events from the last 48 hours, computes engineering metrics,
    and returns metrics along with the 50 most recent events.
    """
    try:
        # Query last 48 hours of events from database
        sql = """
            SELECT * FROM events
            WHERE ts >= NOW() - INTERVAL '48 hours'
            ORDER BY ts DESC
        """
        events = await fetch(sql)

        # Convert database rows to list of dicts and handle datetime objects
        converted_events = []
        for event in events:
            if hasattr(event, 'keys'):
                # Convert asyncpg Record to dict
                event_dict = dict(event)
            else:
                event_dict = event

            # Convert datetime objects to ISO strings for JSON serialization
            if 'ts' in event_dict and hasattr(event_dict['ts'], 'isoformat'):
                event_dict['ts'] = event_dict['ts'].isoformat()

            converted_events.append(event_dict)

        events = converted_events

        # Compute 48h metrics
        metrics = compute_48h_metrics(events)

        # Get 50 most recent events
        recent_events = filter_recent_events(events, limit=50)

        return AnalyzeResponse(
            metrics=metrics,
            events=recent_events
        )

    except Exception as e:
        logger.error(f"Unexpected error in analyze: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during analysis")


@router.get("/report", response_model=ReportResponse)
async def generate_report():
    # TODO: Implement AI-powered report generation
    # - Fetch analyzed metrics
    # - Use OpenAI API to generate focus actions
    # - Return structured report data
    return ReportResponse(
        focus_actions=["TODO: Implement AI focus actions"],
        kpis={"placeholder": "implementation_needed"},
        event_stream=[]
    )


@router.get("/report/public", response_model=PublicReportResponse)
async def get_public_report_endpoint(request: Request):
    """
    Get public report with latest metrics, feedback, and recent events.

    This is a read-only endpoint with no authentication required.
    Rate limited to 5 requests per minute per IP.

    Returns:
        Public report with sanitized data safe for public consumption
    """
    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # Apply rate limiting (5 requests per minute)
    is_allowed, rate_info = rate_limiter.is_allowed(client_ip, limit=5, window_seconds=60)

    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 5 requests per minute.",
            headers={
                "X-RateLimit-Limit": str(rate_info.limit),
                "X-RateLimit-Remaining": str(rate_info.remaining),
                "X-RateLimit-Reset": str(rate_info.reset),
                "Retry-After": str(rate_info.window)
            }
        )

    try:
        # Generate public report
        report_data = await get_public_report()

        # Add rate limit headers to successful responses
        response = PublicReportResponse(**report_data)

        # Note: FastAPI doesn't support adding headers directly to response models,
        # but the rate limiting info is logged for monitoring
        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate public report: {str(e)}"
        )
