from pnytter import Pnytter
import json


def test_basic_pnytter():
    """Test basic pnytter functionality."""
    pnytter = Pnytter(nitter_instances=["https://nitter.net"])

    # Test getting a profile
    print("\nTesting profile fetch...")
    profile = pnytter.find_user("elonmusk")
    if profile:
        print("Profile data:")
        print(f"Fullname: {profile.fullname}")
        print(f"Biography: {profile.biography}")
        print(f"Stats: {profile.stats}")
    else:
        print("Could not fetch profile")

    # Test getting tweets
    print("\nTesting tweet fetch...")
    tweets = pnytter.get_user_tweets_list(
        "elonmusk", filter_from="2024-01-01", filter_to="2024-02-10"
    )
    if tweets:
        print(f"Found {len(tweets)} tweets")
        for tweet in tweets[:3]:  # Show first 3 tweets
            print(f"\nTweet: {tweet.text}")
            print(f"Created on: {tweet.created_on}")
            if tweet.stats:
                print(f"Stats: {tweet.stats}")
    else:
        print("Could not fetch tweets")


if __name__ == "__main__":
    test_basic_pnytter()
