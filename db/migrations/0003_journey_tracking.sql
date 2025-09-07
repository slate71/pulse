-- Migration: 0003_journey_tracking.sql
-- Description: Add journey tracking tables for AI Priority Engine
-- Created: 2025-09-07

-- User journey state tracking
CREATE TABLE user_journey (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    desired_state JSONB NOT NULL,  -- {"role": "$200k+ Senior/Staff", "timeline": "3 months", "priorities": [...]}
    current_state JSONB NOT NULL,  -- {"status": "job_searching", "momentum": "high", "blockers": [...]}
    context_history JSONB[] DEFAULT '{}',  -- Array of context snapshots over time
    preferences JSONB DEFAULT '{}',  -- {"work_hours": "9-5", "energy_pattern": "morning_peak"}
    is_active BOOLEAN DEFAULT true
);

-- Index for active journey lookup
CREATE INDEX idx_user_journey_active ON user_journey(is_active) WHERE is_active = true;

-- Priority recommendations and outcomes
CREATE TABLE priority_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    journey_id UUID REFERENCES user_journey(id) ON DELETE CASCADE,
    context_snapshot JSONB NOT NULL,  -- Full context at recommendation time
    recommendations JSONB NOT NULL,    -- Primary + alternatives with reasoning
    action_taken TEXT,                 -- What user actually did
    outcome TEXT,                      -- success/blocked/deferred/skipped
    feedback_score INT CHECK (feedback_score BETWEEN -1 AND 1),  -- -1: bad, 0: neutral, 1: good
    time_to_complete INTERVAL,
    completed_at TIMESTAMPTZ
);

-- Indexes for recommendation queries
CREATE INDEX idx_priority_recommendations_journey ON priority_recommendations(journey_id);
CREATE INDEX idx_priority_recommendations_created ON priority_recommendations(created_at);
CREATE INDEX idx_priority_recommendations_feedback ON priority_recommendations(feedback_score) WHERE feedback_score IS NOT NULL;

-- Context enrichment cache (avoid re-fetching)
CREATE TABLE context_cache (
    key TEXT PRIMARY KEY,
    data JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for cache expiration
CREATE INDEX idx_context_cache_expires ON context_cache(expires_at);

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at on user_journey
CREATE TRIGGER update_user_journey_updated_at BEFORE UPDATE ON user_journey
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default journey for current user (can be updated via API later)
INSERT INTO user_journey (desired_state, current_state, preferences)
VALUES (
    '{
        "role": "$200k+ Staff/Senior Role",
        "timeline": "3 months",
        "priorities": [
            "Build impressive portfolio",
            "Demonstrate system design skills",
            "Show AI/ML integration capabilities"
        ]
    }'::jsonb,
    '{
        "status": "building_portfolio",
        "momentum": "high",
        "current_project": "Pulse AI Priority Engine",
        "blockers": []
    }'::jsonb,
    '{
        "work_hours": "9:00-17:00",
        "timezone": "America/Los_Angeles",
        "energy_pattern": "morning_peak",
        "preferred_task_size": "2-4 hours"
    }'::jsonb
);