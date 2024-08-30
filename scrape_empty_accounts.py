import sys
import os
import json
import requests
import logging
from typing import Dict, List, Tuple, Optional, Any, TypedDict
from datetime import datetime
from pyairtable import Api
from scraping.scraping import init_driver, load_cookies, scrape_twitter_profile
import unicodedata
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add a file handler
file_handler = logging.FileHandler('scrape_empty_accounts.log')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Constants
BASE_ID = 'appYCZWcmNBXB2uUS'
TABLE_ID = 'tblJCXhcrCxDUJR3F'
JSON_FILE_PATH = 'user_details.json'
AIRTABLE_BATCH_SIZE = 10
TWITTER_API_ENDPOINT = 'https://api.twitter.com/2/users/by/username'
TWITTER_API_FIELDS = 'id,name,username,created_at,description,public_metrics'
AIRTABLE_API_ENDPOINT = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"

# Environment variables
AIRTABLE_TOKEN = os.environ.get('AIRTABLE_TOKEN')
TWITTER_BEARER_TOKEN = os.environ.get('BEARER_TOKEN')

if not AIRTABLE_TOKEN or not TWITTER_BEARER_TOKEN:
    logger.error("AIRTABLE_TOKEN or BEARER_TOKEN environment variable is not set")
    raise ValueError("AIRTABLE_TOKEN or BEARER_TOKEN environment variable is not set")

# Initialize Airtable API
api = Api(AIRTABLE_TOKEN)
table = api.table(BASE_ID, TABLE_ID)

def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ''
    
    # Normalize Unicode characters
    text = unicodedata.normalize('NFKD', text)
    
    # Remove non-ASCII characters
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    
    # Remove any remaining non-printable characters and trim whitespace
    text = re.sub(r'[^\x20-\x7E]+', '', text).strip()
    
    return text

def parse_number(value: Any) -> int:
    if not value:
        return 0
    
    value = str(value).strip().lower()
    
    # Remove commas
    value = value.replace(',', '')
    
    # Handle abbreviations
    if value.endswith('k'):
        return int(float(value[:-1]) * 1000)
    elif value.endswith('m'):
        return int(float(value[:-1]) * 1000000)
    elif value.endswith('b'):
        return int(float(value[:-1]) * 1000000000)
    
    # If it's just a number (possibly with decimal places)
    try:
        return int(float(value))
    except ValueError:
        logger.warning(f"Could not parse number: {value}. Setting to 0.")
        return 0

def format_data_for_airtable(data: Dict[str, Any]) -> Dict[str, Any]:
    formatted_data = {}
    
    for key, value in data.items():
        if key in ["Followers Count", "Listed Count"]:
            formatted_data[key] = parse_number(value)
        elif key == "Join Date":
            if value:
                try:
                    # Remove "Joined " prefix if present
                    date_str = clean_text(value.replace("Joined ", ""))
                    # Parse the date string (assuming format like "September 2018")
                    parsed_date = datetime.strptime(date_str, "%B %Y")
                    # Format it as YYYY-MM-DD for Airtable
                    formatted_data[key] = parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    logger.warning(f"Could not parse Join Date '{value}'. Saving as is.")
                    formatted_data[key] = clean_text(value)
            else:
                formatted_data[key] = None
        else:
            # For text fields, ensure they're strings and clean them
            formatted_data[key] = clean_text(str(value)) if value is not None else None
    
    return formatted_data

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
        logger.error(f"Error fetching data from Twitter API: {e}", exc_info=True)
        return None

def get_unenriched_accounts() -> List[Tuple[str, str]]:
    try:
        records = table.all(formula="NOT({Description})")
        logger.info(f"Pulled {len(records)} unenriched records from Airtable")
        return [(record['id'], record['fields']['Username'].lower()) for record in records if 'Username' in record['fields']]
    except Exception as e:
        logger.error(f"Error fetching records from Airtable: {e}", exc_info=True)
        return []

def load_and_clean_data() -> Dict[str, Any]:
    try:
        with open(JSON_FILE_PATH, 'r') as f:
            data = json.load(f)
        cleaned_data = {k.lower(): v for k, v in data.items() if 'data' in v and isinstance(v['data'], dict)}
        for username, user_data in cleaned_data.items():
            user_data['data'] = format_data_for_airtable(user_data['data'])
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
        logger.error(f"Error decoding JSON from {JSON_FILE_PATH}. Check if the file is valid JSON.", exc_info=True)
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading data: {e}", exc_info=True)
        return {}

def save_individual_record(username: str, data: Dict[str, Any]) -> None:
    try:
        formatted_data = format_data_for_airtable(data)
        
        with open(JSON_FILE_PATH, 'r+') as f:
            existing_data = json.load(f)
            existing_data[username.lower()] = {
                "data": formatted_data,
                "last_updated": datetime.now().isoformat()
            }
            f.seek(0)
            json.dump(existing_data, f, indent=2)
            f.truncate()
        logger.info(f"Saved formatted record for {username} to {JSON_FILE_PATH}")
    except Exception as e:
        logger.error(f"Error saving record for {username} to {JSON_FILE_PATH}: {e}", exc_info=True)

def save_data(data: Dict[str, Any]) -> None:
    try:
        with open(JSON_FILE_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(data)} records to {JSON_FILE_PATH}")
    except Exception as e:
        logger.error(f"Error saving data to {JSON_FILE_PATH}: {e}", exc_info=True)

class UpdateRecordDict(TypedDict):
    id: str
    fields: Dict[str, Any]

def prepare_update_record(record_id: str, username: str, data: Dict[str, Any]) -> Optional[UpdateRecordDict]:
    try:
        logger.debug(f"Preparing update for {username}. Data received: {json.dumps(data, indent=2)}")
        
        twitter_data = data.get('data', {})
        
        fields = {
            'fldQTZqbhLnvX4J4N': twitter_data.get('Username', ''),  # Username
            'fldymcou2AR8Ybgcl': twitter_data.get('Full Name', ''),  # Full Name
            'fldzG3qnqMraQOE3f': twitter_data.get('Description', ''),  # Description
            'fldYuSUsg1sB5qhHE': twitter_data.get('Location', ''),  # Location
            'fldyrFKXNAtJVE3rv': twitter_data.get('Website', ''),  # Website
            'fldpE5wkrktOYUPkJ': twitter_data.get('Join Date'),  # Created At
            'fldKPxZQbZgyRCw2x': twitter_data.get('Followers Count', 0),  # Followers Count
            'fldMBcHWW8ku5W5NS': twitter_data.get('Listed Count', 0),  # Listed Count
            'fld6us1NRxWC3pxPl': twitter_data.get('Account ID', ''),  # Account ID
        }
        
        fields = {k: v for k, v in fields.items() if v is not None and v != ''}
        
        return {'id': record_id, 'fields': fields} if fields else None
    except Exception as e:
        logger.error(f"Unexpected error preparing record for {username}: {e}", exc_info=True)
        return None

def update_airtable(records_to_update: List[Tuple[str, str, Dict[str, Any]]]) -> None:
    batches = [records_to_update[i:i + AIRTABLE_BATCH_SIZE] for i in range(0, len(records_to_update), AIRTABLE_BATCH_SIZE)]
    total_updated = 0
    for i, batch in enumerate(batches, 1):
        prepared_batch = [prepare_update_record(record_id, username, data) for record_id, username, data in batch if data]
        prepared_batch = [record for record in prepared_batch if record]
        
        if prepared_batch:
            try:
                headers = {
                    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
                    "Content-Type": "application/json"
                }
                logger.debug(f"Sending batch {i} to Airtable: {json.dumps(prepared_batch, indent=2)}")
                response = requests.patch(AIRTABLE_API_ENDPOINT, headers=headers, json={"records": prepared_batch})
                response.raise_for_status()
                batch_size = len(prepared_batch)
                total_updated += batch_size
                logger.info(f"Batch {i}: Updated {batch_size} records in Airtable")
                logger.info(f"Updated accounts: {', '.join(username for _, username, _ in batch)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error updating batch {i} in Airtable: {str(e)}", exc_info=True)
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response content: {e.response.content}")
                    logger.error(f"Request payload: {json.dumps(prepared_batch, indent=2)}")
        else:
            logger.warning(f"Batch {i} was empty after preparation, skipping update")

    logger.info(f"Total records updated in Airtable: {total_updated}")

def main() -> None:
    try:
        # Load existing data from JSON file
        existing_data = load_and_clean_data()
        
        # Get unenriched accounts from Airtable
        unenriched_accounts = get_unenriched_accounts()
        
        logger.info(f"Total accounts in user_details.json: {len(existing_data)}")
        logger.info(f"Total unenriched accounts from Airtable: {len(unenriched_accounts)}")
        
        records_to_update = []
        for record_id, username in unenriched_accounts:
            if username.lower() in existing_data:
                twitter_data = existing_data[username.lower()]
                records_to_update.append((record_id, username, twitter_data))
            else:
                logger.warning(f"No match found for username: {username}")
        
        logger.info(f"Total records matched and ready to update: {len(records_to_update)}")

        if records_to_update:
            update_airtable(records_to_update)
        else:
            logger.info("No records to update in Airtable from existing data")

        # If there are still unenriched accounts, proceed with scraping
        remaining_accounts = [(record_id, username) for record_id, username in unenriched_accounts if username.lower() not in existing_data]
        
        if remaining_accounts:
            logger.info(f"Proceeding to scrape data for {len(remaining_accounts)} remaining accounts")
            driver = init_driver()
            load_cookies(driver, 'twitter_cookies.pkl')
            
            for record_id, username in remaining_accounts:
                twitter_data = scrape_twitter_profile(driver, username)
                if twitter_data:
                    save_individual_record(username, twitter_data)
                    records_to_update.append((record_id, username, {'data': twitter_data}))
            
            if records_to_update:
                update_airtable(records_to_update)
            
            driver.quit()
        
        logger.info(f"Script completed. Attempted to enrich {len(records_to_update)} records in total.")

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()