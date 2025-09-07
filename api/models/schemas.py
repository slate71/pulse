"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


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