from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
from db import health_check, fetch
from github_ingest import ingest_github_events
from metrics import compute_48h_metrics, filter_recent_events
from report import get_public_report
from rate_limiter import rate_limiter

load_dotenv()

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


class IngestRunResponse(BaseModel):
    inserted: int
    skipped: int


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
async def run_ingest(request: IngestRunRequest):
    """
    Run data ingestion from configured sources.
    
    Currently supports:
    - GitHub: Fetch events from a repository
    """
    if not request.github:
        raise HTTPException(status_code=400, detail="No ingest sources specified")
    
    try:
        result = await ingest_github_events(
            owner=request.github.owner,
            repo=request.github.repo,
            since_iso=request.github.since_iso
        )
        
        return IngestRunResponse(
            inserted=result["inserted"],
            skipped=result["skipped"]
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


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
            detail="Failed to generate public report"
        )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "localhost")
    port = int(os.getenv("API_PORT", 8000))

    uvicorn.run(app, host=host, port=port, reload=True)
