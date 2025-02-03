import os
import json
import logging
import time
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

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Load environment variables
env_vars = load_env_variables()
BEARER_TOKEN = env_vars.get("twitter_bearer_token")
AIRTABLE_TOKEN = env_vars.get("airtable_token")
TABLE_ID = env_vars.get("airtable_followers_table")


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
API_CALLS_MADE = 0
API_RETRY_LIMIT = 5  # Maximum number of retries for a single request


# Define a custom exception for rate limiting
class RateLimitException(Exception):
    pass


def fetch_profile(username, retries=0):
    global API_CALLS_MADE
    if not BEARER_TOKEN:
        logger.error("BEARER_TOKEN is not set")
        return None

    try:
        API_CALLS_MADE += 1
        user_data = fetch_twitter_data_api(username, bearer_token=BEARER_TOKEN)
        if not user_data:
            logger.error(f"No data returned for {username}")
            return None
        return user_data
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            retry_after = int(
                e.response.headers.get("Retry-After", 60)
            )  # Default to 60 seconds if not provided
            logger.warning(
                f"Rate limit reached. Retrying after {retry_after} seconds..."
            )
            if retries < API_RETRY_LIMIT:
                time.sleep(retry_after)
                return fetch_profile(username, retries + 1)
            else:
                logger.error(f"Max retries exceeded for {username}. Skipping.")
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
    }
    update_user_details(username, formatted_data)


def create_updated_record(record, profile):
    updated_record = {
        "id": record["id"],
        "fields": {
            "Account ID": str(profile.get("id", "")),
            "Full Name": str(profile.get("name", "")),
            "Description": str(profile.get("description", "")),
        },
    }

    if "created_at" in profile:
        try:
            created_at = datetime.strptime(
                profile["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            updated_record["fields"]["Created At"] = created_at.strftime("%Y-%m-%d")
        except ValueError as ve:
            logger.error(f"Date parsing error for {record['id']}: {ve}")

    # Remove any None or empty string values
    updated_record["fields"] = {
        k: v for k, v in updated_record["fields"].items() if v not in [None, ""]
    }

    return updated_record if updated_record["fields"] else None


def save_user_data(username: str, user_data: dict, json_file_path: str):
    # Load existing data
    if os.path.exists(json_file_path):
        try:
            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {json_file_path}")
            data = {}
    else:
        data = {}

    # Update the data with the new entry
    data[username] = {
        "data": user_data,
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }

    # Save back to JSON file
    try:
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved data for '{username}' to {json_file_path}")
    except Exception as e:
        logger.error(f"Error writing to {json_file_path}: {e}")


def process_batch(updated_records):
    """Process a batch of records and update Airtable"""
    if not updated_records:  # Don't process empty batches
        return []

    try:
        # Log the batch we're trying to update
        logger.debug(f"Attempting to update batch with {len(updated_records)} records")
        logger.debug(f"Batch content: {json.dumps(updated_records, indent=2)}")

        url = f"https://api.airtable.com/v0/{os.getenv('AIRTABLE_BASE_ID')}/{TABLE_ID}"
        headers = {
            "Authorization": f"Bearer {AIRTABLE_TOKEN}",
            "Content-Type": "application/json",
        }

        response = requests.patch(
            url, headers=headers, json={"records": updated_records}
        )

        # Log the response
        logger.debug(f"Airtable API Response Status: {response.status_code}")
        logger.debug(f"Airtable API Response: {response.text}")

        response.raise_for_status()

        if response.status_code in [200, 201]:
            logger.info(
                f"Successfully updated batch of {len(updated_records)} records in Airtable"
            )
        else:
            logger.error(f"Failed to update batch. Status code: {response.status_code}")
            logger.error(f"Response content: {response.text}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error updating batch: {str(e)}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"Response status code: {e.response.status_code}")
            logger.error(f"Response content: {e.response.text}")
    except Exception as e:
        logger.error(f"Error processing batch: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")

    return []  # Return empty list for next batch


def main():
    try:
        if not check_tokens():
            logger.error("Required tokens are missing. Exiting the script.")
            return

        if TABLE_ID is None:
            logger.error("TABLE_ID is not set. Exiting the script.")
            return

        # Fetch all accounts from Airtable without any filter
        accounts_to_update = fetch_records_from_airtable(
            TABLE_ID,
            {"Authorization": f"Bearer {AIRTABLE_TOKEN}"},
        )[
            :MAX_API_CALLS
        ]  # Limit the records to MAX_API_CALLS

        BATCH_SIZE = 10  # Process in smaller batches
        updated_records = []

        for record in accounts_to_update:
            if API_CALLS_MADE >= MAX_API_CALLS:
                logger.info(
                    f"Reached maximum of {MAX_API_CALLS} Twitter API calls. Stopping further profile fetches."
                )
                # Process final batch before breaking
                if updated_records:
                    process_batch(updated_records)
                break

            username = record["fields"].get("Username")
            if not username:
                logger.warning(
                    f"Record {record['id']} is missing 'Username'. Skipping."
                )
                continue

            try:
                profile = fetch_profile(username)
            except RateLimitException as e:
                # Process any remaining records before exiting
                if updated_records:
                    process_batch(updated_records)
                logger.error(e)
                logger.info("Exiting the script due to rate limit.")
                sys.exit(1)

            if profile:
                update_user_profile(username, profile)
                updated_record = create_updated_record(record, profile)
                if updated_record:
                    updated_records.append(updated_record)

                    # Process batch when it reaches BATCH_SIZE
                    if len(updated_records) >= BATCH_SIZE:
                        updated_records = process_batch(updated_records)
            else:
                logger.warning(
                    f"Failed to fetch profile for {username}. Skipping Airtable update."
                )

        # Process any remaining records in the final batch
        if updated_records:
            process_batch(updated_records)

        logger.info(f"Total API calls made: {API_CALLS_MADE}")

    except RateLimitException as e:
        logger.error(e)
        logger.info("Exiting the script due to rate limit.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
