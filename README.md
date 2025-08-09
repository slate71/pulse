# Pulse

AI-powered engineering radar that connects to GitHub and Linear, ingests activity, computes execution metrics, and uses a tightly scoped LLM prompt to produce 3 grounded focus actions daily.

## Description

Pulse analyzes engineering team activity from GitHub and Linear to provide data-driven insights and AI-generated focus recommendations. It ingests development events, computes execution metrics, and generates daily actionable insights to help teams improve their development velocity and focus.

## Quick Start

```bash
# Set up environment
cp .env.example .env
# Edit .env with your API keys and configuration

# Start development servers
make dev-api    # Start FastAPI backend (port 8000)
make dev-web    # Start Next.js frontend (port 3000)

# Set up database
make db-migrate # Run database migrations
```

## Architecture

- **api/** - FastAPI backend with data ingestion, analysis, and reporting endpoints
- **web/** - Next.js frontend with TanStack Query for data fetching
- **db/** - PostgreSQL migrations for events, metrics, and feedback storage

## Development

Requires Python 3.11+, Node.js 18+, and PostgreSQL 14+.
