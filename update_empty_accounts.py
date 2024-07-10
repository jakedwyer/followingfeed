import os
import json
import time
from datetime import datetime
import logging
import requests
from pyairtable import Api
from typing import List, Dict, Any, TypedDict, Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
AIRTABLE_TOKEN = os.environ.get('AIRTABLE_TOKEN')
BEARER_TOKEN = os.environ.get('BEARER_TOKEN')
BASE_ID = 'appYCZWcmNBXB2uUS'
TABLE_ID = 'tblJCXhcrCxDUJR3F'
JSON_FILE_PATH = 'user_details.json'
TWITTER_API_ENDPOINT = 'https://api.twitter.com/2/users/by/username'
TWITTER_API_FIELDS = 'id,name,username,created_at,description,public_metrics'
AIRTABLE_BATCH_SIZE = 10

class UpdateRecordDict(TypedDict):
    id: str
    fields: Dict[str, Any]

# Check for required environment variables
if not AIRTABLE_TOKEN:
    raise ValueError("AIRTABLE_TOKEN environment variable is not set")
if not BEARER_TOKEN:
    raise ValueError("BEARER_TOKEN environment variable is not set")

# Initialize Airtable API
api = Api(AIRTABLE_TOKEN)
table = api.table(BASE_ID, TABLE_ID)

def get_unenriched_accounts() -> List[Tuple[str, str]]:
    try:
        records = table.all(formula="NOT({Account ID})")
        logging.info(f"Pulled {len(records)} unenriched records from Airtable")
        return [(record['id'], record['fields']['Username'].lower()) for record in records if 'Username' in record['fields']]
    except Exception as e:
        logging.error(f"Error fetching records from Airtable: {str(e)}")
        return []

def load_and_clean_data() -> Dict[str, Any]:
    try:
        with open(JSON_FILE_PATH, 'r') as f:
            data = json.load(f)
        cleaned_data = {k.lower(): v for k, v in data.items() if 'data' in v and isinstance(v['data'], dict)}
        removed_count = len(data) - len(cleaned_data)
        if removed_count > 0:
            logging.warning(f"Removed {removed_count} erroneous records from JSON data")
            save_data(cleaned_data)
        logging.info(f"Loaded and cleaned {len(cleaned_data)} records from {JSON_FILE_PATH}")
        return cleaned_data
    except FileNotFoundError:
        logging.warning(f"JSON file {JSON_FILE_PATH} not found. Starting with empty data.")
        return {}
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from {JSON_FILE_PATH}. Check if the file is valid JSON.")
        return {}
    except Exception as e:
        logging.error(f"Unexpected error loading data: {str(e)}")
        return {}

def save_data(data: Dict[str, Any]) -> None:
    try:
        with open(JSON_FILE_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        logging.info(f"Saved {len(data)} records to {JSON_FILE_PATH}")
    except Exception as e:
        logging.error(f"Error saving data to {JSON_FILE_PATH}: {str(e)}")

def fetch_twitter_data(username: str) -> Optional[Dict[str, Any]]:
    url = f"{TWITTER_API_ENDPOINT}/{username}"
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}", "User-Agent": "TwitterDevSampleCode"}
    params = {"user.fields": TWITTER_API_FIELDS}
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('data')
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response and e.response.status_code == 429:
            logging.warning("Rate limit reached")
        else:
            logging.error(f"Error fetching data for {username}: {str(e)}")
        return None

def update_twitter_data(existing_data: Dict[str, Any], unenriched_accounts: List[Tuple[str, str]]) -> Tuple[Dict[str, Any], int]:
    requests_made = 0
    for _, username in unenriched_accounts:
        username_lower = username.lower()
        if username_lower not in existing_data:
            twitter_data = fetch_twitter_data(username)
            if twitter_data is None:
                logging.warning(f"Stopping Twitter API calls after processing {requests_made} accounts")
                break
            existing_data[username_lower] = {"data": twitter_data}
            requests_made += 1
            logging.info(f"Fetched data for {username}")
            time.sleep(1)  # Rate limiting
    return existing_data, requests_made

def prepare_update_record(record_id: str, username: str, data: Dict[str, Any]) -> Optional[UpdateRecordDict]:
    try:
        twitter_data = data['data']
        return {
            'id': record_id,
            'fields': {
                'Account ID': twitter_data['id'],
                'Full Name': twitter_data['name'],
                'Description': twitter_data.get('description', ''),
                'Listed Count': twitter_data['public_metrics']['listed_count'],
                'Followers Count': twitter_data['public_metrics']['followers_count'],
                'Created At': twitter_data['created_at']
            }
        }
    except KeyError as e:
        logging.error(f"Missing key in data for {username}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error preparing record for {username}: {str(e)}")
    return None

def update_airtable(records_to_update: List[Tuple[str, str, Dict[str, Any]]]) -> None:
    batches = [records_to_update[i:i + AIRTABLE_BATCH_SIZE] for i in range(0, len(records_to_update), AIRTABLE_BATCH_SIZE)]
    total_updated = 0

    for i, batch in enumerate(batches, 1):
        prepared_batch = [record for record in map(lambda x: prepare_update_record(*x), batch) if record]
        
        if prepared_batch:
            try:
                table.batch_update(prepared_batch)
                batch_size = len(prepared_batch)
                total_updated += batch_size
                logging.info(f"Batch {i}: Updated {batch_size} records in Airtable")
                logging.info(f"Updated accounts: {', '.join(username for _, username, _ in batch)}")
            except Exception as e:
                logging.error(f"Error updating batch {i} in Airtable: {str(e)}")
        else:
            logging.warning(f"Batch {i} was empty after preparation, skipping update")

    logging.info(f"Total records updated in Airtable: {total_updated}")

def main() -> None:
    try:
        unenriched_accounts = get_unenriched_accounts()
        existing_data = load_and_clean_data()

        
        matched_from_json = [(id, username, existing_data[username.lower()]) 
                             for id, username in unenriched_accounts 
                             if username.lower() in existing_data]
        
        logging.info(f"Found {len(matched_from_json)} accounts in JSON file that match unenriched Airtable records")
        
        remaining_unenriched = [account for account in unenriched_accounts 
                                if account[1].lower() not in existing_data]
        
        existing_data, requests_made = update_twitter_data(existing_data, remaining_unenriched)
        save_data(existing_data)
        logging.info(f"Made {requests_made} requests to Twitter API")
        
        records_to_update = matched_from_json + [
            (id, username, existing_data[username.lower()]) 
            for id, username in remaining_unenriched 
            if username.lower() in existing_data
        ]
        
        logging.info(f"Preparing to update {len(records_to_update)} records in Airtable")

        if records_to_update:
            update_airtable(records_to_update)
        else:
            logging.info("No records to update in Airtable")

        logging.info(f"Script completed. Attempted to enrich {len(records_to_update)} records in total.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main()
