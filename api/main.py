from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
from db import health_check
from github_ingest import ingest_github_events

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
    insights: List[str]


class ReportResponse(BaseModel):
    focus_actions: List[str]
    kpis: Dict[str, Any]
    event_stream: List[Dict[str, Any]]


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


@app.get("/analyze", response_model=AnalyzeResponse)
async def analyze_metrics():
    # TODO: Implement metric computation and analysis
    # - Query recent events from database
    # - Compute execution metrics (velocity, cycle time, etc.)
    # - Generate insights from patterns
    return AnalyzeResponse(
        metrics={"placeholder": "implementation_needed"},
        insights=["TODO: Implement metric analysis"]
    )


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


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "localhost")
    port = int(os.getenv("API_PORT", 8000))

    uvicorn.run(app, host=host, port=port, reload=True)
