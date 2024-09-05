# take the data from user_details.json and put it into airtable, updating existing records with data from the json file, matching on username

import json
import os
import logging
from typing import Dict, Any, List
from datetime import datetime
from utils.airtable import fetch_records_from_airtable, update_airtable_records, post_airtable_records

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
AIRTABLE_TOKEN = os.environ.get('AIRTABLE_TOKEN')
BASE_ID = os.environ.get('AIRTABLE_BASE_ID', 'appYCZWcmNBXB2uUS')
TABLE_ID = os.environ.get('AIRTABLE_ACCOUNTS_TABLE', 'tblJCXhcrCxDUJR3F')

if not AIRTABLE_TOKEN:
    raise ValueError("AIRTABLE_TOKEN environment variable is not set")

def format_date(date_string: str) -> str:
    if not date_string:
        return None
    try:
        # Attempt to parse the date string
        date_obj = datetime.strptime(date_string, "%Y-%m-%d")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        # If parsing fails, return None
        return None

def prepare_record_data(data: Dict[str, Any]) -> Dict[str, Any]:
    prepared_data = {}
    for key, value in data.items():
        if key == 'Created At':
            formatted_date = format_date(value)
            if formatted_date:
                prepared_data[key] = formatted_date
        elif key in ['Followers Count', 'Following Count', 'Tweet Count', 'Listed Count', 'Like Count']:
            # Only include if the value is not blank and not zero
            try:
                int_value = int(value)
                if int_value > 0:
                    prepared_data[key] = int_value
            except (ValueError, TypeError):
                pass  # Skip this field if it can't be converted to an integer
        elif value and value != '0':  # Only include non-empty and non-zero values
            prepared_data[key] = value
    return prepared_data

def main():
    # Load the data from user_details.json
    try:
        with open('user_details.json', 'r') as f:
            user_details = json.load(f)
    except FileNotFoundError:
        logger.error("user_details.json file not found")
        return
    except json.JSONDecodeError:
        logger.error("Error decoding user_details.json")
        return

    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }

    # Fetch all records from Airtable
    airtable_records = fetch_records_from_airtable(TABLE_ID, headers)
    if not airtable_records:
        logger.error("Failed to fetch records from Airtable. Exiting.")
        return
    airtable_usernames = {record['fields'].get('Username', '').lower(): record for record in airtable_records}

    records_to_update = []
    records_to_create = []

    for username, user_data in user_details.items():
        if isinstance(user_data, dict) and 'data' in user_data:
            normalized_username = username.lower()
            prepared_data = prepare_record_data(user_data['data'])
            if normalized_username in airtable_usernames:
                # Update existing record
                record = airtable_usernames[normalized_username]
                records_to_update.append({
                    "id": record['id'],
                    "fields": prepared_data
                })
            else:
                # Create new record
                records_to_create.append({
                    "fields": {
                        "Username": username,
                        **prepared_data
                    }
                })
        else:
            logger.warning(f"Skipping invalid record for username: {username}")

    # Update existing records
    if records_to_update:
        update_airtable_records(records_to_update, TABLE_ID, headers)
    
    # Create new records
    if records_to_create:
        post_airtable_records(records_to_create, TABLE_ID, headers)

    logger.info(f"Updated {len(records_to_update)} records")
    logger.info(f"Created {len(records_to_create)} new records")

if __name__ == "__main__":
    main()