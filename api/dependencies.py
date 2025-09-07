"""
Shared dependencies for the API.
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def validate_environment():
    """Validate required environment variables are set."""
    required_vars = ["DATABASE_URL"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Log optional configuration status
    if os.getenv("OPENAI_API_KEY"):
        logger.info("OpenAI API key configured - AI reasoning enabled")
    else:
        logger.info("OpenAI API key not configured - using fallback reasoning")
    
    if os.getenv("LINEAR_API_KEY"):
        logger.info("Linear API configured")
    
    if os.getenv("GITHUB_TOKEN"):
        logger.info("GitHub token configured")


# Common configuration
API_VERSION = "1.0.0"
API_TITLE = "Pulse API"
API_DESCRIPTION = "AI-powered engineering radar API"