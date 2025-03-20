import asyncio
import json
from twitter.profile_analyzer_ollama import analyze_twitter_profile


async def main():
    # Test with a known Twitter account (using Elon Musk as an example)
    username = "elonmusk"

    print(f"Analyzing profile for @{username}...")
    try:
        result = await analyze_twitter_profile(username)
        print("\nAnalysis Result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
