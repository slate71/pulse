# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pulse is an AI-powered engineering radar with a context-aware Priority Engine that ingests activity from GitHub and Linear, computes execution metrics, and generates intelligent priority recommendations. Built with staff-level engineering practices including containerization, modern tooling, and AI integration.

## Development Commands (Containerized)

### Setup and Environment
```bash
just setup             # Build containerized development environment
just dev               # Start full development stack (detached)
just stop              # Stop all services
just clean             # Clean up containers and volumes
```

### Database Operations
```bash
just db-migrate        # Apply all SQL migrations from db/migrations/
just db-shell          # Open PostgreSQL shell
```

### Development Tools
```bash
just logs              # View logs from all services
just logs api          # View logs from specific service
just shell api         # Shell into API container
just shell web         # Shell into Web container
```

### Testing
```bash
just shell api         # Enter API container
pytest                 # Run all tests inside container
pytest tests/test_*.py  # Run specific test file
pytest -v              # Verbose test output
```

## Architecture Overview (Staff-Level Containerized)

### Container Services
- **API**: FastAPI backend (Python 3.12) with hot reload
- **Web**: Next.js 15 frontend with TypeScript
- **Database**: PostgreSQL 15 with persistent volumes
- **Cache**: Redis 7 for performance optimization
- **Multi-stage builds**: Optimized for dev/prod deployment

### Database Schema (PostgreSQL)
- **events**: Central event store with unique constraint `(source, ref_id, type, ts)` for idempotency
- **metrics_daily**: Computed daily metrics (PRs, review times, ticket movement)  
- **feedback**: AI model feedback for learning and improvement
- **ingest_cursors**: Key-value store for tracking incremental ingestion cursors
- **user_journey**: Journey state tracking for context-aware recommendations
- **priority_recommendations**: AI recommendation storage with feedback learning
- **context_cache**: Performance optimization for context building

### AI Priority Engine (`api/`)
- **main.py**: FastAPI with priority endpoints: `/priority/generate`, `/priority/feedback`, `/journey/state`
- **priority_engine.py**: Core AI recommendation system with multi-factor scoring
- **context_builder.py**: Context aggregation from multiple data sources (GitHub, Linear, metrics)
- **db.py**: Async database layer using asyncpg with connection pooling
- **github_ingest.py**: GitHub API client with event normalization
- **linear_ingest.py**: Linear GraphQL client with issue-to-event normalization  
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
- **POST `/priority/generate`**: AI-powered priority recommendations with context analysis
- **POST `/priority/feedback`**: Record feedback on recommendations for learning
- **GET `/journey/state`**: Get current user journey state and progress
- **GET `/report/public`**: Public report with rate limiting

### AI Priority Engine Features
- **Context-Aware Analysis**: Multi-source data aggregation (GitHub, Linear, metrics, journey state)
- **Multi-Factor Scoring**: Urgency, impact, momentum, energy alignment scoring
- **OpenAI Integration**: Intelligent reasoning with fallback logic
- **Learning System**: Feedback collection for recommendation improvement
- **Journey Tracking**: User state management for personalized recommendations

### Configuration (Environment Variables)
```bash
DATABASE_URL=postgresql://...
GITHUB_TOKEN=ghp_...              # For GitHub API access
LINEAR_API_KEY=lin_...            # For Linear GraphQL API  
LINEAR_TEAM_ID=...                # Team scope for Linear ingestion
OPENAI_API_KEY=sk-...             # Optional: For enhanced AI reasoning
```

### Frontend (`web/`)
- **Next.js 15** with TypeScript, TailwindCSS, TanStack Query
- **Priority Engine UI**: Real-time recommendations with reasoning display
- **Journey Progress**: Visualization of user journey and goal tracking
- **Components**: Located in `app/` directory following App Router structure

## Development Patterns

### Database Migrations
- Sequential numbered files in `db/migrations/` (e.g., `0001_init.sql`, `0002_ingest_cursors.sql`, `0003_journey_tracking.sql`)
- Apply with `just db-migrate` which runs all migration files in order
- Add new migrations manually to justfile for explicit control
- Use `just db-shell` for direct database access

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