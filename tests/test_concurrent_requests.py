import asyncio
import aiohttp
import time
from datetime import datetime
import json


async def make_request(session, username: str):
    """Make a request to analyze a profile."""
    try:
        start_time = time.time()
        async with session.post(
            "http://127.0.0.1:8001/analyze_profile", json={"username": username}
        ) as response:
            result = await response.json()
            end_time = time.time()
            return {
                "username": username,
                "status": response.status,
                "time": end_time - start_time,
                "cached": result.get("cached", False),
                "error": result.get("error", None),
                "response": result,
            }
    except Exception as e:
        return {
            "username": username,
            "status": "error",
            "time": time.time() - start_time,
            "error": str(e),
            "response": None,
        }


async def run_concurrent_tests():
    """Run multiple concurrent requests."""
    # Test usernames - mix of real and active accounts
    usernames = [
        "elonmusk",  # Active, high-profile account
        "OpenAI",  # Tech company with regular updates
        "Microsoft",  # Corporate account
        "SpaceX",  # Company with specific industry content
        "NVIDIA",  # Tech company with product announcements
    ]

    print(f"Starting concurrent tests at {datetime.now()}")
    print(
        f"Testing with {len(usernames)} requests ({len(set(usernames))} unique usernames)"
    )

    async with aiohttp.ClientSession() as session:
        tasks = [make_request(session, username) for username in usernames]
        results = await asyncio.gather(*tasks)

    # Analyze results
    successful = [
        r for r in results if isinstance(r["status"], int) and r["status"] == 200
    ]
    cached = [r for r in results if r.get("cached", False)]
    errors = [r for r in results if r.get("error") or r["status"] == "error"]

    print("\nTest Results:")
    print(f"Total requests: {len(results)}")
    print(f"Successful requests: {len(successful)}")
    print(f"Cached responses: {len(cached)}")
    print(f"Errors: {len(errors)}")

    print("\nResponse times:")
    times = [r["time"] for r in results if isinstance(r["time"], (int, float))]
    if times:
        print(f"Average response time: {sum(times)/len(times):.2f}s")
        print(f"Min response time: {min(times):.2f}s")
        print(f"Max response time: {max(times):.2f}s")

    print("\nDetailed Profile Data:")
    for result in results:
        print(f"\n{'='*80}")
        print(f"Profile: @{result['username']}")
        print(f"{'='*80}")
        print(f"Status: {result['status']}")
        print(f"Response Time: {result['time']:.2f}s")
        print(f"Cached: {result.get('cached', False)}")

        if result.get("error"):
            print(f"Error: {result['error']}")
            continue

        if result.get("response"):
            # Print raw profile information
            if "profile_info" in result["response"]:
                print("\nProfile Information:")
                for key, value in result["response"]["profile_info"].items():
                    print(f"  {key}: {value}")

            # Print feed sample with actual tweets
            if "feed_sample" in result["response"]:
                print("\nRecent Feed Sample:")
                feed_text = result["response"]["feed_sample"]
                # Split feed into individual tweets/items if possible
                feed_items = feed_text.split("\n\n")
                for i, item in enumerate(feed_items[:3], 1):  # Show first 3 items
                    print(f"\n  Tweet {i}:")
                    print("  " + item.replace("\n", "\n  "))

            # Print analysis results
            print("\nAI Analysis:")
            analysis = result["response"].get("analysis", {})
            print(f"  Business Name: {analysis.get('business_name', 'N/A')}")
            print(f"  Website: {analysis.get('website', 'N/A')}")
            print(f"  Business Context: {analysis.get('business_context', 'N/A')}")

    if errors:
        print("\nErrors encountered:")
        for error in errors:
            print(f"Username: {error['username']}, Error: {error['error']}")


async def test_rate_limiting():
    """Test rate limiting by making rapid requests."""
    print("\nTesting rate limiting...")
    async with aiohttp.ClientSession() as session:
        # Make 15 rapid requests (above our 10/minute limit)
        tasks = [make_request(session, "OpenAI") for _ in range(15)]
        results = await asyncio.gather(*tasks)

    # Count rate limited responses
    rate_limited = [
        r for r in results if isinstance(r["status"], int) and r["status"] == 429
    ]
    print(f"Rate limited responses: {len(rate_limited)} out of {len(results)}")


if __name__ == "__main__":
    print("Running concurrent request tests...")

    # Run the main concurrent tests
    asyncio.run(run_concurrent_tests())

    # Wait a bit before testing rate limiting
    time.sleep(5)

    # Test rate limiting
    asyncio.run(test_rate_limiting())
