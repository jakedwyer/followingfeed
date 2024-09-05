import sys
import os
import json
import requests
import logging
from typing import Dict, List, Tuple, Optional, Any, TypedDict, Set, Union
from datetime import datetime
from pyairtable import Api
from scraping.scraping import init_driver, load_cookies, scrape_twitter_profile, DELETE_RECORD_INDICATOR
import unicodedata
import re
import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.airtable import airtable_api_request, post_airtable_records, update_airtable_records

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

def parse_date(date_string: Union[str, None]) -> str:
    if not date_string:
        return ''
    
    date_string = date_string.strip()
    
    # Handle "Joined" format
    if date_string.startswith('Joined'):
        date_string = date_string.replace('Joined', '').strip()
    
    # Try parsing various date formats
    date_formats = [
        "%B %Y",  # e.g., "November 2017"
        "%Y-%m-%d",  # e.g., "2017-11-01"
        "%Y-%m-%d %H:%M:%S",  # e.g., "2017-11-01 12:00:00"
    ]
    
    for date_format in date_formats:
        try:
            date_obj = datetime.strptime(date_string, date_format)
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If all parsing attempts fail, return the original string
    logger.warning(f"Could not parse date '{date_string}'. Keeping original value.")
    return date_string

def format_data_for_airtable(data: Dict[str, Any]) -> Dict[str, Any]:
    formatted_data = {}
    
    for key, value in data.items():
        if key in ["Followers Count", "Listed Count"]:
            formatted_data[key] = parse_number(value)
        elif key == "Join Date" or key == "Created At":
            formatted_date = parse_date(value)
            formatted_data["Created At"] = formatted_date
        else:
            # For text fields, ensure they're strings and clean them
            formatted_data[key] = clean_text(str(value)) if value is not None else None
    
    # Remove empty fields
    formatted_data = {k: v for k, v in formatted_data.items() if v is not None and v != ''}
    
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
        records = table.all(formula="OR({Full Name} = BLANK(), {Description} = BLANK())")
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

def prepare_update_record(record_id: str, username: str, data: Dict[str, Any], existing_fields: Dict[str, Any]) -> Optional[UpdateRecordDict]:
    twitter_data = data.get('data', {})
    formatted_data = {}
    
    field_mapping = {
        "username": "Username",
        "name": "Full Name",
        "description": "Description",
        "location": "Location",
        "website": "Website",
        "created_at": "Created At",
        "followers_count": "Followers Count",
        "listed_count": "Listed Count",
        "account_id": "Account ID"
    }
    
    for twitter_field, airtable_field in field_mapping.items():
        new_value = twitter_data.get(twitter_field)
        if new_value and new_value != existing_fields.get(airtable_field):
            if airtable_field == "Created At":
                new_value = parse_date(new_value)
            formatted_data[airtable_field] = new_value
    
    if formatted_data:
        return {'id': record_id, 'fields': formatted_data}
    else:
        logger.warning(f"No updateable data for {username}")
        return None

def update_airtable(records_to_update: List[Tuple[str, str, Dict[str, Any], Dict[str, Any]]]) -> None:
    # Prepare all records first
    prepared_records = [
        prepare_update_record(record_id, username, data, existing_fields)
        for record_id, username, data, existing_fields in records_to_update
        if data
    ]
    
    # Filter out None values and records with empty fields
    valid_records = [record for record in prepared_records if record and record['fields']]
    
    logger.info(f"Total records to update: {len(records_to_update)}")
    logger.info(f"Records with valid data after preparation: {len(valid_records)}")
    logger.info(f"Skipped records: {len(records_to_update) - len(valid_records)}")

    # Create batches only from valid records
    batches = [valid_records[i:i + AIRTABLE_BATCH_SIZE] for i in range(0, len(valid_records), AIRTABLE_BATCH_SIZE)]
    
    total_updated = 0
    for i, batch in enumerate(batches, 1):
        try:
            headers = {
                "Authorization": f"Bearer {AIRTABLE_TOKEN}",
                "Content-Type": "application/json"
            }
            logger.debug(f"Sending batch {i} to Airtable: {json.dumps(batch, indent=2)}")
            response = requests.patch(AIRTABLE_API_ENDPOINT, headers=headers, json={"records": batch})
            response.raise_for_status()
            batch_size = len(batch)
            total_updated += batch_size
            logger.info(f"Batch {i}: Updated {batch_size} records in Airtable")
            logger.info(f"Updated accounts: {', '.join(record['fields'].get('Username', '') for record in batch)}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating batch {i} in Airtable: {str(e)}", exc_info=True)
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.content}")
                logger.error(f"Request payload: {json.dumps(batch, indent=2)}")

    logger.info(f"Total records updated in Airtable: {total_updated}")
    if len(records_to_update) > total_updated:
        logger.info(f"Skipped {len(records_to_update) - total_updated} records due to lack of updateable data")

def delete_airtable_record(record_id: str, headers: Dict[str, str]) -> None:
    response = airtable_api_request('DELETE', TABLE_ID, headers, record_id=record_id)
    if response is not None:
        logger.info(f"Successfully deleted record {record_id} from Airtable")
    else:
        logger.error(f"Failed to delete record {record_id} from Airtable")

def prepare_record_for_airtable(username: str, data: Dict[str, Any]) -> Dict[str, Any]:
    fields = {
        "Username": username,
        "Full Name": data.get("Full Name", ""),
        "Description": data.get("Description", ""),
        "Location": data.get("Location", ""),
        "Website": data.get("Website", ""),
        "Created At": parse_date(data.get("Join Date", "")),
        "Followers Count": data.get("Followers Count", 0),
        "Listed Count": data.get("Listed Count", 0),
        "Account ID": data.get("Account ID", "")
    }
    
    # Remove empty fields
    fields = {k: v for k, v in fields.items() if v != "" and v is not None}
    
    return {"fields": fields}

def get_all_usernames_from_airtable() -> Set[str]:
    try:
        all_records = table.all(fields=['Username'])
        return {record['fields'].get('Username', '').lower() for record in all_records if 'Username' in record['fields']}
    except Exception as e:
        logger.error(f"Error fetching usernames from Airtable: {e}", exc_info=True)
        return set()

def main() -> None:
    driver = None
    try:
        # Load existing data from JSON file
        existing_data = load_and_clean_data()
        
        # Get all records from Airtable
        all_airtable_records = table.all()
        
        logger.info(f"Total accounts in user_details.json: {len(existing_data)}")
        logger.info(f"Total accounts in Airtable: {len(all_airtable_records)}")
        
        records_to_update = []
        
        # First, update Airtable with existing JSON data
        for record in all_airtable_records:
            record_id = record['id']
            username = record['fields'].get('Username', '').lower()
            
            if not username:
                continue
            
            json_data = existing_data.get(username, {}).get('data', {})
            
            if json_data and 'Full Name' in json_data and 'Description' in json_data:
                update_data = {
                    'Full Name': json_data['Full Name'],
                    'Description': json_data['Description']
                }
                # Add other fields if they exist in JSON and are blank in Airtable
                for field in ['Location', 'Website', 'Created At', 'Followers Count', 'Listed Count', 'Account ID']:
                    if field in json_data and (field not in record['fields'] or not record['fields'][field]):
                        update_data[field] = json_data[field]
                
                records_to_update.append((record_id, username, {'data': update_data}))
                logger.info(f"Found supplementary data in JSON for {username}")
        
        # Update Airtable with existing JSON data
        if records_to_update:
            update_airtable(records_to_update)
            logger.info(f"Updated {len(records_to_update)} records with existing JSON data")
        
        # Reset records_to_update for the next phase
        records_to_update = []
        
        # Initialize WebDriver for scraping
        driver = init_driver()
        load_cookies(driver, 'twitter_cookies.pkl')
        
        headers = {
            "Authorization": f"Bearer {AIRTABLE_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Now, attempt to enrich remaining unenriched records
        for record in all_airtable_records:
            record_id = record['id']
            username = record['fields'].get('Username', '').lower()
            
            if not username:
                continue
            
            # Check if the record is still unenriched
            if not record['fields'].get('Full Name') or not record['fields'].get('Description'):
                # Attempt to scrape
                twitter_data = scrape_twitter_profile(driver, username)
                
                if twitter_data == DELETE_RECORD_INDICATOR:
                    delete_airtable_record(record_id, headers)
                    logger.warning(f"Deleted record for {username} due to persistent loading failure")
                elif twitter_data:
                    if isinstance(twitter_data, dict):
                        update_record = prepare_update_record(record_id, username, {'data': twitter_data}, record['fields'])
                        if update_record:
                            records_to_update.append((record_id, username, update_record['fields']))
                            logger.info(f"Successfully scraped and prepared update data for {username}")
                    else:
                        logger.warning(f"Unexpected data type for {username}. Skipping.")
                else:
                    logger.warning(f"No data scraped for {username}. Skipping.")
                
                # Add a delay between requests to avoid rate limiting
                time.sleep(random.uniform(5, 10))
        
        # Update Airtable with newly scraped data
        if records_to_update:
            update_airtable(records_to_update)
        
        logger.info(f"Script completed. Attempted to enrich {len(records_to_update)} records through scraping.")

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
    finally:
        if driver:
            logger.info("Closing WebDriver...")
            driver.quit()
            logger.info("WebDriver closed successfully.")

if __name__ == "__main__":
    main()