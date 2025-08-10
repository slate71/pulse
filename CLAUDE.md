# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pulse is an AI-powered engineering radar that ingests activity from GitHub and Linear, computes execution metrics, and generates daily focus actions. It consists of a FastAPI backend that processes events and a Next.js frontend for visualization.

## Development Commands

### Setup and Dependencies
```bash
make setup              # Install all dependencies (Python + Node.js)
make install-api        # Install Python dependencies only
make install-web        # Install Node.js dependencies only
```

### Development Servers
```bash
make dev-api           # Start FastAPI backend on port 8000
make dev-web           # Start Next.js frontend on port 3000
```

### Database Operations
```bash
make db-migrate        # Apply all SQL migrations from db/migrations/
make db-check          # Test database connectivity
```

### Testing
```bash
cd api && python -m pytest                    # Run all tests
cd api && python -m pytest tests/test_*.py    # Run specific test file
cd api && python -m pytest -v                 # Verbose test output
cd web && npm run lint                         # Frontend linting
```

## Architecture Overview

### Database Schema (PostgreSQL)
- **events**: Central event store with unique constraint `(source, ref_id, type, ts)` for idempotency
- **metrics_daily**: Computed daily metrics (PRs, review times, ticket movement)  
- **feedback**: AI model feedback for learning and improvement
- **ingest_cursors**: Key-value store for tracking incremental ingestion cursors

### API Structure (`api/`)
- **main.py**: FastAPI application with CORS, endpoints: `/health`, `/ingest/run`, `/analyze`, `/report`
- **db.py**: Async database layer using asyncpg with connection pooling and utility functions
- **github_ingest.py**: GitHub API client with event normalization (PullRequestEvent_*, PushEvent, etc.)
- **linear_ingest.py**: Linear GraphQL client with issue-to-event normalization (ISSUE_CREATED, ISSUE_STATE_CHANGED, etc.)
- **metrics.py**: Pure functions for computing 48h metrics from events

### Event Ingestion Flow
1. **GitHub**: REST API → normalize to events → idempotent insert via `(source, ref_id, type, ts)`
2. **Linear**: GraphQL API → cursor-based pagination → multiple events per issue → idempotent insert
3. **Cursors**: Stored in `ingest_cursors` table for incremental sync (defaults to 72h lookback)

### Event Types and Normalization
- **GitHub**: `PullRequestEvent_opened`, `PullRequestEvent_merged`, `PushEvent`, etc.
- **Linear**: `ISSUE_CREATED`, `ISSUE_UPDATED`, `ISSUE_STATE_CHANGED`, `ISSUE_BLOCKED`
- **Schema**: `{ts, source, actor, type, ref_id, title, url, meta}` with JSONB metadata

### API Endpoints
- **POST `/ingest/run`**: Accepts `{"github": {...}}` or `{"linear": true}`, supports `?dryRun=true`
- **POST `/analyze`**: Queries 48h events, computes metrics, returns `{metrics, events}`
- **GET `/health`**: Database connectivity and system status

### Configuration (Environment Variables)
```bash
DATABASE_URL=postgresql://...
GITHUB_TOKEN=ghp_...              # For GitHub API access
LINEAR_API_KEY=lin_...            # For Linear GraphQL API
LINEAR_TEAM_ID=...                # Team scope for Linear ingestion
```

### Frontend (`web/`)
- **Next.js 14** with TypeScript, TailwindCSS, TanStack Query
- **Query client**: Configured with React Query for API data fetching
- **Components**: Located in `app/` directory following App Router structure

## Development Patterns

### Database Migrations
- Sequential numbered files in `db/migrations/` (e.g., `0001_init.sql`, `0002_ingest_cursors.sql`)
- Apply with `make db-migrate` which runs all `.sql` files in order
- Use `psql $DATABASE_URL -f migration.sql` for individual migrations

### Event Normalization
- Each ingestion module (`github_ingest.py`, `linear_ingest.py`) has a `normalize_*()` function
- Always return list of dicts matching event schema
- Use `ON CONFLICT DO NOTHING` for idempotent insertion
- Store raw API response in `meta` field as JSONB

### Testing Strategy
- Unit tests in `api/tests/` using pytest
- Test event normalization with fixture data
- Mock external API calls for reliable testing
- Verify idempotency and edge cases

### Error Handling
- API returns structured HTTP errors with clear messages
- Log errors with context for debugging
- Validate environment variables at startup
- Graceful degradation for missing optional config

## Metrics Computation

The `compute_48h_metrics()` function in `metrics.py` processes events to generate:
- `prs_open_48h`: GitHub PullRequestEvent_opened count
- `prs_merged_48h`: GitHub merged PR count (checks meta.payload.pull_request.merged)
- `tickets_moved_48h`: Linear ISSUE_CREATED + ISSUE_STATE_CHANGED count
- `tickets_blocked_now`: Linear ISSUE_BLOCKED count
- `avg_review_hours_48h`: Stub (TODO for future implementation)

## Running Lint/Type Checking

The project uses automatic linting and formatting:
- Python files are handled by the system (no explicit lint commands in Makefile)
- Frontend uses `npm run lint` for ESLint checks
- Always ensure files end with newlines (project standard)