from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import json
import logging
from dotenv import load_dotenv
from db import health_check, fetch, fetchone
from github_ingest import ingest_github_events
from linear_ingest import ingest_linear
from metrics import compute_48h_metrics, filter_recent_events
from report import get_public_report
from rate_limiter import rate_limiter
from priority_engine import PriorityEngine

load_dotenv()

logger = logging.getLogger(__name__)


def parse_jsonb_field(field_value: Any) -> Dict[str, Any]:
    """Helper to parse JSONB fields that may come as strings from asyncpg."""
    if isinstance(field_value, str):
        try:
            return json.loads(field_value)
        except json.JSONDecodeError:
            return {}
    elif isinstance(field_value, dict):
        return field_value
    else:
        return {}

app = FastAPI(
    title="Pulse API",
    description="AI-powered engineering radar API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    version: str
    database: Dict[str, Any]


class IngestRequest(BaseModel):
    source: str
    events: List[Dict[str, Any]]


class GitHubIngestConfig(BaseModel):
    owner: str
    repo: str
    since_iso: Optional[str] = None


class IngestRunRequest(BaseModel):
    github: Optional[GitHubIngestConfig] = None
    linear: Optional[bool] = None


class IngestRunResponse(BaseModel):
    inserted: int
    skipped: int
    cursor: Optional[str] = None
    issues_processed: Optional[int] = None
    events_generated: Optional[int] = None
    sample: Optional[List[Dict[str, Any]]] = None


class AnalyzeResponse(BaseModel):
    metrics: Dict[str, Any]
    events: List[Dict[str, Any]]


class ReportResponse(BaseModel):
    focus_actions: List[str]
    kpis: Dict[str, Any]
    event_stream: List[Dict[str, Any]]


class PublicReportResponse(BaseModel):
    as_of: str
    metrics: Dict[str, Any]
    feedback: Optional[Dict[str, Any]]
    recent_events: List[Dict[str, Any]]


class PriorityRecommendationResponse(BaseModel):
    generated_at: str
    context_id: str
    primary_action: Dict[str, Any]
    alternatives: List[Dict[str, Any]]
    context_summary: str
    journey_alignment: str
    momentum_insight: str
    energy_match: str
    debug_info: Dict[str, Any]


class PriorityFeedbackRequest(BaseModel):
    recommendation_id: str
    action_taken: Optional[str] = None
    outcome: Optional[str] = None
    feedback_score: Optional[int] = None
    time_to_complete_minutes: Optional[int] = None


class JourneyStateResponse(BaseModel):
    id: str
    desired_state: Dict[str, Any]
    current_state: Dict[str, Any]
    preferences: Dict[str, Any]
    created_at: str
    updated_at: str


@app.get("/health", response_model=HealthResponse)
async def health_check_endpoint():
    # Check database connectivity
    db_status = await health_check()

    return HealthResponse(
        status="healthy" if db_status["status"] == "healthy" else "degraded",
        version="1.0.0",
        database=db_status
    )


@app.post("/ingest")
async def ingest_data(request: IngestRequest):
    # TODO: Implement data ingestion from GitHub and Linear
    # - Validate incoming event data
    # - Store events in database
    # - Queue for analysis if needed
    return {"message": f"Ingested {len(request.events)} events from {request.source}"}


@app.post("/ingest/run", response_model=IngestRunResponse)
async def run_ingest(request: IngestRunRequest, dryRun: bool = False):
    """
    Run data ingestion from configured sources.

    Currently supports:
    - GitHub: Fetch events from a repository
    - Linear: Fetch issues from a team
    """
    if not request.github and not request.linear:
        raise HTTPException(status_code=400, detail="No ingest sources specified")

    try:
        # Handle GitHub ingestion
        if request.github:
            result = await ingest_github_events(
                owner=request.github.owner,
                repo=request.github.repo,
                since_iso=request.github.since_iso
            )

            return IngestRunResponse(
                inserted=result["inserted"],
                skipped=result["skipped"]
            )

        # Handle Linear ingestion
        if request.linear:
            linear_api_key = os.getenv("LINEAR_API_KEY")
            linear_team_id = os.getenv("LINEAR_TEAM_ID")

            if not linear_api_key:
                raise HTTPException(
                    status_code=400,
                    detail="LINEAR_API_KEY environment variable is required"
                )

            if not linear_team_id:
                raise HTTPException(
                    status_code=400,
                    detail="LINEAR_TEAM_ID environment variable is required"
                )

            result = await ingest_linear(
                team_id=linear_team_id,
                api_key=linear_api_key,
                dry_run=dryRun
            )

            return IngestRunResponse(
                inserted=result["inserted"],
                skipped=result["skipped"],
                cursor=result.get("cursor"),
                issues_processed=result.get("issues_processed"),
                events_generated=result.get("events_generated"),
                sample=result.get("sample")
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"External service unavailable: {str(e)}")
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=f"Request timeout: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in ingest: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during ingestion")


@app.post("/analyze", response_model=AnalyzeResponse)
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


@app.get("/report", response_model=ReportResponse)
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


@app.get("/report/public", response_model=PublicReportResponse)
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
                "X-RateLimit-Limit": str(rate_info["limit"]),
                "X-RateLimit-Remaining": str(rate_info["remaining"]),
                "X-RateLimit-Reset": str(rate_info["reset"]),
                "Retry-After": str(rate_info["window"])
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


@app.post("/priority/generate", response_model=PriorityRecommendationResponse)
async def generate_priority_recommendation(journey_id: Optional[str] = None):
    """
    Generate AI-powered priority recommendation based on current context.
    
    Analyzes current activity, issues, journey state, and time context to
    recommend the optimal next action with detailed reasoning.
    """
    try:
        priority_engine = PriorityEngine()
        recommendation = await priority_engine.generate_recommendation(journey_id)
        
        # Store recommendation for learning
        await _store_recommendation(recommendation, journey_id)
        
        return PriorityRecommendationResponse(**recommendation)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate priority recommendation: {str(e)}"
        )


@app.post("/priority/feedback")
async def record_priority_feedback(feedback: PriorityFeedbackRequest):
    """
    Record feedback on a priority recommendation for learning.
    
    Tracks what action was actually taken, outcome, and user satisfaction
    to improve future recommendations.
    """
    try:
        # Convert time to PostgreSQL interval if provided
        time_interval = None
        if feedback.time_to_complete_minutes:
            time_interval = f"{feedback.time_to_complete_minutes} minutes"
        
        # Update recommendation with feedback
        sql = """
            UPDATE priority_recommendations 
            SET 
                action_taken = %s,
                outcome = %s,
                feedback_score = %s,
                time_to_complete = %s::interval,
                completed_at = NOW()
            WHERE context_snapshot->>'context_id' = %s
            RETURNING id
        """
        
        result = await fetchone(sql, (
            feedback.action_taken,
            feedback.outcome,
            feedback.feedback_score,
            time_interval,
            feedback.recommendation_id
        ))
        
        if not result:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        return {"message": "Feedback recorded successfully", "recommendation_id": str(result.get("id"))}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to record feedback: {str(e)}"
        )


@app.get("/journey/state", response_model=JourneyStateResponse)
async def get_journey_state(journey_id: Optional[str] = None):
    """
    Get current journey state and progress.
    
    Returns user's desired state, current status, and preferences
    for context-aware priority recommendations.
    """
    try:
        if journey_id:
            sql = "SELECT * FROM user_journey WHERE id = %s"
            journey = await fetchone(sql, (journey_id,))
        else:
            sql = "SELECT * FROM user_journey WHERE is_active = true ORDER BY created_at DESC LIMIT 1"
            journey = await fetchone(sql)
        
        if not journey:
            raise HTTPException(status_code=404, detail="Journey not found")
        
        # Parse JSONB fields that come as strings from asyncpg
        desired_state = parse_jsonb_field(journey.get("desired_state", {}))
        current_state = parse_jsonb_field(journey.get("current_state", {}))
        preferences = parse_jsonb_field(journey.get("preferences", {}))
        
        return JourneyStateResponse(
            id=str(journey.get("id")),
            desired_state=desired_state,
            current_state=current_state,
            preferences=preferences,
            created_at=journey.get("created_at").isoformat() if hasattr(journey.get("created_at"), 'isoformat') else str(journey.get("created_at")),
            updated_at=journey.get("updated_at").isoformat() if hasattr(journey.get("updated_at"), 'isoformat') else str(journey.get("updated_at"))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get journey state: {str(e)}"
        )


async def _store_recommendation(recommendation: Dict[str, Any], journey_id: Optional[str] = None):
    """Store recommendation in database for learning."""
    try:
        # Get journey ID if not provided
        if not journey_id:
            sql = "SELECT id FROM user_journey WHERE is_active = true ORDER BY created_at DESC LIMIT 1"
            journey = await fetchone(sql)
            journey_id = str(journey.get("id")) if journey else None
        
        # Store recommendation with full context
        sql = """
            INSERT INTO priority_recommendations (
                journey_id, context_snapshot, recommendations
            ) VALUES (%s, %s, %s)
            RETURNING id
        """
        
        context_snapshot = {
            "context_id": recommendation.get("context_id"),
            "generated_at": recommendation.get("generated_at"),
            "debug_info": recommendation.get("debug_info", {})
        }
        
        recommendations_data = {
            "primary_action": recommendation.get("primary_action"),
            "alternatives": recommendation.get("alternatives"),
            "context_summary": recommendation.get("context_summary"),
            "journey_alignment": recommendation.get("journey_alignment"),
            "momentum_insight": recommendation.get("momentum_insight"),
            "energy_match": recommendation.get("energy_match")
        }
        
        result = await fetchone(sql, (journey_id, context_snapshot, recommendations_data))
        return str(result.get("id")) if result else None
        
    except Exception as e:
        # Log error but don't fail the main request
        import logging
        logging.error(f"Failed to store recommendation: {e}")
        return None


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "localhost")
    port = int(os.getenv("API_PORT", 8000))

    uvicorn.run(app, host=host, port=port, reload=True)
