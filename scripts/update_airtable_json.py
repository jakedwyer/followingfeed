# take the data from user_details.json and put it into airtable, updating existing records with data from the json file, matching on username

import json
import os
import logging
from typing import Dict, Any, List
from datetime import datetime
from utils.airtable import (
    fetch_records_from_airtable,
    update_airtable_records,
    post_airtable_records,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "appYCZWcmNBXB2uUS")
TABLE_ID = os.environ.get("AIRTABLE_ACCOUNTS_TABLE", "tblJCXhcrCxDUJR3F")

if not AIRTABLE_TOKEN:
    raise ValueError("AIRTABLE_TOKEN environment variable is not set")

# Load schema to get valid fields
with open("airtableschema.json", "r") as f:
    schema = json.load(f)

# Get fields for Accounts table
accounts_table = next(table for table in schema["tables"] if table["id"] == TABLE_ID)
valid_fields = {field["name"] for field in accounts_table["fields"]}


def format_date(date_string: str) -> str | None:
    if not date_string:
        return None

    # Check if already in YYYY-MM-DD format
    if len(date_string) == 10 and date_string[4] == "-" and date_string[7] == "-":
        return date_string

    try:
        # Attempt to parse the date string in ISO 8601 format
        date_obj = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        logger.warning(f"Invalid date format: {date_string}")
        return None


def prepare_record_data(data: Dict[str, Any]) -> Dict[str, Any]:
    prepared_data = {}
    for key, value in data.items():
        # Skip if field not in schema
        if key not in valid_fields:
            continue

        if key == "Created At":
            formatted_date = format_date(value)
            if formatted_date:
                prepared_data[key] = formatted_date
            # Do not include the field if date is invalid or None
        elif key in [
            "Followers Count",
            "Following Count",
            "Tweet Count",
            "Listed Count",
            "Like Count",
        ]:
            # Only include if the value is not blank and not zero
            try:
                int_value = int(value)
                if int_value > 0:
                    prepared_data[key] = int_value
            except (ValueError, TypeError):
                pass  # Skip this field if it can't be converted to an integer
        elif value and value != "0":  # Only include non-empty and non-zero values
            prepared_data[key] = value
    return prepared_data


def main():
    # Load the data from user_details.json
    try:
        with open("user_details.json", "r") as f:
            user_details = json.load(f)
    except FileNotFoundError:
        logger.error("user_details.json file not found")
        return
    except json.JSONDecodeError:
        logger.error("Error decoding user_details.json")
        return

    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }

    # Fetch all records from Airtable
    airtable_records = fetch_records_from_airtable(TABLE_ID, headers)
    if not airtable_records:
        logger.error("Failed to fetch records from Airtable. Exiting.")
        return

    airtable_usernames = {
        record["fields"].get("Username") for record in airtable_records
    }

    records_to_update = []
    for username, data in user_details.items():
        if username not in airtable_usernames:
            # Add logic for new records if needed
            continue

        prepared_data = prepare_record_data(data)
        if prepared_data:
            # Find the record ID from Airtable
            record = next(
                (
                    rec
                    for rec in airtable_records
                    if rec["fields"].get("Username") == username
                ),
                None,
            )
            if record:
                records_to_update.append({"id": record["id"], "fields": prepared_data})

    logger.info(f"Found {len(records_to_update)} records to update")

    # Batch update records (Airtable allows up to 10 records per request)
    BATCH_SIZE = 10
    successful_updates = 0
    for i in range(0, len(records_to_update), BATCH_SIZE):
        batch = records_to_update[i : i + BATCH_SIZE]
        response = update_airtable_records(TABLE_ID, batch, headers)
        if response is None:
            logger.error(
                f"Failed to PATCH records in {TABLE_ID}. No response received."
            )
        elif response.status_code != 200:
            logger.error(
                f"Failed to PATCH records in {TABLE_ID}. Status code: {response.status_code}"
            )
            logger.error(f"Response content: {response.content}")
        else:
            successful_updates += len(batch)
            logger.info(f"Successfully updated batch {i // BATCH_SIZE + 1}")

    logger.info(f"Successfully updated {successful_updates} records in total")


if __name__ == "__main__":
    main()
