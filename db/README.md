# Database Setup

## Environment Configuration

1. Copy the environment template:
   ```bash
   cp db/.env.example .env
   ```

2. Update `.env` with your PostgreSQL credentials:
   ```env
   DATABASE_URL=postgresql://username:password@localhost:5432/pulse_db
   ```

## Running Migrations

Run all migrations in order:
```bash
make db-migrate
```

## Database Schema

The database includes three core tables:

### `events`
Stores GitHub and Linear activity events:
- `id`: UUID primary key
- `ts`: Event timestamp
- `source`: 'github' or 'linear' 
- `actor`: User who triggered the event
- `type`: Event type (commit, pr_open, etc.)
- `ref_id`: External reference ID
- `title`: Event title
- `url`: Event URL
- `meta`: Additional metadata as JSONB

### `metrics_daily`
Daily aggregated engineering metrics:
- `as_of_date`: Date (primary key)
- `prs_open`: Pull requests opened
- `prs_merged`: Pull requests merged  
- `avg_pr_review_hours`: Average review time
- `tickets_moved`: Linear tickets moved
- `tickets_blocked`: Blocked tickets count

### `feedback`
AI model feedback for continuous improvement:
- `id`: UUID primary key
- `as_of_ts`: Feedback timestamp
- `context_hash`: Hash of input context
- `llm_json`: LLM response as JSONB
