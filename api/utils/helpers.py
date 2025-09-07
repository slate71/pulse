"""
Utility helper functions for the API.
"""

import json
import logging
from typing import Dict, Any, Optional
from db import fetchone

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


async def store_recommendation(recommendation: Dict[str, Any], journey_id: Optional[str] = None):
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
        logger.error(f"Failed to store recommendation: {e}")
        return None
