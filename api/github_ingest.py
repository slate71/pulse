"""
GitHub ingest module for fetching events from GitHub API and storing them in the database.
"""

import os
import httpx
import logging
from typing import Dict, List, Optional
from datetime import datetime
from db import exec, insert_event

logger = logging.getLogger(__name__)


async def fetch_github_events(owner: str, repo: str, since_iso: str | None = None) -> List[Dict]:
    """
    Fetch GitHub events for a repository.
    
    Args:
        owner: Repository owner
        repo: Repository name
        since_iso: ISO timestamp to fetch events since (optional)
    
    Returns:
        List of GitHub event dictionaries
    
    Raises:
        httpx.RequestError: If the GitHub API request fails
        ValueError: If GH_TOKEN is not set
    """
    gh_token = os.getenv("GH_TOKEN")
    if not gh_token:
        raise ValueError("GH_TOKEN environment variable is required")
    
    url = f"https://api.github.com/repos/{owner}/{repo}/events"
    headers = {
        "Authorization": f"token {gh_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "pulse-github-ingest/1.0"
    }
    
    params = {}
    if since_iso:
        # Note: GitHub events API doesn't support 'since' parameter directly
        # We'll filter client-side for now
        params["per_page"] = "100"
    else:
        params["per_page"] = "100"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        events = response.json()
        
        # Filter by since_iso if provided (client-side filtering)
        if since_iso:
            since_dt = datetime.fromisoformat(since_iso.replace('Z', '+00:00'))
            filtered_events = []
            for event in events:
                event_dt = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
                if event_dt >= since_dt:
                    filtered_events.append(event)
            events = filtered_events
        
        logger.info(f"Fetched {len(events)} GitHub events for {owner}/{repo}")
        return events


def normalize_github_event(event: Dict) -> Dict:
    """
    Normalize a GitHub event to our schema format.
    
    Args:
        event: Raw GitHub event dictionary
    
    Returns:
        Normalized event dictionary with our schema fields
    """
    # Extract basic info
    ts = event.get('created_at')
    actor = event.get('actor', {}).get('login') if event.get('actor') else None
    event_type = event.get('type', 'unknown')
    
    # Generate ref_id based on event type
    ref_id = event.get('id', str(event.get('id', 'unknown')))
    
    # Extract title and URL based on event type
    title = None
    url = None
    
    payload = event.get('payload', {})
    repo_info = event.get('repo', {})
    
    if event_type == 'PushEvent':
        commits = payload.get('commits', [])
        if commits:
            title = f"Push: {commits[0].get('message', 'No message')[:100]}"
        else:
            title = f"Push to {payload.get('ref', 'unknown ref')}"
        # Use the first commit SHA as ref_id for uniqueness
        if commits:
            ref_id = commits[0].get('sha', ref_id)
        url = f"https://github.com/{repo_info.get('name')}/commits/{ref_id}" if commits else None
    
    elif event_type == 'PullRequestEvent':
        pr = payload.get('pull_request', {})
        action = payload.get('action', 'unknown')
        title = f"PR {action}: {pr.get('title', 'No title')[:100]}"
        ref_id = str(pr.get('id', ref_id))
        url = pr.get('html_url')
        # Add PR action to type for more specific tracking
        event_type = f"PullRequestEvent_{action}"
    
    elif event_type == 'IssuesEvent':
        issue = payload.get('issue', {})
        action = payload.get('action', 'unknown')
        title = f"Issue {action}: {issue.get('title', 'No title')[:100]}"
        ref_id = str(issue.get('id', ref_id))
        url = issue.get('html_url')
        event_type = f"IssuesEvent_{action}"
    
    elif event_type == 'CreateEvent':
        ref_type = payload.get('ref_type', 'unknown')
        ref = payload.get('ref')
        if ref:
            title = f"Created {ref_type}: {ref}"
            ref_id = f"{ref_type}_{ref}"
        else:
            title = f"Created {ref_type}"
        url = f"https://github.com/{repo_info.get('name')}"
    
    elif event_type == 'DeleteEvent':
        ref_type = payload.get('ref_type', 'unknown')
        ref = payload.get('ref')
        if ref:
            title = f"Deleted {ref_type}: {ref}"
            ref_id = f"{ref_type}_{ref}"
        else:
            title = f"Deleted {ref_type}"
        url = f"https://github.com/{repo_info.get('name')}"
    
    else:
        # Generic handling for other event types
        title = f"{event_type} event"
        url = f"https://github.com/{repo_info.get('name')}" if repo_info.get('name') else None
    
    return {
        'ts': ts,
        'source': 'github',
        'actor': actor,
        'type': event_type,
        'ref_id': ref_id,
        'title': title,
        'url': url,
        'meta': event  # Store the raw event data
    }


async def ingest_github_events(owner: str, repo: str, since_iso: str | None = None) -> Dict[str, int]:
    """
    Fetch and store GitHub events in the database.
    
    Args:
        owner: Repository owner
        repo: Repository name  
        since_iso: ISO timestamp to fetch events since (optional)
    
    Returns:
        Dict with 'inserted' and 'skipped' counts
    """
    try:
        # Fetch events from GitHub API
        events = await fetch_github_events(owner, repo, since_iso)
        
        inserted = 0
        skipped = 0
        
        # Process each event
        for raw_event in events:
            try:
                # Normalize to our schema
                normalized = normalize_github_event(raw_event)
                
                # Insert with ON CONFLICT DO NOTHING (idempotent)
                result = await insert_event(
                    ts=normalized['ts'],
                    source=normalized['source'],
                    actor=normalized['actor'],
                    event_type=normalized['type'],
                    ref_id=normalized['ref_id'],
                    title=normalized['title'],
                    url=normalized['url'],
                    meta=normalized['meta']
                )
                
                # Check if row was actually inserted
                # PostgreSQL returns "INSERT 0 1" for successful insert, "INSERT 0 0" for conflict
                if "INSERT 0 1" in result:
                    inserted += 1
                else:
                    skipped += 1
                    
            except Exception as e:
                logger.error(f"Failed to process event {raw_event.get('id')}: {e}")
                skipped += 1
        
        logger.info(f"GitHub ingest completed: {inserted} inserted, {skipped} skipped")
        return {"inserted": inserted, "skipped": skipped}
        
    except Exception as e:
        logger.error(f"GitHub ingest failed: {e}")
        raise