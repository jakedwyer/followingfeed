import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from utils.airtable import update_airtable_records, fetch_records_from_airtable
from twitter.twitter import fetch_twitter_data_api
import requests

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BEARER_TOKEN = os.getenv('BEARER_TOKEN')
AIRTABLE_TOKEN = os.getenv('AIRTABLE_TOKEN')
TABLE_ID = os.getenv('AIRTABLE_ACCOUNTS_TABLE')
MAX_API_CALLS = 500

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
            logger.error(f"Twitter API rate limit reached for {username}. Stopping the script.")
            return "RATE_LIMIT_REACHED"
        logger.error(f"Error fetching profile for {username}: {e}")
    except Exception as e:
        logger.error(f"Error fetching profile for {username}: {e}")
    return None

def update_user_details(username, profile):
    try:
        with open('user_details.json', 'r') as f:
            user_details = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        user_details = {}
    
    user_details[username] = profile
    
    with open('user_details.json', 'w') as f:
        json.dump(user_details, f, indent=2, default=str)

def create_updated_record(record, profile):
    updated_record = {
        "id": record["id"],
        "fields": {
            "Account ID": str(profile.get('id', '')),
            "Full Name": str(profile.get('name', '')),
            "Description": str(profile.get('description', '')),
            "Listed Count": int(profile.get('public_metrics', {}).get('listed_count', 0)),
            "Followers Count": int(profile.get('public_metrics', {}).get('followers_count', 0)),
            "Following Count": int(profile.get('public_metrics', {}).get('following_count', 0)),
            "Location": str(profile.get('location', '')),
            "Website": str(profile.get('url', '')),
        }
    }
    
    if 'created_at' in profile:
        created_at = datetime.strptime(profile['created_at'], "%Y-%m-%dT%H:%M:%S.%fZ")
        updated_record['fields']["Created At"] = created_at.strftime("%Y-%m-%d")
    
    return updated_record

def main():
    accounts_to_update = [
        record for record in fetch_records_from_airtable(TABLE_ID, {"Authorization": f"Bearer {AIRTABLE_TOKEN}"})
        if not record['fields'].get('Account ID')
    ]
    
    api_calls = 0
    updated_records = []
    
    for record in accounts_to_update:
        if api_calls >= MAX_API_CALLS:
            logger.info(f"Reached maximum of {MAX_API_CALLS} Twitter API calls. Stopping further profile fetches.")
            break
        
        username = record['fields'].get('Username')
        if not username:
            continue
        
        profile = fetch_profile(username)
        api_calls += 1
        
        if profile == "RATE_LIMIT_REACHED":
            logger.info("Twitter API rate limit reached. Stopping further profile fetches.")
            break
        elif profile:
            update_user_details(username, profile)
            updated_records.append(create_updated_record(record, profile))
    
    if updated_records:
        update_airtable_records(updated_records, TABLE_ID, {"Authorization": f"Bearer {AIRTABLE_TOKEN}"})
        logger.info(f"Updated {len(updated_records)} records in Airtable")
    else:
        logger.info("No records to update in Airtable")

    logger.info(f"Total API calls made: {api_calls}")

if __name__ == "__main__":
    main()