-- Migration: Create events table
-- Created: Initial migration
-- Description: Store GitHub and Linear events for analysis

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL, -- 'github' or 'linear'
    event_type VARCHAR(100) NOT NULL, -- 'commit', 'pr_open', 'pr_merge', 'issue_created', etc.
    event_id VARCHAR(255) NOT NULL, -- External ID from source system
    repository_name VARCHAR(255), -- GitHub repo name or Linear workspace
    author VARCHAR(255) NOT NULL, -- User who triggered the event
    title TEXT, -- PR/Issue title
    body TEXT, -- PR/Issue description
    labels TEXT[], -- Array of labels/tags
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB, -- Additional event-specific data
    
    -- Ensure we don't duplicate events
    UNIQUE(source, event_id)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_author ON events(author);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_repository ON events(repository_name);

-- Index on metadata for JSON queries
CREATE INDEX IF NOT EXISTS idx_events_metadata_gin ON events USING GIN (metadata);