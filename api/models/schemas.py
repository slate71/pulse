"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from .domain import (
    MetricsData, Event, JourneyState, PriorityRecommendation, 
    StandardErrorResponse, ValidationErrorResponse
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
    metrics: MetricsData
    events: List[Event]


class ReportResponse(BaseModel):
    focus_actions: List[str]
    kpis: Dict[str, Any]
    event_stream: List[Dict[str, Any]]


class PublicReportResponse(BaseModel):
    as_of: str
    metrics: MetricsData
    feedback: Optional[Dict[str, Any]]  # Keep flexible for now as it's sanitized data
    recent_events: List[Event]


# Use the domain model directly for priority recommendations
PriorityRecommendationResponse = PriorityRecommendation


class PriorityFeedbackRequest(BaseModel):
    recommendation_id: str
    action_taken: Optional[str] = None
    outcome: Optional[str] = None
    feedback_score: Optional[int] = None
    time_to_complete_minutes: Optional[int] = None


class JourneyStateResponse(BaseModel):
    """Journey state response with flexible typing for backward compatibility."""
    id: str
    desired_state: Dict[str, Any]
    current_state: Dict[str, Any]
    preferences: Dict[str, Any]
    created_at: str
    updated_at: str
