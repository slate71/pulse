"""
Metrics computation module for analyzing events data.

Provides functions to compute engineering metrics from events data.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List


def compute_48h_metrics(events: List[Dict]) -> Dict:
    """
    Compute metrics from events in the last 48 hours.
    
    Args:
        events: List of event dictionaries with schema fields:
                - ts: ISO timestamp string
                - source: 'github' or 'linear'
                - type: event type (e.g., 'PullRequestEvent_opened')
                - actor: username
                - ref_id: reference ID
                - title: event title
                - url: event URL
                - meta: raw event data
    
    Returns:
        Dict with metrics:
        - prs_open_48h: Number of PRs opened in last 48h
        - prs_merged_48h: Number of PRs merged in last 48h  
        - avg_review_hours_48h: Average review time in hours (TODO - stub for now)
        - tickets_moved_48h: Number of tickets moved in last 48h (Linear events)
        - tickets_blocked_now: Number of tickets currently blocked (Linear events)
    """
    # Calculate 48 hours ago from now
    now = datetime.now(timezone.utc)
    cutoff_48h = now - timedelta(hours=48)
    
    # Initialize metrics
    metrics = {
        "prs_open_48h": 0,
        "prs_merged_48h": 0, 
        "avg_review_hours_48h": 0.0,  # TODO: implement when we have review data
        "tickets_moved_48h": 0,       # TODO: implement for Linear events
        "tickets_blocked_now": 0      # TODO: implement for Linear events
    }
    
    # Filter events to last 48 hours and process
    for event in events:
        # Parse event timestamp
        ts_str = event.get('ts')
        if not ts_str:
            continue
            
        try:
            # Handle both 'Z' and '+00:00' timezone formats
            if ts_str.endswith('Z'):
                # Remove Z and add +00:00, but only if it doesn't already have timezone info
                if '+' not in ts_str and '-' not in ts_str[10:]:  # Check for timezone after the date part
                    event_dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                else:
                    # Already has timezone info, just remove Z
                    event_dt = datetime.fromisoformat(ts_str[:-1])
            else:
                event_dt = datetime.fromisoformat(ts_str)
                
            # Ensure timezone-aware datetime
            if event_dt.tzinfo is None:
                event_dt = event_dt.replace(tzinfo=timezone.utc)
                
        except (ValueError, TypeError):
            # Skip events with invalid timestamps
            continue
        
        # Skip events older than 48 hours
        if event_dt < cutoff_48h:
            continue
            
        # Process GitHub events
        source = event.get('source', '')
        event_type = event.get('type', '')
        
        if source == 'github':
            if event_type == 'PullRequestEvent_opened':
                metrics["prs_open_48h"] += 1
            elif event_type in ['PullRequestEvent_closed', 'PullRequestEvent_merged']:
                # Check if it was actually merged (not just closed)
                meta = event.get('meta', {})
                if isinstance(meta, dict):
                    payload = meta.get('payload', {})
                    pr = payload.get('pull_request', {})
                    if pr.get('merged', False):
                        metrics["prs_merged_48h"] += 1
                elif event_type == 'PullRequestEvent_merged':
                    # If event type explicitly says merged
                    metrics["prs_merged_48h"] += 1
                    
        elif source == 'linear':
            # TODO: Implement Linear ticket metrics when we have Linear events
            # For now, these remain at 0
            pass
    
    return metrics


def filter_recent_events(events: List[Dict], limit: int = 50) -> List[Dict]:
    """
    Filter and return the most recent events, sorted by timestamp descending.
    
    Args:
        events: List of event dictionaries
        limit: Maximum number of events to return
        
    Returns:
        List of most recent events, sorted newest first
    """
    # Sort events by timestamp descending (newest first)
    def parse_timestamp(event):
        ts_str = event.get('ts', '')
        try:
            if ts_str.endswith('Z'):
                return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(ts_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
        except (ValueError, TypeError):
            # Return epoch for invalid timestamps (will be sorted last)
            return datetime.fromtimestamp(0, tz=timezone.utc)
    
    sorted_events = sorted(events, key=parse_timestamp, reverse=True)
    return sorted_events[:limit]