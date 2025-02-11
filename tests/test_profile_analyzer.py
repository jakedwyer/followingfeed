import asyncio
import pytest
from twitter.profile_analyzer import analyze_twitter_profile
import requests
import json


def print_json(data):
    """Print JSON with proper encoding for emojis."""
    print(json.dumps(data, ensure_ascii=False, indent=2))


async def test_profile_analyzer():
    """Test the profile analyzer directly."""
    # Test with multiple known public profiles
    usernames = ["elonmusk", "BillGates", "BarackObama"]

    for username in usernames:
        print(f"\nTesting profile: {username}")
        result = await analyze_twitter_profile(username)

        assert result is not None
        assert "username" in result
        assert "date_analyzed" in result

        if "error" in result:
            print(f"Got error for {username}: {result['error']}")
            continue

        assert "feed_sample" in result
        assert "analysis" in result

        print("\nProfile Analysis Results for {username}:")
        print_json(result)

        # If we got a successful result, we can break
        if not result.get("error"):
            break


async def test_api_endpoint():
    """Test the FastAPI endpoint."""
    try:
        # Test with multiple known public profiles
        usernames = ["elonmusk", "BillGates", "BarackObama"]

        for username in usernames:
            print(f"\nTesting API with profile: {username}")
            response = requests.post(
                "http://localhost:8000/analyze_profile", json={"username": username}
            )

            if response.status_code != 200:
                print(f"API error for {username}: {response.text}")
                continue

            result = response.json()

            assert "username" in result
            assert "date_analyzed" in result

            if "error" in result:
                print(f"Got error for {username}: {result['error']}")
                continue

            assert "feed_sample" in result
            assert "analysis" in result

            print(f"\nAPI Results for {username}:")
            print_json(result)

            # If we got a successful result, we can break
            if not result.get("error"):
                break

    except requests.exceptions.ConnectionError:
        print("\nAPI test failed: Make sure the FastAPI server is running on port 8000")


if __name__ == "__main__":
    # Run both tests
    asyncio.run(test_profile_analyzer())
    asyncio.run(test_api_endpoint())
