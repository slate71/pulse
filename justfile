# Pulse Development Commands

# Show available commands
default:
    @just --list

# Setup development environment
setup:
    @echo "Setting up Pulse development environment"
    podman-compose build
    @echo "Development environment ready"

# Start development environment
dev:
    @echo "Starting Pulse development stack"
    podman-compose up --build -d

# Stop all services
stop:
    @echo "Stopping all services"
    podman-compose down

# View logs
logs service="":
    @if [ -z "{{service}}" ]; then \
        podman-compose logs -f; \
    else \
        podman-compose logs -f {{service}}; \
    fi

# Shell into service
shell service:
    @echo "Opening shell in {{service}}"
    podman-compose exec {{service}} /bin/bash

# Run database migrations
db-migrate:
    @echo "Running database migrations"
    -podman-compose exec -T db psql -U postgres -d pulse < db/migrations/0001_init.sql 2>/dev/null || true
    -podman-compose exec -T db psql -U postgres -d pulse < db/migrations/0002_ingest_cursors.sql 2>/dev/null || true  
    -podman-compose exec -T db psql -U postgres -d pulse < db/migrations/0003_journey_tracking.sql 2>/dev/null || true
    @echo "Migrations completed (existing tables preserved)"

# Database shell
db-shell:
    @echo "Opening database shell"
    podman-compose exec db psql -U postgres -d pulse

# Clean up everything
clean:
    @echo "Cleaning up development environment"
    podman-compose down -v --remove-orphans
    podman system prune -f
