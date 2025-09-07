"""
Context Builder for AI Priority Engine.

Aggregates data from multiple sources to build rich context for priority decisions.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from db import fetch, fetchone
from metrics import compute_48h_metrics
from models.domain import MetricsData

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds rich context for priority decision making."""

    def __init__(self):
        self.cache = {}  # Simple in-memory cache for this session

    async def build_context(self, journey_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Build comprehensive context for priority engine.

        Args:
            journey_id: Optional specific journey ID, defaults to active journey

        Returns:
            Rich context dictionary with all relevant data
        """
        try:
            context = {
                # Layer 1: Current Activity (from existing /analyze endpoint logic)
                "metrics": await self._get_48h_metrics(),
                "recent_events": await self._get_recent_events(),

                # Layer 2: Issue Intelligence
                "active_issues": await self._get_enriched_issues(),
                "blocked_items": await self._get_blocked_context(),
                "pr_status": await self._get_pr_review_status(),

                # Layer 3: Journey Progress
                "journey": await self._get_journey_state(journey_id),
                "momentum": await self._calculate_momentum(),
                "patterns": await self._get_work_patterns(),

                # Layer 4: Temporal Context
                "time_context": self._get_time_context(),

                # Layer 5: Recent Recommendations (for learning)
                "recent_recommendations": await self._get_recent_recommendations(),
            }

            logger.info("Built context successfully")
            return context

        except Exception as e:
            logger.error(f"Failed to build context: {e}")
            return self._get_fallback_context()

    async def _get_48h_metrics(self) -> MetricsData:
        """Get 48h metrics using existing logic from /analyze endpoint."""
        try:
            # Reuse existing logic from main.py /analyze endpoint
            sql = """
                SELECT * FROM events
                WHERE ts >= NOW() - INTERVAL '48 hours'
                ORDER BY ts DESC
            """
            events = await fetch(sql)

            # Convert database rows to list of dicts
            converted_events = []
            for event in events:
                if hasattr(event, 'keys'):
                    event_dict = dict(event)
                else:
                    event_dict = event

                # Convert datetime objects to ISO strings
                if 'ts' in event_dict and hasattr(event_dict['ts'], 'isoformat'):
                    event_dict['ts'] = event_dict['ts'].isoformat()

                converted_events.append(event_dict)

            # Compute metrics
            metrics = compute_48h_metrics(converted_events)
            return metrics

        except Exception as e:
            logger.error(f"Failed to get 48h metrics: {e}")
            return MetricsData(
                prs_open_48h=0,
                prs_merged_48h=0,
                avg_review_hours_48h=0.0,
                tickets_moved_48h=0,
                tickets_blocked_now=0
            )

    async def _get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent events for context."""
        try:
            sql = """
                SELECT ts, source, actor, type, ref_id, title, url, meta
                FROM events
                ORDER BY ts DESC
                LIMIT %s
            """
            events = await fetch(sql, (limit,))

            converted_events = []
            for event in events:
                event_dict = dict(event)

                # Convert timestamp to ISO string
                if 'ts' in event_dict and hasattr(event_dict['ts'], 'isoformat'):
                    event_dict['ts'] = event_dict['ts'].isoformat()

                converted_events.append(event_dict)

            return converted_events

        except Exception as e:
            logger.error(f"Failed to get recent events: {e}")
            return []

    async def _get_enriched_issues(self) -> List[Dict[str, Any]]:
        """Get Linear issues with enriched context (blocked status, age, etc.)."""
        try:
            # For now, extract issue information from Linear events
            # TODO: Could be enhanced with direct Linear API calls for real-time state
            sql = """
                SELECT DISTINCT ON (ref_id)
                    ref_id, title, url, meta, ts,
                    EXTRACT(DAYS FROM NOW() - ts) as days_old
                FROM events
                WHERE source = 'linear'
                  AND type IN ('ISSUE_CREATED', 'ISSUE_UPDATED', 'ISSUE_STATE_CHANGED')
                  AND ts >= NOW() - INTERVAL '7 days'
                ORDER BY ref_id, ts DESC
            """

            issues = await fetch(sql)
            enriched_issues = []

            for issue in issues:
                issue_dict = dict(issue)

                # Extract status from metadata if available
                meta = issue_dict.get('meta', {})
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except json.JSONDecodeError:
                        meta = {}

                enriched_issue = {
                    "ref_id": issue_dict.get("ref_id"),
                    "title": issue_dict.get("title"),
                    "url": issue_dict.get("url"),
                    "days_old": float(issue_dict.get("days_old", 0)),
                    "last_updated": self._format_timestamp(issue_dict.get("ts")),
                    "priority": self._extract_priority_from_meta(meta),
                    "state": self._extract_state_from_meta(meta),
                }

                enriched_issues.append(enriched_issue)

            return enriched_issues

        except Exception as e:
            logger.error(f"Failed to get enriched issues: {e}")
            return []

    async def _get_blocked_context(self) -> List[Dict[str, Any]]:
        """Get context about blocked items."""
        try:
            sql = """
                SELECT ref_id, title, url, meta, ts
                FROM events
                WHERE source = 'linear'
                  AND type = 'ISSUE_BLOCKED'
                  AND ts >= NOW() - INTERVAL '7 days'
                ORDER BY ts DESC
            """

            blocked_events = await fetch(sql)
            blocked_items = []

            for event in blocked_events:
                event_dict = dict(event)
                blocked_items.append({
                    "ref_id": event_dict.get("ref_id"),
                    "title": event_dict.get("title"),
                    "url": event_dict.get("url"),
                    "blocked_since": self._format_timestamp(event_dict.get("ts")),
                    "reason": self._extract_blocked_reason(event_dict.get("meta", {}))
                })

            return blocked_items

        except Exception as e:
            logger.error(f"Failed to get blocked context: {e}")
            return []

    async def _get_pr_review_status(self) -> List[Dict[str, Any]]:
        """Get PR review status and aging information."""
        try:
            sql = """
                SELECT ref_id, title, url, meta, ts,
                       EXTRACT(HOURS FROM NOW() - ts) as hours_old
                FROM events
                WHERE source = 'github'
                  AND type = 'PullRequestEvent_opened'
                  AND ts >= NOW() - INTERVAL '7 days'
                ORDER BY ts DESC
            """

            prs = await fetch(sql)
            pr_status = []

            for pr in prs:
                pr_dict = dict(pr)
                pr_status.append({
                    "ref_id": pr_dict.get("ref_id"),
                    "title": pr_dict.get("title"),
                    "url": pr_dict.get("url"),
                    "hours_old": float(pr_dict.get("hours_old", 0)),
                    "needs_review": pr_dict.get("hours_old", 0) > 24,  # PRs older than 24h need attention
                    "opened_at": self._format_timestamp(pr_dict.get("ts"))
                })

            return pr_status

        except Exception as e:
            logger.error(f"Failed to get PR review status: {e}")
            return []

    async def _get_journey_state(self, journey_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current journey state."""
        try:
            if journey_id:
                sql = "SELECT * FROM user_journey WHERE id = %s"
                journey = await fetchone(sql, (journey_id,))
            else:
                sql = "SELECT * FROM user_journey WHERE is_active = true ORDER BY created_at DESC LIMIT 1"
                journey = await fetchone(sql)

            if journey:
                return {
                    "id": str(journey.get("id")),
                    "desired_state": journey.get("desired_state", {}),
                    "current_state": journey.get("current_state", {}),
                    "preferences": journey.get("preferences", {}),
                    "created_at": self._format_timestamp(journey.get("created_at")),
                    "updated_at": self._format_timestamp(journey.get("updated_at"))
                }
            else:
                return self._get_default_journey()

        except Exception as e:
            logger.error(f"Failed to get journey state: {e}")
            return self._get_default_journey()

    async def _calculate_momentum(self) -> Dict[str, Any]:
        """Calculate current momentum based on recent activity."""
        try:
            # Get activity from last 3 days vs previous 3 days
            recent_sql = """
                SELECT COUNT(*) as recent_count
                FROM events
                WHERE ts >= NOW() - INTERVAL '3 days'
            """

            previous_sql = """
                SELECT COUNT(*) as previous_count
                FROM events
                WHERE ts >= NOW() - INTERVAL '6 days'
                  AND ts < NOW() - INTERVAL '3 days'
            """

            recent = await fetchone(recent_sql)
            previous = await fetchone(previous_sql)

            recent_count = recent.get("recent_count", 0) if recent else 0
            previous_count = previous.get("previous_count", 0) if previous else 0

            if previous_count == 0:
                velocity_change = 1.0 if recent_count > 0 else 0.0
            else:
                velocity_change = recent_count / previous_count

            return {
                "recent_activity": recent_count,
                "previous_activity": previous_count,
                "velocity_change": velocity_change,
                "trend": "increasing" if velocity_change > 1.2 else "decreasing" if velocity_change < 0.8 else "stable"
            }

        except Exception as e:
            logger.error(f"Failed to calculate momentum: {e}")
            return {
                "recent_activity": 0,
                "previous_activity": 0,
                "velocity_change": 0.0,
                "trend": "unknown"
            }

    async def _get_work_patterns(self) -> Dict[str, Any]:
        """Analyze work patterns from historical data."""
        try:
            # Simple pattern analysis - when are most events created?
            sql = """
                SELECT
                    EXTRACT(HOUR FROM ts) as hour,
                    COUNT(*) as event_count
                FROM events
                WHERE ts >= NOW() - INTERVAL '30 days'
                GROUP BY EXTRACT(HOUR FROM ts)
                ORDER BY event_count DESC
                LIMIT 3
            """

            patterns = await fetch(sql)

            peak_hours = [int(p.get("hour", 9)) for p in patterns] if patterns else [9, 10, 14]

            return {
                "peak_hours": peak_hours,
                "most_productive_hour": peak_hours[0] if peak_hours else 9,
                "pattern_confidence": len(patterns) / 24.0 if patterns else 0.0
            }

        except Exception as e:
            logger.error(f"Failed to get work patterns: {e}")
            return {
                "peak_hours": [9, 10, 14],
                "most_productive_hour": 9,
                "pattern_confidence": 0.0
            }

    def _get_time_context(self) -> Dict[str, Any]:
        """Get current time context for decision making."""
        now = datetime.now(timezone.utc)

        # Convert to Pacific Time for user context
        # Note: This should be pulled from user preferences in a real system
        pacific_offset = timedelta(hours=-8)  # PST/PDT handling would be more complex
        local_time = now + pacific_offset

        return {
            "current_utc": now.isoformat(),
            "local_time": local_time.isoformat(),
            "hour_of_day": local_time.hour,
            "is_work_hours": 9 <= local_time.hour <= 17,
            "work_day_remaining": max(0, 17 - local_time.hour) if local_time.hour < 17 else 0,
            "energy_level": self._estimate_energy_level(local_time.hour),
            "day_of_week": local_time.strftime("%A"),
            "is_weekend": local_time.weekday() >= 5
        }

    async def _get_recent_recommendations(self) -> List[Dict[str, Any]]:
        """Get recent priority recommendations for learning context."""
        try:
            sql = """
                SELECT
                    id, created_at, recommendations, action_taken,
                    outcome, feedback_score
                FROM priority_recommendations
                ORDER BY created_at DESC
                LIMIT 5
            """

            recommendations = await fetch(sql)
            recent_recs = []

            for rec in recommendations:
                rec_dict = dict(rec)
                recent_recs.append({
                    "id": str(rec_dict.get("id")),
                    "created_at": self._format_timestamp(rec_dict.get("created_at")),
                    "recommendations": rec_dict.get("recommendations", {}),
                    "action_taken": rec_dict.get("action_taken"),
                    "outcome": rec_dict.get("outcome"),
                    "feedback_score": rec_dict.get("feedback_score")
                })

            return recent_recs

        except Exception as e:
            logger.error(f"Failed to get recent recommendations: {e}")
            return []

    def _extract_priority_from_meta(self, meta: Dict) -> str:
        """Extract priority level from event metadata."""
        if isinstance(meta, dict):
            # Look for common priority indicators in Linear metadata
            priority_mapping = {
                0: "none",
                1: "urgent",
                2: "high",
                3: "normal",
                4: "low"
            }

            priority_value = meta.get("priority", {}).get("value", 3) if meta.get("priority") else 3
            return priority_mapping.get(priority_value, "normal")

        return "normal"

    def _extract_state_from_meta(self, meta: Dict) -> str:
        """Extract issue state from metadata."""
        if isinstance(meta, dict) and meta.get("state"):
            return meta["state"].get("name", "unknown")
        return "unknown"

    def _extract_blocked_reason(self, meta: Dict) -> str:
        """Extract reason for being blocked from metadata."""
        if isinstance(meta, dict):
            return meta.get("blocked_reason", "No reason specified")
        return "No reason specified"

    def _estimate_energy_level(self, hour: int) -> str:
        """Estimate energy level based on time of day."""
        if 9 <= hour <= 11:
            return "high"
        elif 13 <= hour <= 15:
            return "medium"
        elif 16 <= hour <= 17:
            return "medium"
        else:
            return "low"

    def _get_default_journey(self) -> Dict[str, Any]:
        """Return default journey state if none exists."""
        return {
            "id": "default",
            "desired_state": {
                "role": "$200k+ Staff/Senior Role",
                "timeline": "3 months",
                "priorities": ["Build impressive portfolio", "Demonstrate system design skills"]
            },
            "current_state": {
                "status": "building_portfolio",
                "momentum": "high",
                "current_project": "Pulse AI Priority Engine"
            },
            "preferences": {
                "work_hours": "9:00-17:00",
                "energy_pattern": "morning_peak"
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

    def _get_fallback_context(self) -> Dict[str, Any]:
        """Return minimal context when building fails."""
        return {
            "metrics": {"prs_open_48h": 0, "prs_merged_48h": 0, "tickets_moved_48h": 0},
            "recent_events": [],
            "active_issues": [],
            "blocked_items": [],
            "pr_status": [],
            "journey": self._get_default_journey(),
            "momentum": {"trend": "unknown", "velocity_change": 0.0},
            "patterns": {"peak_hours": [9, 10, 14]},
            "time_context": self._get_time_context(),
            "recent_recommendations": []
        }

    def _format_timestamp(self, ts: Any) -> Optional[str]:
        """Helper to safely format timestamps for JSON serialization."""
        if ts is None:
            return None
        if hasattr(ts, 'isoformat'):
            return ts.isoformat()
        return str(ts) if ts else None
