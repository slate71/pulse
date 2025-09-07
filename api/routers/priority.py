"""
Priority recommendation and journey management router.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from models.schemas import (
    PriorityRecommendationResponse,
    PriorityFeedbackRequest,
    JourneyStateResponse
)
from db import fetchone
from priority_engine import PriorityEngine
from utils.helpers import parse_jsonb_field, store_recommendation

router = APIRouter(tags=["priority"])


@router.post("/priority/generate", response_model=PriorityRecommendationResponse)
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
        await store_recommendation(recommendation, journey_id)
        
        return PriorityRecommendationResponse(**recommendation)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate priority recommendation: {str(e)}"
        )


@router.post("/priority/feedback")
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


@router.get("/journey/state", response_model=JourneyStateResponse)
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
        
        # Handle datetime fields safely
        created_at = journey.get("created_at")
        updated_at = journey.get("updated_at")
        
        return JourneyStateResponse(
            id=str(journey.get("id")),
            desired_state=desired_state,
            current_state=current_state,
            preferences=preferences,
            created_at=created_at.isoformat() if created_at and hasattr(created_at, 'isoformat') else str(created_at or ""),
            updated_at=updated_at.isoformat() if updated_at and hasattr(updated_at, 'isoformat') else str(updated_at or "")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get journey state: {str(e)}"
        )