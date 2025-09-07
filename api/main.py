"""
Pulse API - Main application module.

AI-powered engineering radar API with priority recommendations.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dependencies import API_TITLE, API_DESCRIPTION, API_VERSION, validate_environment
from routers import health, ingest, priority, report

# Validate environment on startup
validate_environment()

# Create FastAPI application
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(report.router)
app.include_router(priority.router)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "localhost")
    port = int(os.getenv("API_PORT", 8000))

    uvicorn.run(app, host=host, port=port, reload=True)