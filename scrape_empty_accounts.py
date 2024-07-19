import sys
import os
import json
import requests
import logging
from typing import Dict, List, Tuple, Optional, Any, TypedDict
from datetime import datetime
from twitter.twitter import fetch_twitter_data_api  # Make sure this line is present
from pyairtable import Api
from scraping.scraping import init_driver, load_cookies, update_twitter_data


# Constants
BASE_ID = 'appYCZWcmNBXB2uUS'
TABLE_ID = 'tblJCXhcrCxDUJR3F'
JSON_FILE_PATH = 'user_details.json'
AIRTABLE_BATCH_SIZE = 10
TWITTER_API_ENDPOINT = 'https://api.twitter.com/2/users/by/username'
TWITTER_API_FIELDS = 'id,name,username,created_at,description,public_metrics'
AIRTABLE_API_ENDPOINT = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment variables
AIRTABLE_TOKEN = os.environ.get('AIRTABLE_TOKEN')
TWITTER_BEARER_TOKEN = os.environ.get('BEARER_TOKEN')

if not AIRTABLE_TOKEN or not TWITTER_BEARER_TOKEN:
    raise ValueError("AIRTABLE_TOKEN or BEARER_TOKEN environment variable is not set")

# Initialize Airtable API
api = Api(AIRTABLE_TOKEN)
table = api.table(BASE_ID, TABLE_ID)

def fetch_twitter_data_api(username: str) -> Optional[Dict[str, Any]]:
    url = f"{TWITTER_API_ENDPOINT}/{username}"
    headers = {
        "Authorization": f"Bearer {TWITTER_BEARER_TOKEN}",
        "User-Agent": "TwitterDevSampleCode"
    }
    params = {"user.fields": TWITTER_API_FIELDS}
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('data')
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from Twitter API: {e}")
        return None

def get_unenriched_accounts() -> List[Tuple[str, str]]:
    try:
        records = table.all(formula="NOT({Account ID})")
        logger.info(f"Pulled {len(records)} unenriched records from Airtable")
        return [(record['id'], record['fields']['Username'].lower()) for record in records if 'Username' in record['fields']]
    except Exception as e:
        logger.error(f"Error fetching records from Airtable: {e}")
        return []

def load_and_clean_data() -> Dict[str, Any]:
    try:
        with open(JSON_FILE_PATH, 'r') as f:
            data = json.load(f)
        cleaned_data = {k.lower(): v for k, v in data.items() if 'data' in v and isinstance(v['data'], dict)}
        removed_count = len(data) - len(cleaned_data)
        if removed_count > 0:
            logger.warning(f"Removed {removed_count} erroneous records from JSON data")
            save_data(cleaned_data)
        logger.info(f"Loaded and cleaned {len(cleaned_data)} records from {JSON_FILE_PATH}")
        return cleaned_data
    except FileNotFoundError:
        logger.warning(f"JSON file {JSON_FILE_PATH} not found. Starting with empty data.")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {JSON_FILE_PATH}. Check if the file is valid JSON.")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading data: {e}")
        return {}

def save_individual_record(username: str, data: Dict[str, Any]) -> None:
    try:
        with open(JSON_FILE_PATH, 'r+') as f:
            existing_data = json.load(f)
            existing_data[username.lower()] = {
                "data": data,
                "last_updated": datetime.now().isoformat()
            }
            f.seek(0)
            json.dump(existing_data, f, indent=2)
            f.truncate()
        logger.info(f"Saved record for {username} to {JSON_FILE_PATH}")
    except Exception as e:
        logger.error(f"Error saving record for {username} to {JSON_FILE_PATH}: {e}")

def save_data(data: Dict[str, Any]) -> None:
    try:
        with open(JSON_FILE_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(data)} records to {JSON_FILE_PATH}")
    except Exception as e:
        logger.error(f"Error saving data to {JSON_FILE_PATH}: {e}")

class UpdateRecordDict(TypedDict):
    id: str
    fields: Dict[str, Any]

def prepare_update_record(record_id: str, username: str, data: Dict[str, Any]) -> Optional[UpdateRecordDict]:
    try:
        twitter_data = data['data']
        fields = {
            'Account ID': twitter_data.get('id'),
            'Full Name': twitter_data.get('name'),
            'Description': twitter_data.get('description'),
            'Created At': twitter_data.get('created_at')
        }
        
        if 'public_metrics' in twitter_data:
            metrics = twitter_data['public_metrics']
            fields.update({
                'Listed Count': int(metrics.get('listed_count', 0)),
                'Followers Count': int(metrics.get('followers_count', 0)),
                'Following Count': int(metrics.get('following_count', 0))
            })
        
        fields = {k: v for k, v in fields.items() if v is not None}
        
        return {'id': record_id, 'fields': fields} if fields else None
    except Exception as e:
        logger.error(f"Unexpected error preparing record for {username}: {e}")
        return None

def update_airtable(records_to_update: List[Tuple[str, str, Dict[str, Any]]]) -> None:
    batches = [records_to_update[i:i + AIRTABLE_BATCH_SIZE] for i in range(0, len(records_to_update), AIRTABLE_BATCH_SIZE)]
    total_updated = 0

    for i, batch in enumerate(batches, 1):
        prepared_batch = [record for record in map(lambda x: prepare_update_record(*x), batch) if record]
        
        if prepared_batch:
            try:
                headers = {
                    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
                    "Content-Type": "application/json"
                }
                response = requests.patch(AIRTABLE_API_ENDPOINT, headers=headers, json={"records": prepared_batch})
                response.raise_for_status()
                batch_size = len(prepared_batch)
                total_updated += batch_size
                logger.info(f"Batch {i}: Updated {batch_size} records in Airtable")
                logger.info(f"Updated accounts: {', '.join(username for _, username, _ in batch)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error updating batch {i} in Airtable: {e}")
        else:
            logger.warning(f"Batch {i} was empty after preparation, skipping update")

    logger.info(f"Total records updated in Airtable: {total_updated}")

def main() -> None:
    driver = None
    try:
        unenriched_accounts = get_unenriched_accounts()
        existing_data = load_and_clean_data()
        
        driver = init_driver()
        load_cookies(driver, 'twitter_cookies.pkl')
        
        existing_data, updated_count = update_twitter_data(driver, existing_data, unenriched_accounts, TWITTER_BEARER_TOKEN, save_individual_record)
        logger.info(f"Updated {updated_count} profiles from Twitter")
        records_to_update = [
            (record_id, username, existing_data[username.lower()])
            for record_id, username in unenriched_accounts
            if username.lower() in existing_data
        ]
        
        logger.info(f"Preparing to update {len(records_to_update)} records in Airtable")

        if records_to_update:
            update_airtable(records_to_update)
        else:
            logger.info("No records to update in Airtable")

        logger.info(f"Script completed. Attempted to enrich {len(records_to_update)} records in total.")

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()