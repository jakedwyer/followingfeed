import logging
import time
import sys
from datetime import datetime, timedelta
from twitter_update import fetch_records_with_empty_account_id, update_airtable_records, get_user_details
from utils.config import load_env_variables

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DAILY_RATE_LIMIT = 500

def main():
    # Load environment variables
    env_vars = load_env_variables()
    
    # Set up headers
    airtable_headers = {"Authorization": f"Bearer {env_vars['airtable_token']}"}
    twitter_headers = {"Authorization": f"Bearer {env_vars['bearer_token']}"}
    
    # Fetch records with empty Account ID
    table_id = 'tblJCXhcrCxDUJR3F'  # Replace with your actual table ID
    records = fetch_records_with_empty_account_id(table_id, airtable_headers)
    logging.info(f"Fetched {len(records)} records with empty Account ID")
    
    # Initialize rate limit tracking
    api_calls = 0
    rate_limit_reset = datetime.now() + timedelta(days=1)
    
    # Update records with user details from Twitter
    updated_records = []
    for i, record in enumerate(records):
        username = record['fields'].get('Username')
        if username:
            # Check if we've hit the daily rate limit
            if api_calls >= DAILY_RATE_LIMIT:
                wait_time = (rate_limit_reset - datetime.now()).total_seconds()
                if wait_time > 0:
                    logging.info(f"Daily rate limit reached. Waiting {wait_time:.2f} seconds until reset.")
                    time.sleep(wait_time)
                api_calls = 0
                rate_limit_reset = datetime.now() + timedelta(days=1)
            
            try:
                user_details = get_user_details(username, twitter_headers)
                api_calls += 1
                if user_details and 'data' in user_details:
                    record['fields']['Account ID'] = user_details['data']['id']
                    updated_records.append(record)
                    logging.info(f"Updated record {i+1}/{len(records)}: {username} (API calls: {api_calls})")
                else:
                    logging.warning(f"No data found for user: {username}")
            except Exception as e:
                if "Rate limit exceeded" in str(e):
                    logging.error(f"Rate limit exceeded. Stopping the script.")
                    # Update Airtable with any remaining records before exiting
                    if updated_records:
                        update_airtable_records(updated_records, table_id, airtable_headers)
                        logging.info(f"Updated final {len(updated_records)} records in Airtable before exiting")
                    sys.exit(1)  # Exit the script with an error code
                else:
                    logging.error(f"Error processing user {username}: {str(e)}")
        
        # Update Airtable every 100 records or at the end
        if len(updated_records) >= 100 or i == len(records) - 1:
            if updated_records:
                update_airtable_records(updated_records, table_id, airtable_headers)
                logging.info(f"Updated {len(updated_records)} records in Airtable")
                updated_records = []  # Reset the list after updating
    
    logging.info("Script completed successfully")

if __name__ == "__main__":
    main()