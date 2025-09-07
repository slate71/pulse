"""
Domain-specific Pydantic models for type safety.

These models replace Dict[str, Any] usage with proper validation.
"""

from datetime import datetime
from typing import Optional, List, Literal, Union, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


# === Event Models ===

class EventSource(str, Enum):
    GITHUB = "github"
    LINEAR = "linear"


class GitHubEventType(str, Enum):
    PULL_REQUEST_OPENED = "PullRequestEvent_opened"
    PULL_REQUEST_CLOSED = "PullRequestEvent_closed"
    PULL_REQUEST_MERGED = "PullRequestEvent_merged"
    PUSH_EVENT = "PushEvent"


class LinearEventType(str, Enum):
    ISSUE_CREATED = "ISSUE_CREATED"
    ISSUE_UPDATED = "ISSUE_UPDATED"
    ISSUE_STATE_CHANGED = "ISSUE_STATE_CHANGED"
    ISSUE_BLOCKED = "ISSUE_BLOCKED"
    ISSUE_UNBLOCKED = "ISSUE_UNBLOCKED"


class EventMetadata(BaseModel):
    """Base metadata for all events."""
    raw_payload: Optional[dict] = Field(None, description="Raw API response")
    event_type: Optional[str] = Field(None, description="Original event type")


class GitHubMetadata(EventMetadata):
    """GitHub-specific metadata."""
    pull_request: Optional[dict] = None
    repository: Optional[dict] = None
    merged: Optional[bool] = None


class LinearMetadata(EventMetadata):
    """Linear-specific metadata."""
    state: Optional[dict] = None
    priority: Optional[dict] = None
    labels: Optional[List[dict]] = None
    blocked_reason: Optional[str] = None


class Event(BaseModel):
    """Standardized event model."""
    ts: datetime = Field(..., description="Event timestamp")
    source: EventSource = Field(..., description="Event source")
    actor: Optional[str] = Field(None, description="Actor username")
    type: str = Field(..., description="Event type")
    ref_id: str = Field(..., description="Reference ID (PR number, issue ID)")
    title: Optional[str] = Field(None, description="Event title")
    url: Optional[str] = Field(None, description="Event URL")
    meta: dict = Field(default_factory=dict, description="Event-specific metadata")

    @validator('type')
    def validate_event_type(cls, v, values):
        """Validate event type matches source."""
        source = values.get('source')
        if source == EventSource.GITHUB:
            valid_types = [e.value for e in GitHubEventType]
            if v not in valid_types and not v.startswith('PullRequestEvent_'):
                # Allow unknown GitHub events but warn
                pass
        elif source == EventSource.LINEAR:
            valid_types = [e.value for e in LinearEventType]
            if v not in valid_types:
                # Allow unknown Linear events but warn
                pass
        return v


# === Metric Models ===

class MetricsData(BaseModel):
    """48-hour engineering metrics."""
    prs_open_48h: int = Field(ge=0, description="PRs opened in last 48h")
    prs_merged_48h: int = Field(ge=0, description="PRs merged in last 48h")
    avg_review_hours_48h: float = Field(ge=0.0, description="Average review time in hours")
    tickets_moved_48h: int = Field(ge=0, description="Tickets moved in last 48h")
    tickets_blocked_now: int = Field(ge=0, description="Currently blocked tickets")


# === Journey Models ===

class Priority(str, Enum):
    NONE = "none"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class DesiredState(BaseModel):
    """User's desired career state."""
    role: str = Field(..., description="Target role")
    timeline: str = Field(..., description="Target timeline")
    priorities: List[str] = Field(default_factory=list, description="Key priorities")


class CurrentState(BaseModel):
    """User's current state."""
    status: str = Field(..., description="Current status")
    momentum: str = Field(..., description="Current momentum level")
    current_project: Optional[str] = Field(None, description="Current main project")


class UserPreferences(BaseModel):
    """User work preferences."""
    work_hours: str = Field(default="9:00-17:00", description="Preferred work hours")
    energy_pattern: str = Field(default="morning_peak", description="Energy pattern")


class JourneyState(BaseModel):
    """Complete user journey state."""
    id: str = Field(..., description="Journey ID")
    desired_state: DesiredState = Field(..., description="Target state")
    current_state: CurrentState = Field(..., description="Current state")
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    is_active: bool = Field(default=True, description="Whether journey is active")


# === Priority Engine Models ===

class PriorityAction(BaseModel):
    """Single priority action recommendation."""
    action: str = Field(..., description="Recommended action")
    why: str = Field(..., description="Reasoning for recommendation")
    expected_impact: float = Field(ge=0.0, le=1.0, description="Expected impact score")
    time_estimate: str = Field(..., description="Estimated time required")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in recommendation")
    urgency: float = Field(ge=0.0, le=1.0, description="Urgency score")
    importance: float = Field(ge=0.0, le=1.0, description="Importance score")
    when_to_consider: Optional[str] = Field(None, description="When to consider this action")


class DebugInfo(BaseModel):
    """Debug information for priority recommendations."""
    total_actions_considered: int = Field(default=0, ge=0, description="Total actions evaluated")
    context_layers: List[str] = Field(default_factory=list, description="Context layers used")
    ai_reasoning_used: bool = Field(default=False, description="Whether AI reasoning was used")
    context_id: Optional[str] = Field(None, description="Context identifier")
    generation_time_ms: Optional[float] = Field(None, description="Generation time in milliseconds")


class PriorityRecommendation(BaseModel):
    """Complete priority recommendation."""
    generated_at: datetime = Field(..., description="Generation timestamp")
    context_id: str = Field(..., description="Context identifier")
    primary_action: PriorityAction = Field(..., description="Primary recommended action")
    alternatives: List[PriorityAction] = Field(default_factory=list, description="Alternative actions")
    context_summary: str = Field(..., description="Context summary")
    journey_alignment: str = Field(..., description="Journey alignment assessment")
    momentum_insight: str = Field(..., description="Momentum analysis")
    energy_match: str = Field(..., description="Energy level match")
    debug_info: Optional[DebugInfo] = Field(default=None, description="Debug information")


# === Context Models ===

class EnrichedIssue(BaseModel):
    """Enriched Linear issue with context."""
    ref_id: str = Field(..., description="Issue reference ID")
    title: Optional[str] = Field(None, description="Issue title")
    url: Optional[str] = Field(None, description="Issue URL")
    days_old: float = Field(ge=0.0, description="Days since creation")
    last_updated: Optional[str] = Field(None, description="Last update timestamp")
    priority: Priority = Field(default=Priority.NORMAL, description="Issue priority")
    state: str = Field(default="unknown", description="Issue state")


class BlockedItem(BaseModel):
    """Blocked item context."""
    ref_id: str = Field(..., description="Item reference ID")
    title: Optional[str] = Field(None, description="Item title")
    url: Optional[str] = Field(None, description="Item URL")
    blocked_since: Optional[str] = Field(None, description="When item was blocked")
    reason: str = Field(default="No reason specified", description="Blocked reason")


class PRStatus(BaseModel):
    """Pull request status."""
    ref_id: str = Field(..., description="PR reference ID")
    title: Optional[str] = Field(None, description="PR title")
    url: Optional[str] = Field(None, description="PR URL")
    hours_old: float = Field(ge=0.0, description="Hours since opened")
    needs_review: bool = Field(default=False, description="Whether PR needs review")
    opened_at: Optional[str] = Field(None, description="When PR was opened")


class MomentumData(BaseModel):
    """Momentum calculation data."""
    recent_activity: int = Field(ge=0, description="Recent activity count")
    previous_activity: int = Field(ge=0, description="Previous period activity")
    velocity_change: float = Field(description="Velocity change ratio")
    trend: Literal["increasing", "decreasing", "stable", "unknown"] = Field(
        description="Activity trend"
    )


class WorkPatterns(BaseModel):
    """Work pattern analysis."""
    peak_hours: List[int] = Field(default_factory=list, description="Most active hours")
    most_productive_hour: int = Field(ge=0, le=23, description="Most productive hour")
    pattern_confidence: float = Field(ge=0.0, le=1.0, description="Pattern confidence")


class TimeContext(BaseModel):
    """Time-based context."""
    current_utc: str = Field(..., description="Current UTC time")
    local_time: str = Field(..., description="Local time")
    hour_of_day: int = Field(ge=0, le=23, description="Current hour")
    is_work_hours: bool = Field(description="Whether in work hours")
    work_day_remaining: int = Field(ge=0, description="Work hours remaining")
    energy_level: Literal["low", "medium", "high"] = Field(description="Estimated energy level")
    day_of_week: str = Field(..., description="Day of week")
    is_weekend: bool = Field(description="Whether it's weekend")


class RecentRecommendation(BaseModel):
    """Recent recommendation for context."""
    id: str = Field(..., description="Recommendation ID")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    recommendations: dict = Field(default_factory=dict, description="Recommendation data")
    action_taken: Optional[str] = Field(None, description="Action taken by user")
    outcome: Optional[str] = Field(None, description="Outcome of action")
    feedback_score: Optional[int] = Field(None, ge=1, le=5, description="User feedback score")


class ContextData(BaseModel):
    """Complete context for priority engine."""
    metrics: MetricsData = Field(..., description="48-hour metrics")
    recent_events: List[Event] = Field(default_factory=list, description="Recent events")
    active_issues: List[EnrichedIssue] = Field(default_factory=list, description="Active issues")
    blocked_items: List[BlockedItem] = Field(default_factory=list, description="Blocked items")
    pr_status: List[PRStatus] = Field(default_factory=list, description="PR status")
    journey: JourneyState = Field(..., description="User journey state")
    momentum: MomentumData = Field(..., description="Momentum data")
    patterns: WorkPatterns = Field(..., description="Work patterns")
    time_context: TimeContext = Field(..., description="Time context")
    recent_recommendations: List[RecentRecommendation] = Field(
        default_factory=list, 
        description="Recent recommendations"
    )


# === Error Models ===

class ErrorDetail(BaseModel):
    """Detailed error information."""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    field: Optional[str] = Field(None, description="Field that caused error")


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    detail: str = Field(..., description="Error summary")
    errors: List[ErrorDetail] = Field(..., description="Detailed errors")


class StandardErrorResponse(BaseModel):
    """Standard error response."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Application error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


# === Rate Limiting Models ===

class RateLimitInfo(BaseModel):
    """Rate limiting information."""
    limit: int = Field(..., description="Rate limit")
    remaining: int = Field(..., description="Remaining requests")
    reset: int = Field(..., description="Reset timestamp")
    window: int = Field(..., description="Time window in seconds")


class RateLimitStats(BaseModel):
    """Rate limiter statistics."""
    active_ips: int = Field(ge=0, description="Number of active IPs")
    total_requests_last_hour: int = Field(ge=0, description="Total requests in last hour")
    last_cleanup: float = Field(..., description="Last cleanup timestamp")