# Pulse - AI Priority Engine

An engineering metrics dashboard with AI-powered priority recommendations.

## Features
- **AI Priority Engine**: Context analysis from GitHub/Linear activity with multi-factor scoring
- **Data Sources**: Pull requests, commits, issue tracking, 48-hour rolling metrics
- **Containerized Development**: Docker/Podman setup with modern tooling

## Tech Stack
- **Backend**: FastAPI, PostgreSQL, Redis, OpenAI integration
- **Frontend**: Next.js 15, TypeScript, TailwindCSS
- **Infrastructure**: Multi-stage Docker builds, `just` task runner

## Setup

### Prerequisites
- Podman or Docker
- `just` task runner (`brew install just`)

### Quick Start
```bash
git clone <repository>
cd pulse
cp .env.example .env
just dev              # Start development stack
just db-migrate       # Apply database migrations
```

**Access:**
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Commands
```bash
just dev       # Start all services
just stop      # Stop all services  
just logs      # View logs
just db-shell  # Database shell
just clean     # Clean up containers
```

## API Endpoints
- `POST /priority/generate` - AI priority recommendations
- `POST /ingest/run` - GitHub/Linear data ingestion
- `GET /health` - System health check

## Database Schema
- `events` - GitHub/Linear activity events
- `user_journey` - User state and preferences  
- `priority_recommendations` - AI recommendations and feedback
