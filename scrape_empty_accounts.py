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
from utils.airtable import (
    fetch_records_from_airtable,
    update_airtable_records,
    airtable_api_request,
)
from utils.logging_setup import setup_logging
from scraping.scraping import (
    init_driver,
    load_cookies,
    update_twitter_data,
    parse_date,
)

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
    Returns a list of tuples containing record ID and username.
    """
    try:
        records = fetch_records_from_airtable(
            TABLE_ID,
            {"Authorization": f"Bearer {AIRTABLE_TOKEN}"},
            formula="OR({Full Name} = BLANK(), {Description} = BLANK())",
        )
        logger.info(f"Pulled {len(records)} unenriched records from Airtable")
        return [
            (record["id"], record["fields"]["Username"].lower())
            for record in records
            if "Username" in record.get("fields", {})
        ]
    except Exception as e:
        logger.error(
            f"Error fetching unenriched records from Airtable: {e}", exc_info=True
        )
        return []


def load_and_clean_data() -> Dict[str, Any]:
    """
    Load existing user data from JSON file and clean it.
    Removes records with missing or empty 'data' fields.
    """
    try:
        with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cleaned_data = {}
        for username, user_data in data.items():
            username_lower = username.lower()
            if (
                "data" in user_data
                and isinstance(user_data["data"], dict)
                and user_data["data"]  # Ensure 'data' is not empty
            ):
                cleaned_data[username_lower] = {
                    "data": format_data_for_airtable(user_data["data"]),
                    "last_updated": user_data.get("last_updated", ""),
                }
            else:
                logger.debug(
                    f"Skipping user '{username}' as 'data' is missing or empty."
                )
        removed_count = len(data) - len(cleaned_data)
        if removed_count > 0:
            logger.warning(
                f"Removed {removed_count} erroneous or incomplete records from JSON data"
            )
            save_data(cleaned_data)
        logger.info(
            f"Loaded and cleaned {len(cleaned_data)} records from {JSON_FILE_PATH}"
        )
        return cleaned_data
    except FileNotFoundError:
        logger.warning(
            f"JSON file {JSON_FILE_PATH} not found. Starting with empty data."
        )
        return {}
    except json.JSONDecodeError:
        logger.error(
            f"Error decoding JSON from {JSON_FILE_PATH}. Check if the file is valid JSON.",
            exc_info=True,
        )
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading data: {e}", exc_info=True)
        return {}


def format_data_for_airtable(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format user data to match Airtable's schema.
    Cleans text fields and parses dates.
    Preserves line breaks and rich text formatting.
    """
    formatted_data = {
        "Account ID": data.get("Username", ""),
        "Full Name": clean_text(data.get("Full Name", "")),
        "Description": clean_text(data.get("Description", "")),
        "Location": clean_text(data.get("Location", "")),
        "Website": data.get("Website", ""),
        "Followers Count": data.get("Followers Count", 0),
        "Following Count": data.get("Following Count", 0),
        "Tweet Count": data.get("Tweet Count", 0),
        "Listed Count": data.get("Listed Count", 0),
        "Like Count": data.get("Like Count", 0),
    }

    created_at = data.get("Created At", "")
    if created_at:
        formatted_data["Created At"] = parse_date(created_at)

    return formatted_data


def save_data(data: Dict[str, Any]) -> None:
    """
    Save user data to the JSON file.
    """
    try:
        with open(JSON_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(data)} records to {JSON_FILE_PATH}")
    except Exception as e:
        logger.error(f"Error saving data to {JSON_FILE_PATH}: {e}", exc_info=True)


class UpdateRecordDict(TypedDict):
    id: str
    fields: Dict[str, Any]


def update_airtable(records_to_update: List[UpdateRecordDict]) -> None:
    """
    Update Airtable records with the provided data.
    """
    if not records_to_update:
        logger.info("No records to update in Airtable.")
        return

    try:
        # Airtable API allows batch updates of up to 10 records per request
        BATCH_SIZE = 10
        for i in range(0, len(records_to_update), BATCH_SIZE):
            batch = records_to_update[i : i + BATCH_SIZE]
            update_airtable_records(
                batch,
                TABLE_ID,
                {
                    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
                    "Content-Type": "application/json",
                },
            )
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
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        response = airtable_api_request(
            "DELETE", TABLE_ID, headers, record_id=record_id
        )
        if response is not None:
            logger.info(f"Successfully deleted record {record_id} from Airtable")
        else:
            logger.error(f"Failed to delete record {record_id} from Airtable")
    except Exception as e:
        logger.error(f"Error deleting record {record_id}: {e}", exc_info=True)


def clean_text(text: str) -> str:
    """
    Normalize whitespace and perform optional cleaning.
    Preserves non-ASCII characters and line breaks to maintain rich text integrity.
    """
    # Normalize Unicode characters
    text = unicodedata.normalize("NFKC", text)
    # Remove unwanted control characters while preserving printable characters and line breaks
    text = "".join(c for c in text if c.isprintable() or c == "\n")
    # Normalize whitespace within each line but preserve line breaks
    lines = text.split("\n")
    cleaned_lines = [re.sub(r"\s+", " ", line).strip() for line in lines]
    cleaned_text = "\n".join(cleaned_lines)
    return cleaned_text


def enrich_with_existing_data(
    unenriched_records: List[Tuple[str, str]], existing_data: Dict[str, Any]
) -> Tuple[List[UpdateRecordDict], List[Tuple[str, str]]]:
    """
    Separate records into those that can be enriched with existing JSON data
    and those that require scraping.
    """
    records_with_data = []
    records_without_data = []

    for record_id, username in unenriched_records:
        if username in existing_data:
            records_with_data.append(
                {
                    "id": record_id,
                    "fields": existing_data[username]["data"],
                }
            )
        else:
            records_without_data.append((record_id, username))

    logger.info(f"Records with existing data to update: {len(records_with_data)}")
    logger.info(f"Records without existing data to scrape: {len(records_without_data)}")

    return records_with_data, records_without_data


def enrich_with_scraped_data(
    driver, records_to_scrape: List[Tuple[str, str]]
) -> Dict[str, Any]:
    """
    Scrape data for the given records and return the enriched data.
    """
    try:
        enriched_data = update_twitter_data(
            driver,
            records_to_scrape,
            AIRTABLE_TOKEN,
            BASE_ID,
            TABLE_ID,
        )
        if isinstance(enriched_data, dict):
            logger.info(f"Enriched {len(enriched_data)} records through scraping.")
        else:
            logger.error("Enriched data is not a dictionary as expected.")
            enriched_data = {}
        return enriched_data
    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)
        return {}


def main() -> None:
    driver = None
    try:
        # Step 1: Load existing data from JSON file
        existing_data = load_and_clean_data()

        # Step 2: Get all unenriched records from Airtable
        unenriched_records = get_unenriched_accounts()

        logger.info(f"Total unenriched accounts in Airtable: {len(unenriched_records)}")
        logger.info(f"Total accounts in JSON file: {len(existing_data)}")

        if not unenriched_records:
            logger.info("No unenriched records found. Exiting.")
            return

        # Step 3: Enrich with existing JSON data
        records_with_data, records_to_scrape = enrich_with_existing_data(
            unenriched_records, existing_data
        )

        # Step 4: Update Airtable with existing JSON data
        if records_with_data:
            update_airtable(records_with_data)
            logger.info(
                f"Updated {len(records_with_data)} records with existing JSON data"
            )

        # Step 5: Scrape and enrich remaining records
        if records_to_scrape:
            driver = init_driver()
            cookie_path = config.get("cookie_path")
            if not cookie_path:
                logger.error("COOKIE_PATH is not set in the environment variables.")
                sys.exit(1)
            load_cookies(driver, cookie_path)

            enriched_data = enrich_with_scraped_data(driver, records_to_scrape)

            if enriched_data:
                # Step 6: Save the newly scraped data to user_details.json
                for username, data in enriched_data.items():
                    existing_data[username] = {
                        "data": format_data_for_airtable(data),
                        "last_updated": datetime.now().isoformat(),
                    }
                save_data(existing_data)

                # Step 7: Prepare records to update Airtable with scraped data
                scraped_records_to_update = []
                for record_id, username in records_to_scrape:
                    if username in enriched_data:
                        scraped_records_to_update.append(
                            {
                                "id": record_id,
                                "fields": existing_data[username]["data"],
                            }
                        )

                # Update Airtable with scraped data
                if scraped_records_to_update:
                    update_airtable(scraped_records_to_update)
                    logger.info(
                        f"Updated {len(scraped_records_to_update)} records with scraped data"
                    )
            else:
                logger.warning(
                    "No data was scraped. Skipping update with scraped data."
                )
        else:
            logger.info("No records require scraping.")

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
    finally:
        if driver:
            try:
                logger.info("Closing WebDriver...")
                driver.quit()
                logger.info("WebDriver closed successfully.")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}", exc_info=True)


if __name__ == "__main__":
    main()
