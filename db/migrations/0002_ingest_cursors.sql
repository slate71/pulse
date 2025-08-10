-- Migration: 0002_ingest_cursors.sql
-- Description: Add ingest_cursors table for tracking ingestion cursors
-- Created: 2025-08-10

-- Ingest cursors table: Store cursors for incremental data ingestion
CREATE TABLE ingest_cursors (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for faster lookups by updated timestamp
CREATE INDEX idx_ingest_cursors_updated_at ON ingest_cursors(updated_at);