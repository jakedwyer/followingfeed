import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import json
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential
import ollama
from .nitter_scraper import NitterScraper
from utils.config import load_env_variables
from utils.logging_setup import setup_logging

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Load environment variables
config = load_env_variables()

# Configure rate limiting
MAX_CONCURRENT_REQUESTS = 5
request_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


class ProfileAnalyzer:
    def __init__(self):
        self.scraper = NitterScraper()
        self.client = ollama.AsyncClient(
            host=config.get("ollama_base_url", "http://localhost:11434")
        )

    async def _get_profile_content(self, username: str) -> Dict[str, Any]:
        """Get profile content using Nitter."""
        try:
            # Get profile info
            profile = self.scraper.get_profile(username)
            if not profile:
                error_msg = f"Could not find profile for user: {username}"
                logger.error(error_msg)
                return {"error": error_msg, "profile_info": {}, "feed_text": ""}

            # Get recent tweets (last 30 days)
            tweets = self.scraper.get_recent_tweets(username, limit=50)

            profile_info = {
                "Full Name": profile.fullname,
                "Description": profile.biography,
                "Website": profile.website,
                "Following": str(profile.following_count),
                "Followers": str(profile.followers_count),
                "Tweets": str(profile.tweets_count),
                "Likes": str(profile.likes_count),
                "Verified": profile.is_verified,
            }

            # Format feed text
            feed_text = self._format_feed_text(tweets) if tweets else ""

            return {"profile_info": profile_info, "feed_text": feed_text}

        except Exception as e:
            error_msg = f"Error collecting content for {username}: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg, "profile_info": {}, "feed_text": ""}

    def _format_feed_text(self, tweets: List[Any]) -> str:
        """Format tweet data into readable text, optimizing for analysis."""
        feed_text = ""
        try:
            # Define emoji constants to avoid encoding issues
            COMMENT_EMOJI = "💬"
            RETWEET_EMOJI = "🔁"
            LIKE_EMOJI = "❤️"
            PEOPLE_EMOJI = "👥"
            MEDIA_EMOJI = "📷"

            for tweet in tweets:
                # Skip empty tweets
                if not tweet.text.strip():
                    continue

                # Format date more concisely (e.g., "2024-02" or empty if unknown)
                date_str = ""
                if tweet.created_on and tweet.created_on != "unknown date":
                    try:
                        # Try to parse and format the date consistently
                        date_parts = tweet.created_on.split()
                        if len(date_parts) >= 2:  # At least month and day
                            date_str = date_parts[0][:3]  # First 3 chars of month
                    except Exception:
                        pass

                # Start with engagement metrics if significant (>1000 total engagement)
                engagement = ""
                if tweet.stats:
                    total_engagement = (
                        tweet.stats.comments + tweet.stats.retweets + tweet.stats.likes
                    )
                    if total_engagement > 1000:
                        engagement = (
                            f"[{COMMENT_EMOJI}{tweet.stats.comments//1000}K"
                            if tweet.stats.comments > 1000
                            else f"[{COMMENT_EMOJI}{tweet.stats.comments}"
                        )
                        engagement += (
                            f" {RETWEET_EMOJI}{tweet.stats.retweets//1000}K"
                            if tweet.stats.retweets > 1000
                            else f" {RETWEET_EMOJI}{tweet.stats.retweets}"
                        )
                        engagement += (
                            f" {LIKE_EMOJI}{tweet.stats.likes//1000}K]"
                            if tweet.stats.likes > 1000
                            else f" {LIKE_EMOJI}{tweet.stats.likes}]"
                        )
                    elif total_engagement > 0:
                        engagement = f"[{PEOPLE_EMOJI}{total_engagement}]"

                # Add media indicator with type if present
                media_info = ""
                if hasattr(tweet, "media_urls") and tweet.media_urls:
                    media_info = f"[{MEDIA_EMOJI}{len(tweet.media_urls)}]"

                # Combine all parts, using minimal separators
                prefix = f"{date_str}{' ' if date_str else ''}"
                suffix = f"{' ' + engagement if engagement else ''}{' ' + media_info if media_info else ''}"

                # Add the tweet with its metadata
                feed_text += f"{prefix}{tweet.text.strip()}{suffix}\n"

        except Exception as e:
            logger.error(f"Error formatting tweets: {str(e)}")

        return feed_text

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def analyze_profile_with_retries(self, username: str) -> Dict[str, Any]:
        """Analyze a Twitter profile with retries and rate limiting."""
        async with request_semaphore:  # Rate limit concurrent requests
            return await self._analyze_profile(username)

    async def _analyze_profile(self, username: str) -> Dict[str, Any]:
        """Internal method to analyze a profile."""
        logger.info(f"Starting analysis for username: {username}")

        try:
            # Get all profile content
            result = await self._get_profile_content(username)
            profile_info = result["profile_info"]
            feed_text = result["feed_text"]

            if not feed_text and not profile_info:
                logger.error(f"No content found for user: {username}")
                return {
                    "error": "No content found",
                    "username": username,
                    "date_analyzed": datetime.utcnow().isoformat(),
                }

            # Add profile context but keep it concise
            analysis_prompt = {
                "name": profile_info.get("Full Name", ""),
                "description": profile_info.get("Description", ""),
                "website": str(profile_info.get("Website", "")),
                "location": profile_info.get("Location", ""),
                "join_date": profile_info.get("Join Date", ""),
                "stats": {
                    "tweets": profile_info.get("Tweets", 0),
                    "following": profile_info.get("Following", 0),
                    "followers": profile_info.get("Followers", 0),
                    "likes": profile_info.get("Likes", 0),
                },
                "is_verified": profile_info.get("Verified", False),
                "feed_content": (
                    feed_text[:8000] if feed_text else "No recent tweets available"
                ),
            }

            logger.info(f"Sending profile data to Ollama for user {username}")

            # Get analysis from Ollama using the official library
            system_prompt = """Analyze the Twitter profile and its content to extract business information. Focus on key details only. Format as JSON with these fields:
- business_name: Business name or "Not explicitly mentioned"
- website: Business website or "Not explicitly mentioned"
- business_context: Brief business description (max 1000 words)"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(analysis_prompt, indent=2)},
            ]

            response = await self.client.chat(
                model="llama2",  # Using llama2 instead of mistral for better performance
                messages=messages,
                format="json",
                options={
                    "temperature": 0,  # Lower temperature for faster, more deterministic responses
                    "num_ctx": 4096,  # Smaller context window since we don't need 32k
                    "num_thread": 4,  # Use multiple CPU threads
                },
            )

            if not response or not response.message or not response.message.content:
                logger.error("Empty response from Ollama")
                return {"error": "Empty analysis results"}

            try:
                analysis = json.loads(response.message.content)
            except json.JSONDecodeError:
                logger.error(
                    f"Failed to parse Ollama response: {response.message.content}"
                )
                return {"error": "Failed to parse analysis results"}

            # Ensure proper encoding of feed sample
            feed_sample = (
                feed_text[:2000] if feed_text else "No recent tweets available"
            )
            feed_sample = feed_sample.encode("utf-8").decode("utf-8")

            result = {
                "username": username,
                "date_analyzed": datetime.utcnow().isoformat(),
                "feed_sample": feed_sample,
                "analysis": analysis,
            }

            return result

        except Exception as e:
            logger.error(
                f"Error analyzing profile for {username}: {str(e)}", exc_info=True
            )
            return {
                "error": f"Analysis failed: {str(e)}",
                "username": username,
                "date_analyzed": datetime.utcnow().isoformat(),
            }


async def analyze_twitter_profile(username: str) -> Dict[str, Any]:
    """Analyze a Twitter profile and return structured insights."""
    analyzer = ProfileAnalyzer()
    return await analyzer.analyze_profile_with_retries(username)
