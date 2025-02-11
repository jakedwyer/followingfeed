from twitter.nitter_scraper import NitterScraper
import json
import urllib3

# Disable SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def test_nitter_scraper():
    """Test the custom Nitter scraper functionality."""
    scraper = NitterScraper(base_url="http://67.207.92.143:8080")

    # Test getting a profile
    print("\nTesting profile fetch...")
    profile = scraper.get_profile("nvidia")
    if profile:
        print("Profile data:")
        print(f"Name: {profile.fullname}")
        print(f"Bio: {profile.biography}")
        print(f"Location: {profile.location}")
        print(f"Website: {profile.website}")
        print(f"Join date: {profile.join_date}")
        print(f"Followers: {profile.followers_count}")
        print(f"Following: {profile.following_count}")
        print(f"Tweets: {profile.tweets_count}")
        print(f"Verified: {profile.is_verified}")
    else:
        print("Could not fetch profile")

    # Test getting tweets
    print("\nTesting tweet fetch...")
    tweets = scraper.get_recent_tweets("nvidia", limit=5)
    if tweets:
        print(f"Found {len(tweets)} tweets")
        for i, tweet in enumerate(tweets, 1):
            print(f"\nTweet {i}:")
            print(f"Text: {tweet.text[:100]}...")
            print(f"Created on: {tweet.created_on}")
            print(f"Stats: {json.dumps(tweet.stats.__dict__, indent=2)}")
            if tweet.media_urls:
                print(f"Media URLs: {tweet.media_urls}")
    else:
        print("Could not fetch tweets")


if __name__ == "__main__":
    test_nitter_scraper()
