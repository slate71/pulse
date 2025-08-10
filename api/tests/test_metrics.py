"""
Unit tests for metrics computation.
"""

import pytest
from datetime import datetime, timezone, timedelta
import sys
import os

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metrics import compute_48h_metrics, filter_recent_events


@pytest.fixture
def sample_events():
    """
    Fixture providing a sample list of events for testing.
    """
    now = datetime.now(timezone.utc)
    
    # Create events spanning different time periods
    events = [
        # Recent PR opened (within 48h)
        {
            "ts": (now - timedelta(hours=12)).isoformat(),
            "source": "github",
            "type": "PullRequestEvent_opened",
            "actor": "dev1",
            "ref_id": "pr_123",
            "title": "Add new feature",
            "url": "https://github.com/owner/repo/pull/123",
            "meta": {
                "payload": {
                    "action": "opened",
                    "pull_request": {"id": 123, "merged": False}
                }
            }
        },
        # Recent PR merged (within 48h)
        {
            "ts": (now - timedelta(hours=24)).isoformat(),
            "source": "github", 
            "type": "PullRequestEvent_closed",
            "actor": "dev2",
            "ref_id": "pr_124",
            "title": "Fix bug",
            "url": "https://github.com/owner/repo/pull/124",
            "meta": {
                "payload": {
                    "action": "closed",
                    "pull_request": {"id": 124, "merged": True}
                }
            }
        },
        # Old PR opened (outside 48h) - should not count
        {
            "ts": (now - timedelta(hours=72)).isoformat(),
            "source": "github",
            "type": "PullRequestEvent_opened", 
            "actor": "dev3",
            "ref_id": "pr_125",
            "title": "Old PR",
            "url": "https://github.com/owner/repo/pull/125",
            "meta": {
                "payload": {
                    "action": "opened",
                    "pull_request": {"id": 125, "merged": False}
                }
            }
        },
        # Recent PR closed but not merged (within 48h)
        {
            "ts": (now - timedelta(hours=6)).isoformat(),
            "source": "github",
            "type": "PullRequestEvent_closed",
            "actor": "dev1", 
            "ref_id": "pr_126",
            "title": "Closed PR",
            "url": "https://github.com/owner/repo/pull/126",
            "meta": {
                "payload": {
                    "action": "closed",
                    "pull_request": {"id": 126, "merged": False}
                }
            }
        },
        # Recent push event (within 48h)
        {
            "ts": (now - timedelta(hours=3)).isoformat(),
            "source": "github",
            "type": "PushEvent",
            "actor": "dev1",
            "ref_id": "commit_abc123",
            "title": "Push: Update README",
            "url": "https://github.com/owner/repo/commit/abc123",
            "meta": {
                "payload": {
                    "commits": [{"sha": "abc123", "message": "Update README"}]
                }
            }
        },
        # Linear event (not implemented yet - should not count)
        {
            "ts": (now - timedelta(hours=1)).isoformat(),
            "source": "linear",
            "type": "IssueEvent_moved",
            "actor": "dev2",
            "ref_id": "issue_456",
            "title": "Move ticket to In Progress",
            "url": "https://linear.app/issue/456",
            "meta": {}
        }
    ]
    
    return events


def test_compute_48h_metrics_pr_counts(sample_events):
    """Test that PR open/merge counts are computed correctly."""
    metrics = compute_48h_metrics(sample_events)
    
    # Should count 1 PR opened in last 48h (not the 72h old one)
    assert metrics["prs_open_48h"] == 1
    
    # Should count 1 PR merged in last 48h (not the closed but unmerged one)
    assert metrics["prs_merged_48h"] == 1


def test_compute_48h_metrics_stub_values(sample_events):
    """Test that stub values are returned for unimplemented metrics."""
    metrics = compute_48h_metrics(sample_events)
    
    # These should be 0.0 or 0 as they're not implemented yet
    assert metrics["avg_review_hours_48h"] == 0.0
    assert metrics["tickets_moved_48h"] == 0
    assert metrics["tickets_blocked_now"] == 0


def test_compute_48h_metrics_empty_events():
    """Test that empty events list returns zero metrics."""
    metrics = compute_48h_metrics([])
    
    expected = {
        "prs_open_48h": 0,
        "prs_merged_48h": 0,
        "avg_review_hours_48h": 0.0,
        "tickets_moved_48h": 0,
        "tickets_blocked_now": 0
    }
    
    assert metrics == expected


def test_compute_48h_metrics_invalid_timestamps():
    """Test that events with invalid timestamps are skipped."""
    events_with_invalid_ts = [
        {
            "ts": "invalid-timestamp",
            "source": "github",
            "type": "PullRequestEvent_opened",
            "actor": "dev1",
            "ref_id": "pr_123"
        },
        {
            "ts": None,
            "source": "github", 
            "type": "PullRequestEvent_opened",
            "actor": "dev2",
            "ref_id": "pr_124"
        }
    ]
    
    metrics = compute_48h_metrics(events_with_invalid_ts)
    
    # Should be all zeros since no valid events
    assert metrics["prs_open_48h"] == 0
    assert metrics["prs_merged_48h"] == 0


def test_filter_recent_events(sample_events):
    """Test that recent events are filtered and sorted correctly."""
    recent = filter_recent_events(sample_events, limit=3)
    
    # Should return 3 events
    assert len(recent) == 3
    
    # Should be sorted by timestamp descending (newest first)
    timestamps = [event["ts"] for event in recent]
    sorted_timestamps = sorted(timestamps, reverse=True)
    assert timestamps == sorted_timestamps
    
    # First event should be the most recent (1 hour ago)
    assert recent[0]["source"] == "linear"  # This was 1 hour ago
    

def test_filter_recent_events_limit():
    """Test that limit parameter works correctly."""
    now = datetime.now(timezone.utc)
    
    events = []
    for i in range(10):
        events.append({
            "ts": (now - timedelta(hours=i)).isoformat(),
            "source": "github",
            "type": "PushEvent",
            "actor": "dev1",
            "ref_id": f"commit_{i}"
        })
    
    # Test different limits
    assert len(filter_recent_events(events, limit=5)) == 5
    assert len(filter_recent_events(events, limit=3)) == 3
    assert len(filter_recent_events(events, limit=15)) == 10  # Max available


def test_z_timestamp_format():
    """Test that both 'Z' and '+00:00' timestamp formats are handled."""
    now = datetime.now(timezone.utc)
    
    events = [
        {
            "ts": (now - timedelta(hours=12)).isoformat() + "Z",  # Z format
            "source": "github",
            "type": "PullRequestEvent_opened",
            "actor": "dev1",
            "ref_id": "pr_123"
        },
        {
            "ts": (now - timedelta(hours=6)).isoformat() + "Z",  # Z format
            "source": "github", 
            "type": "PullRequestEvent_opened",
            "actor": "dev2",
            "ref_id": "pr_124"
        }
    ]
    
    metrics = compute_48h_metrics(events)
    assert metrics["prs_open_48h"] == 2
