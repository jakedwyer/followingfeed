import asyncio
import os
import sys
from pathlib import Path

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.utils.selenium_profile_creator import TwitterProfileCreator
from dotenv import load_dotenv


async def main():
    load_dotenv()

    # Get credentials from environment variables
    api_key = os.getenv("AIRTOP_API_KEY")
    twitter_username = os.getenv("TWITTER_USERNAME")
    twitter_password = os.getenv("TWITTER_PASSWORD")

    if not all([api_key, twitter_username, twitter_password]):
        raise ValueError("Missing required environment variables")

    creator = TwitterProfileCreator(str(api_key))

    # Check if we already have a saved profile
    saved_profile = creator.get_saved_profile()
    if saved_profile:
        print(f"Found existing profile: {saved_profile['profile_id']}")
        return saved_profile["profile_id"]

    # Create new profile if none exists
    profile_id = await creator.create_and_save_profile(
        username=str(twitter_username), password=str(twitter_password)
    )

    if profile_id:
        print(f"Successfully created new profile: {profile_id}")
        return profile_id
    else:
        print("Failed to create profile")
        return None


if __name__ == "__main__":
    asyncio.run(main())
