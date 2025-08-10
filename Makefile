.PHONY: help dev-api dev-web db-migrate install-api install-web setup

# Default target
help:
	@echo "Pulse Development Commands:"
	@echo "  setup       - Install all dependencies"
	@echo "  dev-api     - Start FastAPI development server"
	@echo "  dev-web     - Start Next.js development server"
	@echo "  db-migrate  - Run database migrations"
	@echo "  install-api - Install Python dependencies"
	@echo "  install-web - Install Node.js dependencies"

# Setup everything
setup: install-api install-web
	@echo "✅ Setup complete! Copy .env.example to .env and configure your settings."

# Install Python dependencies
install-api:
	@echo "🐍 Installing Python dependencies..."
	cd api && pip install -r requirements.txt

# Install Node.js dependencies
install-web:
	@echo "📦 Installing Node.js dependencies..."
	cd web && npm install

# Start FastAPI development server
dev-api:
	@echo "🚀 Starting FastAPI development server..."
	@echo "📊 Public report available at http://localhost:8000/report/public"
	cd api && python main.py

# Start Next.js development server
dev-web:
	@echo "🌐 Starting Next.js development server..."
	cd web && npm run dev

# Run database migrations
db-migrate:
	@echo "🗄️  Running database migrations..."
	@if [ ! -f .env ]; then \
		echo "❌ Error: .env file not found. Copy .env.example to .env and configure your database settings."; \
		exit 1; \
	fi
	@echo "Loading environment variables..."
	@set -a && . ./.env && set +a && \
	for migration in db/migrations/*.sql; do \
		echo "Applying migration: $$(basename $$migration)"; \
		psql $$DATABASE_URL -f "$$migration" || exit 1; \
	done
	@echo "✅ Database migrations complete!"

# Check if database is accessible
db-check:
	@echo "🔍 Checking database connection..."
	@psql $(DATABASE_URL) -c "SELECT version();" || echo "❌ Database connection failed"

# Clean up build artifacts
clean:
	@echo "🧹 Cleaning up..."
	cd web && rm -rf .next node_modules/.cache
	cd api && find . -type d -name __pycache__ -exec rm -rf {} +
