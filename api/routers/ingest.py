"""
Data ingestion router for GitHub and Linear sources.
"""

import os
import logging
from fastapi import APIRouter, HTTPException
from models.schemas import IngestRequest, IngestRunRequest, IngestRunResponse
from github_ingest import ingest_github_events
from linear_ingest import ingest_linear

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("")
async def ingest_data(request: IngestRequest):
    # TODO: Implement data ingestion from GitHub and Linear
    # - Validate incoming event data
    # - Store events in database
    # - Queue for analysis if needed
    return {"message": f"Ingested {len(request.events)} events from {request.source}"}


@router.post("/run", response_model=IngestRunResponse)
async def run_ingest(request: IngestRunRequest, dryRun: bool = False):
    """
    Run data ingestion from configured sources.

    Currently supports:
    - GitHub: Fetch events from a repository
    - Linear: Fetch issues from a team
    """
    if not request.github and not request.linear:
        raise HTTPException(status_code=400, detail="No ingest sources specified")

    try:
        # Handle GitHub ingestion
        if request.github:
            result = await ingest_github_events(
                owner=request.github.owner,
                repo=request.github.repo,
                since_iso=request.github.since_iso
            )

            return IngestRunResponse(
                inserted=result["inserted"],
                skipped=result["skipped"]
            )

        # Handle Linear ingestion
        if request.linear:
            linear_api_key = os.getenv("LINEAR_API_KEY")
            linear_team_id = os.getenv("LINEAR_TEAM_ID")

            if not linear_api_key:
                raise HTTPException(
                    status_code=400,
                    detail="LINEAR_API_KEY environment variable is required"
                )

            if not linear_team_id:
                raise HTTPException(
                    status_code=400,
                    detail="LINEAR_TEAM_ID environment variable is required"
                )

            result = await ingest_linear(
                team_id=linear_team_id,
                api_key=linear_api_key,
                dry_run=dryRun
            )

            # Handle optional sample field with proper typing
            sample_data = result.get("sample")
            sample_field = sample_data if isinstance(sample_data, list) else None
            
            return IngestRunResponse(
                inserted=result["inserted"],
                skipped=result["skipped"],
                cursor=str(result.get("cursor")) if result.get("cursor") is not None else None,
                issues_processed=result.get("issues_processed"),
                events_generated=result.get("events_generated"),
                sample=sample_field
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"External service unavailable: {str(e)}")
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=f"Request timeout: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in ingest: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during ingestion")
