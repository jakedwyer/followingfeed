import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from utils.airtable import update_airtable_records, fetch_records_from_airtable
from twitter.twitter import fetch_twitter_data_api
import requests
from utils.user_data import update_user_details
from utils.config import load_env_variables
import sys

from utils.logging_setup import setup_logging

load_dotenv()

# Remove or comment out the following lines
# logging.basicConfig(
#     level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
# )

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Replace the existing BEARER_TOKEN and AIRTABLE_TOKEN assignments
env_vars = load_env_variables()
BEARER_TOKEN = env_vars.get("twitter_bearer_token")
AIRTABLE_TOKEN = env_vars.get("airtable_token")
TABLE_ID = env_vars.get("airtable_accounts_table")


# Add this function to check if the tokens are loaded properly
def check_tokens():
    if not BEARER_TOKEN:
        logger.error("Twitter BEARER_TOKEN is not set or loaded properly")
        return False
    if not AIRTABLE_TOKEN:
        logger.error("AIRTABLE_TOKEN is not set or loaded properly")
        return False
    if not TABLE_ID:
        logger.error("AIRTABLE_ACCOUNTS_TABLE is not set or loaded properly")
        return False
    return True


MAX_API_CALLS = 500


# Define a custom exception for rate limiting
class RateLimitException(Exception):
    pass


def fetch_profile(username):
    if not BEARER_TOKEN:
        logger.error("BEARER_TOKEN is not set")
        return None

    try:
        user_data = fetch_twitter_data_api(username, bearer_token=BEARER_TOKEN)
        if not user_data:
            logger.error(f"No data returned for {username}")
            return None
        return user_data
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.error(
                f"Twitter API rate limit reached for {username}. Stopping the script."
            )
            raise RateLimitException("Twitter API rate limit reached")
        logger.error(f"HTTPError fetching profile for {username}: {e}")
    except Exception as e:
        logger.error(f"Error fetching profile for {username}: {e}")
    return None


def update_user_profile(username, profile):
    formatted_data = {
        "Account ID": str(profile.get("id", "")),
        "Username": username,
        "Full Name": str(profile.get("name", "")),
        "Description": str(profile.get("description", "")),
        "Location": str(profile.get("location", "")),
        "Website": str(profile.get("url", "")),
        "Created At": profile.get("created_at", ""),
        "Followers Count": int(
            profile.get("public_metrics", {}).get("followers_count", 0)
        ),
        "Following Count": int(
            profile.get("public_metrics", {}).get("following_count", 0)
        ),
        "Tweet Count": int(profile.get("public_metrics", {}).get("tweet_count", 0)),
        "Listed Count": int(profile.get("public_metrics", {}).get("listed_count", 0)),
        "Like Count": int(profile.get("public_metrics", {}).get("like_count", 0)),
    }
    update_user_details(username, formatted_data)


def create_updated_record(record, profile):
    updated_record = {
        "id": record["id"],
        "fields": {
            "Account ID": str(profile.get("id", "")),
            "Full Name": str(profile.get("name", "")),
            "Description": str(profile.get("description", "")),
            "Listed Count": int(
                profile.get("public_metrics", {}).get("listed_count", 0)
            ),
            "Followers Count": int(
                profile.get("public_metrics", {}).get("followers_count", 0)
            ),
            "Following Count": int(
                profile.get("public_metrics", {}).get("following_count", 0)
            ),
            "Location": str(profile.get("location", "")),
            "Website": str(profile.get("url", "")),
        },
    }

    if "created_at" in profile:
        try:
            created_at = datetime.strptime(
                profile["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            updated_record["fields"]["Created At"] = created_at.strftime("%Y-%m-%d")
        except ValueError as ve:
            logger.error(
                f"Date parsing error for {record['id']} ({record['fields'].get('Username', '')}): {ve}"
            )
            updated_record["fields"]["Created At"] = profile[
                "created_at"
            ]  # Fallback to original

    return updated_record


def main():
    try:
        if not check_tokens():
            logger.error("Required tokens are missing. Exiting the script.")
            return

        if TABLE_ID is None:
            logger.error("TABLE_ID is not set. Exiting the script.")
            return

        accounts_to_update = [
            record
            for record in fetch_records_from_airtable(
                TABLE_ID, {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
            )
            if not record["fields"].get("Account ID")
        ]

        api_calls = 0
        updated_records = []

        for record in accounts_to_update:
            if api_calls >= MAX_API_CALLS:
                logger.info(
                    f"Reached maximum of {MAX_API_CALLS} Twitter API calls. Stopping further profile fetches."
                )
                break

            username = record["fields"].get("Username")
            if not username:
                logger.warning(
                    f"Record {record['id']} is missing 'Username'. Skipping."
                )
                continue

            profile = fetch_profile(username)  # May raise RateLimitException

            if profile:
                api_calls += 1
                update_user_profile(username, profile)
                updated_record = create_updated_record(record, profile)
                if updated_record:
                    updated_records.append(updated_record)
            else:
                logger.warning(
                    f"Failed to fetch profile for {username}. Skipping Airtable update."
                )

        if updated_records:
            success = update_airtable_records(
                updated_records, TABLE_ID, {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
            )
            if success:
                logger.info(f"Updated {len(updated_records)} records in Airtable")
            else:
                logger.error("Failed to update some records in Airtable")
        else:
            logger.info("No records to update in Airtable")

        logger.info(f"Total API calls made: {api_calls}")

    except RateLimitException as e:
        logger.error(e)
        logger.info("Exiting the script due to rate limit.")
        sys.exit(1)


if __name__ == "__main__":
    main()
