import os
import sys
import pytest
import asyncio
from typing import Dict, Any
import logging
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from twitter.profile_analyzer import ProfileAnalyzer
from twitter.nitter_scraper import NitterScraper
from utils.config import load_env_variables

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def config():
    """Load environment variables for testing"""
    return load_env_variables()


@pytest.fixture
def nitter_scraper():
    """Create a NitterScraper instance"""
    return NitterScraper()


@pytest.fixture
def profile_analyzer():
    """Create a ProfileAnalyzer instance"""
    return ProfileAnalyzer()


def test_nitter_scraper_initialization(nitter_scraper):
    """Test that NitterScraper initializes correctly"""
    assert nitter_scraper is not None
    assert nitter_scraper.base_url == "http://localhost:8081"
    assert nitter_scraper.session is not None


def test_profile_analyzer_initialization(profile_analyzer):
    """Test that ProfileAnalyzer initializes correctly"""
    assert profile_analyzer is not None
    assert profile_analyzer.scraper is not None


@pytest.mark.asyncio
async def test_profile_analysis(profile_analyzer):
    """Test profile analysis functionality with a known public account"""
    username = "github"  # Using a stable, public account
    result = await profile_analyzer.analyze_profile_with_retries(username)

    assert result is not None
    assert "username" in result
    assert result["username"] == username
    assert "date_analyzed" in result
    assert "analysis" in result

    # Check analysis structure
    analysis = result["analysis"]
    assert isinstance(analysis, dict)
    assert "business_name" in analysis
    assert "website" in analysis
    assert "business_context" in analysis


def test_nitter_profile_fetch(nitter_scraper):
    """Test fetching a profile using NitterScraper"""
    username = "github"  # Using a stable, public account
    profile = nitter_scraper.get_profile(username)

    assert profile is not None
    assert profile.username.lower() == username.lower()
    assert profile.fullname != ""
    assert isinstance(profile.followers_count, int)
    assert isinstance(profile.following_count, int)
    assert isinstance(profile.tweets_count, int)


def test_nitter_tweets_fetch(nitter_scraper):
    """Test fetching recent tweets using NitterScraper"""
    username = "github"
    tweets = nitter_scraper.get_recent_tweets(username, limit=5)

    assert isinstance(tweets, list)
    assert len(tweets) > 0

    # Test first tweet structure
    first_tweet = tweets[0]
    assert hasattr(first_tweet, "text")
    assert hasattr(first_tweet, "created_on")
    assert hasattr(first_tweet, "stats")
    assert hasattr(first_tweet, "media_urls")


@pytest.mark.asyncio
async def test_main_components():
    """Test that main.py's core components are working"""
    from main import load_env, setup_logging

    # Test environment loading
    load_env()
    assert os.getenv("AIRTABLE_TOKEN") is not None

    # Test logging setup
    setup_logging()
    logger = logging.getLogger()
    assert logger.level == logging.INFO
    assert len(logger.handlers) > 0


if __name__ == "__main__":
    pytest.main(["-v", __file__])
