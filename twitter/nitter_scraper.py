import logging
import requests
import urllib3
from bs4 import BeautifulSoup, Tag
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional, Union, cast
import time
from tenacity import retry, stop_after_attempt, wait_exponential
import threading
from collections import deque

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        """
        Initialize rate limiter
        :param max_requests: Maximum number of requests allowed in time window
        :param time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = threading.Lock()

    def acquire(self):
        """Check if request can be made and update request history"""
        with self.lock:
            now = time.time()
            # Remove requests older than time window
            while self.requests and self.requests[0] <= now - self.time_window:
                self.requests.popleft()

            if len(self.requests) >= self.max_requests:
                oldest_request = self.requests[0]
                sleep_time = oldest_request + self.time_window - now
                if sleep_time > 0:
                    logger.warning(
                        f"Rate limit reached, sleeping for {sleep_time:.2f} seconds"
                    )
                    time.sleep(sleep_time)
                    # After sleeping, clean up old requests again
                    while (
                        self.requests
                        and self.requests[0] <= time.time() - self.time_window
                    ):
                        self.requests.popleft()

            self.requests.append(now)


@dataclass
class TweetStats:
    comments: int = 0
    retweets: int = 0
    quotes: int = 0
    likes: int = 0


@dataclass
class Tweet:
    text: str
    created_on: str
    stats: TweetStats
    media_urls: List[str]


@dataclass
class Profile:
    fullname: str
    username: str
    biography: str
    location: str
    website: str
    join_date: str
    tweets_count: int
    following_count: int
    followers_count: int
    likes_count: int
    is_verified: bool


class NitterScraper:
    def __init__(self, base_url: str = "http://67.207.92.143:8080"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        # Disable SSL verification warnings since we're using a local instance
        self.session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # Initialize rate limiter (45 requests per minute)
        self.rate_limiter = RateLimiter(max_requests=45, time_window=60)

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _get_page(self, username: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a profile page with retry logic."""
        try:
            # Apply rate limiting before making request
            self.rate_limiter.acquire()

            url = f"{self.base_url}/{username}"
            response = self.session.get(url, timeout=10)

            if response.status_code == 429:
                logger.warning(
                    f"Rate limited when fetching {username}, waiting before retry..."
                )
                time.sleep(5)  # Wait 5 seconds before retry
                raise Exception("Rate limited")

            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            logger.error(f"Failed to fetch profile for {username}: {str(e)}")
            return None

    def _parse_stats(self, stat_element: Optional[Tag]) -> int:
        """Parse numeric stats, handling K/M suffixes."""
        if not stat_element:
            return 0

        try:
            text = stat_element.text.strip()
            if "K" in text:
                return int(float(text.replace("K", "")) * 1000)
            elif "M" in text:
                return int(float(text.replace("M", "")) * 1000000)
            return int(text.replace(",", ""))
        except (ValueError, AttributeError):
            return 0

    def _parse_tweet_stats(self, tweet_element: Tag) -> TweetStats:
        """Parse tweet engagement statistics."""
        stats = TweetStats()
        try:
            stat_elements = tweet_element.select(".tweet-stats .tweet-stat")
            for stat in stat_elements:
                icon = stat.select_one(".icon-container span")
                if not icon:
                    continue

                count = stat.text.strip() or "0"
                count = int(count.replace(",", ""))

                icon_classes = icon.get("class", [])
                if isinstance(icon_classes, list):
                    if "icon-comment" in icon_classes:
                        stats.comments = count
                    elif "icon-retweet" in icon_classes:
                        stats.retweets = count
                    elif "icon-quote" in icon_classes:
                        stats.quotes = count
                    elif "icon-heart" in icon_classes:
                        stats.likes = count
        except Exception as e:
            logger.error(f"Error parsing tweet stats: {str(e)}")
        return stats

    def get_profile(self, username: str) -> Optional[Profile]:
        """Fetch and parse a Twitter profile."""
        soup = self._get_page(username)
        if not soup:
            return None

        try:
            profile_card = soup.select_one(".profile-card")
            if not profile_card:
                return None

            # Basic profile info
            fullname_elem = profile_card.select_one(".profile-card-fullname")
            username_elem = profile_card.select_one(".profile-card-username")

            if not fullname_elem or not username_elem:
                logger.error("Could not find required profile elements")
                return None

            fullname = cast(str, fullname_elem.text.strip())
            username = cast(str, username_elem.text.strip().lstrip("@"))

            bio = profile_card.select_one(".profile-bio")
            biography = bio.text.strip() if bio else ""

            # Location and website
            location_elem = profile_card.select_one(".profile-location")
            location = location_elem.text.strip() if location_elem else ""

            # Updated website extraction logic with proper type handling
            website = ""
            website_container = profile_card.select_one(".profile-website")
            if website_container:
                website_link = website_container.select_one("a")
                if website_link:
                    href = website_link.get("href", "")
                    if isinstance(href, str) and href:
                        website = href if href.startswith("http") else f"http://{href}"

            # Join date
            join_date = ""
            join_elem = profile_card.select_one(".profile-joindate")
            if join_elem:
                join_date = join_elem.text.replace("Joined", "").strip()

            # Stats
            stats = profile_card.select(".profile-stat-num")
            tweets_count = self._parse_stats(stats[0]) if len(stats) > 0 else 0
            following_count = self._parse_stats(stats[1]) if len(stats) > 1 else 0
            followers_count = self._parse_stats(stats[2]) if len(stats) > 2 else 0
            likes_count = self._parse_stats(stats[3]) if len(stats) > 3 else 0

            # Verification status
            is_verified = bool(profile_card.select_one(".verified-icon"))

            return Profile(
                fullname=fullname,
                username=username,
                biography=biography,
                location=location,
                website=website,
                join_date=join_date,
                tweets_count=tweets_count,
                following_count=following_count,
                followers_count=followers_count,
                likes_count=likes_count,
                is_verified=is_verified,
            )

        except Exception as e:
            logger.error(f"Error parsing profile for {username}: {str(e)}")
            return None

    def get_recent_tweets(self, username: str, limit: int = 20) -> List[Tweet]:
        """Fetch recent tweets from a profile."""
        soup = self._get_page(username)
        if not soup:
            return []

        tweets = []
        try:
            tweet_elements = soup.select(".timeline-item")
            for tweet_elem in tweet_elements[:limit]:
                # Skip retweets
                if tweet_elem.select_one(".retweet-header"):
                    continue

                # Get tweet text
                content = tweet_elem.select_one(".tweet-content")
                if not content:
                    continue
                text = cast(str, content.text.strip())

                # Get timestamp
                date_elem = tweet_elem.select_one(".tweet-date a")
                title = date_elem.get("title") if date_elem else None
                created_on = str(title) if title else "unknown date"

                # Get media URLs
                media_urls = []
                media_elements = tweet_elem.select(".attachment.image a")
                for media in media_elements:
                    href = media.get("href")
                    if href and isinstance(href, str):
                        url = (
                            href
                            if href.startswith("http")
                            else f"{self.base_url}{href}"
                        )
                        media_urls.append(url)

                # Get tweet stats
                stats = self._parse_tweet_stats(tweet_elem)

                tweets.append(
                    Tweet(
                        text=text,
                        created_on=created_on,
                        stats=stats,
                        media_urls=media_urls,
                    )
                )

                if len(tweets) >= limit:
                    break

        except Exception as e:
            logger.error(f"Error fetching tweets for {username}: {str(e)}")

        return tweets
