from twitter.profile_analyzer import analyze_twitter_profile
from utils.config import load_env_variables

# Load environment variables (make sure .env file exists with required credentials)
config = load_env_variables()

# Analyze a single profile
username = "elonmusk"  # or any other Twitter username
result = analyze_twitter_profile(username)

# Print the results
print(f"Analysis for {username}:")
if "error" in result:
    print(f"Error: {result['error']}")
else:
    print(f"Business Name: {result['analysis']['business_name']}")
    print(f"Website: {result['analysis']['website']}")
    print(f"Business Context: {result['analysis']['business_context']}")
    print(f"\nTweet Sample:\n{result['feed_sample']}")
