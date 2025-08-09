-- Migration: 0001_init.sql
-- Description: Initial schema with events, metrics_daily, and feedback tables
-- Created: 2025-08-09

-- Enable UUID extension for UUID primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Events table: Store GitHub and Linear activity events
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL,
    source TEXT CHECK (source IN ('github', 'linear')) NOT NULL,
    actor TEXT,
    type TEXT NOT NULL,
    ref_id TEXT NOT NULL,
    title TEXT,
    url TEXT,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Ensure unique events per source/ref_id/type/timestamp combination
    UNIQUE(source, ref_id, type, ts)
);

-- Indexes for efficient querying
CREATE INDEX idx_events_ts ON events(ts);
CREATE INDEX idx_events_source ON events(source);
CREATE INDEX idx_events_type ON events(type);
CREATE INDEX idx_events_actor ON events(actor);
CREATE INDEX idx_events_ref_id ON events(ref_id);
CREATE INDEX idx_events_meta_gin ON events USING GIN (meta);

-- Daily metrics table: Store computed daily engineering metrics
CREATE TABLE metrics_daily (
    as_of_date DATE PRIMARY KEY,
    prs_open INT NOT NULL DEFAULT 0,
    prs_merged INT NOT NULL DEFAULT 0,
    avg_pr_review_hours NUMERIC(6,2) NOT NULL DEFAULT 0,
    tickets_moved INT NOT NULL DEFAULT 0,
    tickets_blocked INT NOT NULL DEFAULT 0
);

-- Index for date range queries
CREATE INDEX idx_metrics_daily_date ON metrics_daily(as_of_date);

-- Feedback table: Store AI model feedback for learning and improvement
CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    as_of_ts TIMESTAMPTZ NOT NULL,
    context_hash TEXT NOT NULL,
    llm_json JSONB NOT NULL
);

-- Indexes for feedback analysis
CREATE INDEX idx_feedback_ts ON feedback(as_of_ts);
CREATE INDEX idx_feedback_context_hash ON feedback(context_hash);
CREATE INDEX idx_feedback_llm_json_gin ON feedback USING GIN (llm_json);
