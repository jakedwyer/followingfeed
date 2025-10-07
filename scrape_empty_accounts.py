import sys
import os
from typing import Any, Dict, List, Tuple, TypedDict
from datetime import datetime
import logging
import json
import unicodedata
import re

from dotenv import load_dotenv
from pyairtable import Api

from utils.config import load_env_variables
from utils.logging_setup import setup_logging
from twitter.nitter_scraper import NitterScraper

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Load environment variables
config = load_env_variables()

AIRTABLE_TOKEN: str = config["airtable_token"]
BASE_ID: str = config["airtable_base_id"]
TABLE_ID: str = config.get("airtable_accounts_table", "tblJCXhcrCxDUJR3F")
JSON_FILE_PATH: str = config.get("json_file_path", "user_details.json")

# Ensure critical configuration variables are present
assert AIRTABLE_TOKEN, "AIRTABLE_TOKEN is not set in the environment variables."
assert BASE_ID, "AIRTABLE_BASE_ID is not set in the environment variables."
assert TABLE_ID, "AIRTABLE_ACCOUNTS_TABLE is not set in the environment variables."

# Initialize Airtable API
api = Api(AIRTABLE_TOKEN)
table = api.table(BASE_ID, TABLE_ID)


def get_unenriched_accounts() -> List[Tuple[str, str]]:
    """
    Fetch records from Airtable that have missing 'Full Name' or 'Description'.
    Returns a list of tuples containing (record_id, username).
    """
    try:
        formula = "OR(AND({Full Name} = BLANK(), {Description} = BLANK()), {Full Name} = BLANK())"
        records = table.all(formula=formula)
        logger.info(f"Pulled {len(records)} unenriched records from Airtable")
        airtable_usernames = {
            record["fields"].get("Username", "").lower(): record["id"]
            for record in records
        }
        return [
            (record_id, username) for username, record_id in airtable_usernames.items()
        ]
    except Exception as e:
        logger.error(
            f"Error fetching unenriched records from Airtable: {e}", exc_info=True
        )
        return []


def format_data_for_airtable(profile) -> Dict[str, Any]:
    """
    Format profile data from NitterScraper to match Airtable's schema.
    Maps all available fields from the Profile class to their corresponding Airtable fields.

    Fields from Profile class:
    - fullname: str
    - username: str
    - biography: str
    - location: str
    - website: str
    - join_date: str
    - tweets_count: int
    - following_count: int
    - followers_count: int
    - likes_count: int
    - is_verified: bool
    """
    if not profile:
        return {}

    # Convert join_date to proper format if it exists
    join_date = profile.join_date.strip() if profile.join_date else ""
    if join_date.startswith("Joined "):
        join_date = join_date.replace("Joined ", "")

    return {
        # Basic Profile Information
        "Full Name": profile.fullname,
        "Username": profile.username,  # Add username to keep it in sync
        "Description": profile.biography,
        "Location": profile.location,
        "Website": profile.website,
        # Statistics
        "Followers Count": profile.followers_count,
        "Following Count": profile.following_count,
        "Tweet Count": profile.tweets_count,
        "Like Count": profile.likes_count,
        # Additional Information
        "Created At": join_date,
        # Remove fields that don't exist in Airtable schema
        # "Last Updated": datetime.utcnow().isoformat(),
        # "Has Website": bool(profile.website),
        # "Has Location": bool(profile.location),
        # "Has Bio": bool(profile.biography),
    }


class UpdateRecordDict(TypedDict):
    id: str
    fields: Dict[str, Any]


def batch_update_airtable_records(records_to_update: List[UpdateRecordDict]) -> None:
    """
    Update Airtable records with the provided data in batches.
    """
    if not records_to_update:
        logger.info("No records to update in Airtable.")
        return

    try:
        # Airtable API allows batch updates of up to 10 records per request
        BATCH_SIZE = 10
        for i in range(0, len(records_to_update), BATCH_SIZE):
            batch = records_to_update[i : i + BATCH_SIZE]
            table.batch_update(batch)
            logger.info(f"Updated batch of {len(batch)} records in Airtable.")
        logger.info(
            f"Successfully updated {len(records_to_update)} records in Airtable."
        )
    except Exception as e:
        logger.error(f"Failed to update Airtable records: {e}", exc_info=True)


def delete_airtable_record(record_id: str) -> None:
    """
    Delete a specific Airtable record by its ID.
    """
    try:
        table.delete(record_id)
        logger.info(f"Successfully deleted record {record_id} from Airtable")
    except Exception as e:
        logger.error(f"Error deleting record {record_id}: {e}", exc_info=True)


def main() -> None:
    try:
        # Initialize NitterScraper
        scraper = NitterScraper()
        logger.info("Initialized NitterScraper")

        # Get all unenriched records from Airtable
        unenriched_records = get_unenriched_accounts()
        logger.info(f"Found {len(unenriched_records)} unenriched accounts")

        if not unenriched_records:
            logger.info("No unenriched records found. Exiting.")
            return

        # Process each unenriched record
        records_to_update = []
        deleted_records_count = 0
        MAX_RETRIES = 3
        for record_id, username in unenriched_records:
            try:
                # Get profile data using NitterScraper with retries
                profile = None
                retry_count = 0

                while profile is None and retry_count < MAX_RETRIES:
                    try:
                        profile = scraper.get_profile(username)
                        if profile:
                            break
                    except Exception as e:
                        logger.warning(
                            f"Retry {retry_count+1}/{MAX_RETRIES} failed for {username}: {e}"
                        )

                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        logger.info(
                            f"Retrying {username}, attempt {retry_count+1}/{MAX_RETRIES}"
                        )

                if profile:
                    # Format data for Airtable
                    formatted_data = format_data_for_airtable(profile)

                    if formatted_data:
                        records_to_update.append(
                            {"id": record_id, "fields": formatted_data}
                        )
                        logger.info(f"Successfully scraped data for {username}")
                    else:
                        logger.warning(f"No data found for {username}")
                else:
                    logger.warning(
                        f"Could not fetch profile for {username} after {MAX_RETRIES} attempts"
                    )
                    # Only delete records that don't exist after all retries
                    delete_airtable_record(record_id)
                    deleted_records_count += 1

            except Exception as e:
                logger.error(f"Error processing {username}: {e}", exc_info=True)

        # Update Airtable with all the collected data
        if records_to_update:
            batch_update_airtable_records(records_to_update)
            logger.info(f"Updated {len(records_to_update)} records in Airtable")
        else:
            logger.warning("No records to update in Airtable")

        # Log summary of operations
        logger.info(
            f"Summary: {len(records_to_update)} records updated, {deleted_records_count} records deleted"
        )
        print(
            f"Operation completed: {len(records_to_update)} records updated, {deleted_records_count} records deleted"
        )

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
