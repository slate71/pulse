"""
Linear ingest module for fetching issues from Linear API and storing them in the database.
"""

import os
import httpx
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from db import exec, fetchval, fetchone, insert_event

logger = logging.getLogger(__name__)

# GraphQL queries
WORKFLOW_STATES_QUERY = """
query WorkflowStates($teamId: String!) {
  team(id: $teamId) {
    states {
      nodes {
        id
        name
        type
      }
    }
  }
}
"""

ISSUES_QUERY = """
query Issues($teamId: String!, $updatedAfter: DateTime!, $after: String) {
  issues(
    filter: { team: { id: { eq: $teamId } }, updatedAt: { gt: $updatedAfter } }
    orderBy: updatedAt
    first: 50
    after: $after
  ) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      id
      identifier
      title
      url
      createdAt
      updatedAt
      state {
        id
        name
        type
      }
      previousIdentifiers
      branchName
      priority
      assignees {
        nodes {
          id
          name
          displayName
        }
      }
      labels {
        nodes {
          id
          name
        }
      }
    }
  }
}
"""


async def get_cursor(key: str, default_hours_ago: int = 72) -> str:
    """
    Get cursor value from ingest_cursors table.
    
    Args:
        key: Cursor key (e.g., 'linear.updatedAfter')
        default_hours_ago: Default hours ago if cursor doesn't exist
        
    Returns:
        ISO timestamp string
    """
    try:
        result = await fetchval(
            "SELECT value FROM ingest_cursors WHERE key = $1",
            key
        )
        if result:
            return result
    except Exception as e:
        logger.warning(f"Failed to get cursor {key}: {e}")
    
    # Default to X hours ago
    default_time = datetime.now(timezone.utc) - timedelta(hours=default_hours_ago)
    return default_time.isoformat()


async def set_cursor(key: str, value: str) -> None:
    """
    Set cursor value in ingest_cursors table.
    
    Args:
        key: Cursor key
        value: ISO timestamp string
    """
    try:
        await exec(
            """
            INSERT INTO ingest_cursors (key, value, updated_at) 
            VALUES ($1, $2, NOW())
            ON CONFLICT (key) DO UPDATE SET 
                value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at
            """,
            key, value
        )
        logger.info(f"Updated cursor {key} to {value}")
    except Exception as e:
        logger.error(f"Failed to set cursor {key}: {e}")
        raise


async def fetch_workflow_states(team_id: str, api_key: str) -> List[Dict]:
    """
    Fetch workflow states for a Linear team.
    
    Args:
        team_id: Linear team ID
        api_key: Linear API key
        
    Returns:
        List of workflow state dictionaries
        
    Raises:
        httpx.RequestError: If the Linear API request fails
        ValueError: If required environment variables are missing
    """
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    
    variables = {"teamId": team_id}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.linear.app/graphql",
            headers=headers,
            json={"query": WORKFLOW_STATES_QUERY, "variables": variables}
        )
        response.raise_for_status()
        
        data = response.json()
        if "errors" in data:
            raise ValueError(f"Linear API error: {data['errors']}")
            
        team_data = data.get("data", {}).get("team")
        if not team_data:
            raise ValueError(f"Team {team_id} not found")
            
        states = team_data.get("states", {}).get("nodes", [])
        logger.info(f"Fetched {len(states)} workflow states for team {team_id}")
        return states


async def fetch_linear_issues(team_id: str, api_key: str, updated_after_iso: str) -> List[Dict]:
    """
    Fetch Linear issues updated after the given timestamp.
    
    Args:
        team_id: Linear team ID
        api_key: Linear API key
        updated_after_iso: ISO timestamp to fetch issues since
        
    Returns:
        List of Linear issue dictionaries
        
    Raises:
        httpx.RequestError: If the Linear API request fails
        ValueError: If the API returns errors
    """
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    
    all_issues = []
    after_cursor = None
    has_next_page = True
    
    while has_next_page:
        variables = {
            "teamId": team_id,
            "updatedAfter": updated_after_iso,
            "after": after_cursor
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.linear.app/graphql",
                headers=headers,
                json={"query": ISSUES_QUERY, "variables": variables}
            )
            response.raise_for_status()
            
            data = response.json()
            if "errors" in data:
                raise ValueError(f"Linear API error: {data['errors']}")
                
            issues_data = data.get("data", {}).get("issues", {})
            page_info = issues_data.get("pageInfo", {})
            issues = issues_data.get("nodes", [])
            
            all_issues.extend(issues)
            
            has_next_page = page_info.get("hasNextPage", False)
            after_cursor = page_info.get("endCursor")
            
            logger.debug(f"Fetched {len(issues)} issues, total: {len(all_issues)}")
    
    logger.info(f"Fetched {len(all_issues)} Linear issues updated after {updated_after_iso}")
    return all_issues


def normalize_linear_issue(issue: Dict, last_state: Optional[str] = None) -> List[Dict]:
    """
    Normalize a Linear issue to our schema format.
    
    Args:
        issue: Raw Linear issue dictionary
        last_state: Previous state name if known (for state change detection)
        
    Returns:
        List of normalized event dictionaries matching our schema
    """
    events = []
    
    # Extract common fields
    issue_id = issue.get("id")
    identifier = issue.get("identifier", "")
    title = issue.get("title", "")
    url = issue.get("url", "")
    created_at = issue.get("createdAt")
    updated_at = issue.get("updatedAt")
    
    state = issue.get("state", {})
    state_name = state.get("name", "")
    
    assignees = [
        {
            "id": assignee.get("id"),
            "name": assignee.get("name"),
            "displayName": assignee.get("displayName")
        }
        for assignee in issue.get("assignees", {}).get("nodes", [])
    ]
    
    labels = [
        {
            "id": label.get("id"),
            "name": label.get("name")
        }
        for label in issue.get("labels", {}).get("nodes", [])
    ]
    
    # Common metadata
    meta = {
        "identifier": identifier,
        "state": state,
        "priority": issue.get("priority"),
        "assignees": assignees,
        "labels": labels,
        "branchName": issue.get("branchName"),
        "previousIdentifiers": issue.get("previousIdentifiers", [])
    }
    
    # 1. ISSUE_CREATED event (always emit if we have createdAt)
    if created_at:
        events.append({
            "ts": created_at,
            "source": "linear",
            "actor": None,  # TODO: Linear API lacks reliable actor attribution
            "type": "ISSUE_CREATED",
            "ref_id": issue_id,
            "title": f"{identifier} {title}" if identifier else title,
            "url": url,
            "meta": {**meta, "event_type": "created"}
        })
    
    # 2. ISSUE_UPDATED event (only if different from created)
    if updated_at and updated_at != created_at:
        events.append({
            "ts": updated_at,
            "source": "linear", 
            "actor": None,  # TODO: Linear API lacks reliable actor attribution
            "type": "ISSUE_UPDATED",
            "ref_id": issue_id,
            "title": f"{identifier} {title}" if identifier else title,
            "url": url,
            "meta": {**meta, "event_type": "updated"}
        })
    
    # 3. ISSUE_STATE_CHANGED event
    if last_state and state_name != last_state:
        # We have explicit state change information
        events.append({
            "ts": updated_at or created_at,
            "source": "linear",
            "actor": None,  # TODO: Linear API lacks reliable actor attribution
            "type": "ISSUE_STATE_CHANGED",
            "ref_id": issue_id,
            "title": f"{identifier} state changed to {state_name}",
            "url": url,
            "meta": {**meta, "event_type": "state_changed", "last_state": last_state}
        })
    elif updated_at != created_at and state_name:
        # Infer state change from update (no previous state data)
        events.append({
            "ts": updated_at,
            "source": "linear",
            "actor": None,  # TODO: Linear API lacks reliable actor attribution  
            "type": "ISSUE_STATE_CHANGED",
            "ref_id": issue_id,
            "title": f"{identifier} state changed to {state_name}",
            "url": url,
            "meta": {**meta, "event_type": "state_changed"}
        })
    
    # 4. ISSUE_BLOCKED / ISSUE_UNBLOCKED events
    # Check if current state or labels indicate blocked status
    is_currently_blocked = (
        "blocked" in state_name.lower() or
        any("blocked" in label["name"].lower() for label in labels)
    )
    
    if is_currently_blocked:
        events.append({
            "ts": updated_at or created_at,
            "source": "linear",
            "actor": None,  # TODO: Linear API lacks reliable actor attribution
            "type": "ISSUE_BLOCKED",
            "ref_id": issue_id,
            "title": f"{identifier} blocked",
            "url": url,
            "meta": {**meta, "event_type": "blocked"}
        })
    
    # TODO: We can't reliably detect UNBLOCKED without historical state
    # This would require webhook events or storing previous issue states
    
    return events


async def ingest_linear(team_id: str, api_key: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Ingest Linear issues and store events in database.
    
    Args:
        team_id: Linear team ID
        api_key: Linear API key
        dry_run: If True, don't insert events, just return sample
        
    Returns:
        Dict with inserted/skipped counts and cursor info
    """
    try:
        # 1. Load cursor
        cursor_key = "linear.updatedAfter"
        updated_after = await get_cursor(cursor_key, default_hours_ago=72)
        logger.info(f"Starting Linear ingest from cursor: {updated_after}")
        
        # 2. Fetch issues
        issues = await fetch_linear_issues(team_id, api_key, updated_after)
        
        if not issues:
            return {
                "inserted": 0,
                "skipped": 0,
                "cursor": updated_after,
                "issues_processed": 0
            }
        
        # 3. Normalize issues to events
        all_events = []
        max_updated_at = updated_after
        
        for issue in issues:
            # Track the max updatedAt for cursor advancement
            issue_updated = issue.get("updatedAt")
            if issue_updated and issue_updated > max_updated_at:
                max_updated_at = issue_updated
                
            # TODO: Load last_state from previous ingestion for better state change detection
            last_state = None
            
            # Normalize issue to events
            events = normalize_linear_issue(issue, last_state)
            all_events.extend(events)
        
        # 4. Handle dry run
        if dry_run:
            sample = all_events[:3] if len(all_events) >= 3 else all_events
            return {
                "inserted": 0,
                "skipped": 0,
                "cursor": max_updated_at,
                "issues_processed": len(issues),
                "events_generated": len(all_events),
                "sample": sample
            }
        
        # 5. Insert events (with idempotency)
        inserted = 0
        skipped = 0
        
        for event in all_events:
            try:
                result = await insert_event(
                    ts=event["ts"],
                    source=event["source"],
                    actor=event["actor"],
                    event_type=event["type"],
                    ref_id=event["ref_id"],
                    title=event["title"],
                    url=event["url"],
                    meta=event["meta"]
                )
                
                # Check if row was actually inserted
                if "INSERT 0 1" in result:
                    inserted += 1
                else:
                    skipped += 1
                    
            except Exception as e:
                logger.error(f"Failed to insert event {event['ref_id']}: {e}")
                skipped += 1
        
        # 6. Update cursor
        await set_cursor(cursor_key, max_updated_at)
        
        logger.info(f"Linear ingest completed: {inserted} inserted, {skipped} skipped")
        return {
            "inserted": inserted,
            "skipped": skipped,
            "cursor": max_updated_at,
            "issues_processed": len(issues)
        }
        
    except Exception as e:
        logger.error(f"Linear ingest failed: {e}")
        raise
