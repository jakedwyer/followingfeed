from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, Dict
import logging
from twitter.profile_analyzer import analyze_twitter_profile
from utils.logging_setup import setup_logging
from utils.config import load_env_variables
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import asyncio
from datetime import datetime
import re


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data in logs"""

    def __init__(self):
        super().__init__()
        self.patterns = [
            (r"Bearer\s+[a-zA-Z0-9\-._~+/]+=*", "Bearer [FILTERED]"),
            (r'"Authorization":\s*"Bearer\s+[^"]*"', '"Authorization": "[FILTERED]"'),
            (r'api_key["\']:\s*["\'][^"\']*["\']', 'api_key": "[FILTERED]"'),
        ]

    def filter(self, record):
        if isinstance(record.msg, str):
            for pattern, replacement in self.patterns:
                record.msg = re.sub(pattern, replacement, record.msg)
        return True


# Initialize logging with sensitive data filter
setup_logging()
logger = logging.getLogger(__name__)
logger.addFilter(SensitiveDataFilter())

# Load configuration
config = load_env_variables()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Twitter Profile Analyzer",
    description="API for analyzing Twitter profiles using AI",
    version="1.0.0",
)

# Add rate limiting error handler
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return _rate_limit_exceeded_handler(request, exc)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modify this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache for recent results
analysis_cache: Dict[str, Dict] = {}
CACHE_EXPIRY = 3600  # 1 hour in seconds
MAX_CACHE_SIZE = 1000  # Maximum number of items in cache


class ProfileRequest(BaseModel):
    username: str


class ProfileResponse(BaseModel):
    username: str
    date_analyzed: str
    feed_sample: str
    analysis: dict
    error: Optional[str] = None
    cached: bool = False


def is_cache_valid(cache_time: str) -> bool:
    """Check if cached result is still valid."""
    cache_datetime = datetime.fromisoformat(cache_time)
    now = datetime.utcnow()
    return (now - cache_datetime).total_seconds() < CACHE_EXPIRY


def cleanup_cache():
    """Clean up expired cache entries and ensure cache doesn't exceed size limit"""
    current_time = datetime.utcnow()
    # Remove expired entries
    expired_keys = [
        k for k, v in analysis_cache.items() if not is_cache_valid(v["date_analyzed"])
    ]
    for k in expired_keys:
        del analysis_cache[k]

    # If still too many entries, remove oldest ones
    if len(analysis_cache) > MAX_CACHE_SIZE:
        sorted_items = sorted(
            analysis_cache.items(),
            key=lambda x: datetime.fromisoformat(x[1]["date_analyzed"]),
        )
        for k, _ in sorted_items[: len(analysis_cache) - MAX_CACHE_SIZE]:
            del analysis_cache[k]


def update_cache(username: str, result: Dict):
    """Update the analysis cache with cleanup."""
    analysis_cache[username] = result
    cleanup_cache()


@app.post("/analyze_profile", response_model=ProfileResponse)
@limiter.limit("10/minute")
async def analyze_profile(
    request: Request,  # This must be the first parameter for rate limiting
    profile_request: ProfileRequest,
    background_tasks: BackgroundTasks,
):
    """
    Analyze a Twitter profile and return structured insights.

    Parameters:
    - username: Twitter username to analyze (without @ symbol)

    Returns:
    - Structured analysis of the profile including business information
    """
    try:
        username = profile_request.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username cannot be empty")

        logger.info(f"Received analysis request for username: {username}")

        # Check cache first
        if username in analysis_cache:
            cached_result = analysis_cache[username]
            if is_cache_valid(cached_result["date_analyzed"]):
                logger.info(f"Returning cached result for {username}")
                cached_result["cached"] = True
                return cached_result

        # Analyze profile
        logger.info(f"Starting profile analysis for {username}")
        result = await analyze_twitter_profile(username)

        if not result:
            raise HTTPException(
                status_code=404, detail=f"Could not analyze profile for {username}"
            )

        if "error" in result:
            error_msg = result["error"]
            logger.error(f"Error analyzing profile {username}: {error_msg}")
            # Return the error response instead of raising an exception
            return ProfileResponse(
                username=username,
                date_analyzed=datetime.utcnow().isoformat(),
                feed_sample="",
                analysis={},
                error=error_msg,
            )

        # Update cache in background
        logger.info(f"Analysis complete for {username}, updating cache")
        background_tasks.add_task(update_cache, username, result)

        return result
    except HTTPException as he:
        logger.error(f"HTTP error for {profile_request.username}: {str(he)}")
        raise
    except Exception as e:
        logger.error(
            f"Error analyzing profile {profile_request.username}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/health")
@limiter.limit("60/minute")
async def health_check(request: Request):
    """Health check endpoint"""
    return {"status": "healthy"}
