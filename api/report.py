"""
Public report module for generating read-only public reports.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from db import fetchone, fetch

logger = logging.getLogger(__name__)


async def get_public_report() -> Dict[str, Any]:
    """
    Generate a public report with latest metrics, feedback, and recent events.
    
    Strips all sensitive information and internal metadata before returning.
    
    Returns:
        Dict containing public report data with metrics, feedback, and recent events
    """
    try:
        report = {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "metrics": await _get_latest_metrics(),
            "feedback": await _get_latest_feedback(),
            "recent_events": await _get_recent_events_public()
        }
        
        logger.info("Generated public report successfully")
        return report
        
    except Exception as e:
        logger.error(f"Failed to generate public report: {e}")
        # Return safe defaults on error
        return {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "metrics": _get_default_metrics(),
            "feedback": None,
            "recent_events": []
        }


async def _get_latest_metrics() -> Dict[str, Any]:
    """
    Get the most recent metrics from metrics_daily table.
    
    Returns:
        Dict with latest metrics or default values if none exist
    """
    try:
        result = await fetchone(
            """
            SELECT prs_open, prs_merged, avg_pr_review_hours, 
                   tickets_moved, tickets_blocked, as_of_date
            FROM metrics_daily 
            ORDER BY as_of_date DESC 
            LIMIT 1
            """
        )
        
        if result:
            return {
                "prs_open_48h": result.get("prs_open", 0),
                "prs_merged_48h": result.get("prs_merged", 0),
                "avg_review_hours_48h": float(result.get("avg_pr_review_hours", 0.0)),
                "tickets_moved_48h": result.get("tickets_moved", 0),
                "tickets_blocked_now": result.get("tickets_blocked", 0)
            }
        else:
            return _get_default_metrics()
            
    except Exception as e:
        logger.error(f"Failed to fetch latest metrics: {e}")
        return _get_default_metrics()


def _get_default_metrics() -> Dict[str, Any]:
    """Return default/empty metrics structure."""
    return {
        "prs_open_48h": 0,
        "prs_merged_48h": 0,
        "avg_review_hours_48h": 0.0,
        "tickets_moved_48h": 0,
        "tickets_blocked_now": 0
    }


async def _get_latest_feedback() -> Optional[Dict[str, Any]]:
    """
    Get the most recent feedback from feedback table and parse LLM JSON.
    
    Returns:
        Parsed feedback object or None if no valid feedback exists
    """
    try:
        result = await fetchone(
            """
            SELECT llm_json, as_of_ts
            FROM feedback 
            ORDER BY as_of_ts DESC 
            LIMIT 1
            """
        )
        
        if not result:
            return None
            
        llm_json = result.get("llm_json")
        if not llm_json:
            return None
            
        # Parse LLM JSON - handle both JSONB and string cases
        if isinstance(llm_json, dict):
            feedback_data = llm_json
        elif isinstance(llm_json, str):
            try:
                feedback_data = json.loads(llm_json)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in feedback.llm_json field")
                return None
        else:
            logger.warning(f"Unexpected llm_json type: {type(llm_json)}")
            return None
            
        # Validate and sanitize feedback structure
        sanitized = _sanitize_feedback(feedback_data)
        return sanitized
        
    except Exception as e:
        logger.error(f"Failed to fetch latest feedback: {e}")
        return None


def _sanitize_feedback(feedback_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize feedback data for public consumption.
    
    Args:
        feedback_data: Raw feedback data from LLM
        
    Returns:
        Sanitized feedback data safe for public consumption
    """
    sanitized: Dict[str, Any] = {}
    
    # Extract summary
    if "summary" in feedback_data and isinstance(feedback_data["summary"], str):
        sanitized["summary"] = feedback_data["summary"]
    else:
        sanitized["summary"] = "No summary available"
    
    # Extract today_focus actions
    today_focus = feedback_data.get("today_focus", [])
    if isinstance(today_focus, list):
        sanitized_focus = []
        for item in today_focus:
            if isinstance(item, dict):
                focus_item = {}
                if "action" in item and isinstance(item["action"], str):
                    focus_item["action"] = item["action"]
                if "why" in item and isinstance(item["why"], str):
                    focus_item["why"] = item["why"]
                if "evidence" in item and isinstance(item["evidence"], str):
                    focus_item["evidence"] = item["evidence"]
                
                # Only include if we have at least action
                if "action" in focus_item:
                    sanitized_focus.append(focus_item)
        
        sanitized["today_focus"] = sanitized_focus
    else:
        sanitized["today_focus"] = []
    
    # Extract risks
    risks = feedback_data.get("risks", [])
    if isinstance(risks, list):
        sanitized_risks = []
        for item in risks:
            if isinstance(item, dict):
                risk_item = {}
                if "risk" in item and isinstance(item["risk"], str):
                    risk_item["risk"] = item["risk"]
                if "evidence" in item and isinstance(item["evidence"], str):
                    risk_item["evidence"] = item["evidence"]
                
                # Only include if we have at least risk
                if "risk" in risk_item:
                    sanitized_risks.append(risk_item)
        
        sanitized["risks"] = sanitized_risks
    else:
        sanitized["risks"] = []
    
    return sanitized


async def _get_recent_events_public() -> List[Dict[str, Any]]:
    """
    Get recent events with all sensitive information stripped.
    
    Returns:
        List of sanitized event dictionaries safe for public consumption
    """
    try:
        events = await fetch(
            """
            SELECT ts, source, actor, type, title, url
            FROM events 
            ORDER BY ts DESC 
            LIMIT 50
            """
        )
        
        sanitized_events = []
        for event in events:
            # Convert timestamp to ISO string if needed
            ts = event.get("ts")
            if ts is not None and hasattr(ts, "isoformat"):
                ts = ts.isoformat()
            
            # Sanitize event data - remove any potential sensitive info
            sanitized_event = {
                "ts": ts,
                "source": event.get("source"),
                "actor": _sanitize_actor(event.get("actor")),
                "type": _sanitize_event_type(event.get("type")),
                "title": _sanitize_title(event.get("title")),
                "url": _sanitize_url(event.get("url"))
            }
            
            # Only include events with required fields
            if sanitized_event["ts"] and sanitized_event["source"]:
                sanitized_events.append(sanitized_event)
        
        return sanitized_events
        
    except Exception as e:
        logger.error(f"Failed to fetch recent events: {e}")
        return []


def _sanitize_actor(actor: Optional[str]) -> Optional[str]:
    """Sanitize actor name for public consumption."""
    if not actor or not isinstance(actor, str):
        return None
    
    # Remove any potential sensitive prefixes/suffixes
    # Keep basic GitHub/Linear usernames but strip anything that looks like internal IDs
    sanitized_actor = actor.strip()
    
    # Basic validation - should look like a reasonable username
    if len(sanitized_actor) > 50 or len(sanitized_actor) < 1:
        return None
        
    return sanitized_actor


def _sanitize_event_type(event_type: Optional[str]) -> Optional[str]:
    """Sanitize event type for public consumption."""
    if not event_type or not isinstance(event_type, str):
        return None
        
    # Convert internal event types to public-friendly names
    type_mapping = {
        "PullRequestEvent_opened": "PR_OPENED",
        "PullRequestEvent_closed": "PR_CLOSED", 
        "PullRequestEvent_merged": "PR_MERGED",
        "PushEvent": "PUSH",
        "ISSUE_CREATED": "ISSUE_CREATED",
        "ISSUE_UPDATED": "ISSUE_UPDATED",
        "ISSUE_STATE_CHANGED": "ISSUE_STATE_CHANGED",
        "ISSUE_BLOCKED": "ISSUE_BLOCKED",
        "ISSUE_UNBLOCKED": "ISSUE_UNBLOCKED"
    }
    
    return type_mapping.get(event_type, event_type)


def _sanitize_title(title: Optional[str]) -> Optional[str]:
    """Sanitize event title for public consumption."""
    if not title or not isinstance(title, str):
        return None
    
    # Truncate very long titles and strip whitespace
    sanitized_title = title.strip()
    if len(sanitized_title) > 200:
        sanitized_title = sanitized_title[:197] + "..."
    
    return sanitized_title if sanitized_title else None


def _sanitize_url(url: Optional[str]) -> Optional[str]:
    """Sanitize URL for public consumption."""
    if not url or not isinstance(url, str):
        return None
    
    # Basic URL validation - should start with https://
    url = url.strip()
    if not url.startswith(("https://github.com/", "https://linear.app/", "https://app.linear.app/")):
        # Only allow known safe public URLs
        return None
    
    return url
