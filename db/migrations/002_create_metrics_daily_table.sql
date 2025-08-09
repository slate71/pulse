-- Migration: Create metrics_daily table
-- Created: Initial migration
-- Description: Store daily computed execution metrics

CREATE TABLE IF NOT EXISTS metrics_daily (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    repository_name VARCHAR(255), -- NULL for cross-repo metrics
    
    -- Velocity Metrics
    commits_count INTEGER DEFAULT 0,
    pull_requests_opened INTEGER DEFAULT 0,
    pull_requests_merged INTEGER DEFAULT 0,
    issues_created INTEGER DEFAULT 0,
    issues_closed INTEGER DEFAULT 0,
    
    -- Cycle Time Metrics (in hours)
    avg_pr_cycle_time DECIMAL(10,2), -- Time from PR open to merge
    avg_issue_cycle_time DECIMAL(10,2), -- Time from issue open to close
    
    -- Development Metrics
    lines_added INTEGER DEFAULT 0,
    lines_deleted INTEGER DEFAULT 0,
    files_changed INTEGER DEFAULT 0,
    
    -- Team Metrics
    active_contributors INTEGER DEFAULT 0,
    avg_commits_per_contributor DECIMAL(10,2),
    
    -- Quality Metrics
    test_coverage_percentage DECIMAL(5,2),
    build_success_rate DECIMAL(5,2),
    
    -- Deployment Metrics
    deployments_count INTEGER DEFAULT 0,
    avg_deployment_frequency DECIMAL(10,2), -- Deployments per day
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Ensure one record per date per repository
    UNIQUE(date, repository_name)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_metrics_daily_date ON metrics_daily(date);
CREATE INDEX IF NOT EXISTS idx_metrics_daily_repository ON metrics_daily(repository_name);
CREATE INDEX IF NOT EXISTS idx_metrics_daily_date_repo ON metrics_daily(date, repository_name);