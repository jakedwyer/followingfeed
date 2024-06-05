from json import load
import logging
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

#load airtable api token
airtable_token = os.getenv('airtable_token')
bearer_token = os.getenv('airtable_token_secret')

# Setup basic logging
logging.basicConfig(level=logging.INFO)

# Mock data for headers (replace with actual token if needed)
headers = {
    "Authorization": "Bearer {airtable_token}"
}

# Mock data for env_vars (replace with actual values if needed)

# Mock data for existing accounts (from airtable_ids.json)
existing_usernames = airtable_ids

# Mock function to simulate fetching records from Airtable
def fetch_records_from_airtable_mock(table_id, headers):
    if table_id == 'tbl7bEfNVnCEQvUkT':
        return [{'fields': {'Username': 'test_user', 'Followed Accounts': ['existing_account1', 'existing_account2']}}]
    return []

# Mock function to simulate updating records in Airtable
def update_airtable_records_mock(records, table_id, headers):
    logging.info(f"Mock update: {len(records)} records to {table_id}")

# Mock function to simulate fetching and updating accounts
def fetch_and_update_accounts_mock(usernames, headers, existing_usernames):
    new_entries = [username for username in usernames if username not in existing_usernames]
    update_airtable_records_mock(new_entries, 'tblJCXhcrCxDUJR3F', headers)
    return {**existing_usernames, **{username: f'recMockId{username}' for username in new_entries}}

# Mock function to simulate fetching existing follows
def fetch_existing_follows_mock(record_id, headers):
    return {'existing_account1', 'existing_account2'}

# Mock function to simulate getting following accounts
def get_following_mock(driver, username, existing_follows, max_accounts=None):
    return {'new_account1', 'new_account2', 'existing_account1'}

# Mock data for driver (simulated)
driver = None

# Simulate processing a user
def process_user_mock(username, follower_record_id, driver, headers, all_updates, existing_usernames, accounts_table):
    logging.info(f"Processing user: {username}")
    existing_follows = fetch_existing_follows_mock(follower_record_id, headers)
    logging.info(f"Existing follows for {username}: {existing_follows}")
    new_follows = get_following_mock(driver, username, existing_follows, max_accounts=None)
    logging.info(f"New follows for {username}: {new_follows}")

    # Ensure all followed accounts are added to the Accounts table
    existing_usernames = fetch_and_update_accounts_mock(new_follows, headers, existing_usernames)
    logging.info(f"Updated existing usernames: {existing_usernames}")

    for follow_username in new_follows:
        follow_record_id = existing_usernames.get(follow_username)
        if not follow_record_id:
            logging.error(f"Record ID for followed account {follow_username} not found.")
            continue
        
        update = {
            'Account': [follow_record_id],
            'Followed By': [follower_record_id],
        }
        
        # Simulate saving the update to Airtable
        update_airtable_records_mock([update], 'tbldJzvV7qiqk9L5J', headers)
        logging.info(f"Saved update for {username} following {follow_username}")
        all_updates.append(update)

        # Simulate updating the Followers field in the Accounts table
        account_record = accounts_table.get(follow_record_id)
        existing_followers = account_record['fields'].get('Followers', [])
        if follower_record_id not in existing_followers:
            existing_followers.append(follower_record_id)
            account_record['fields']['Followers'] = existing_followers
            logging.info(f"Added follower {follower_record_id} to account {follow_record_id}.")

# Run the test
all_updates = []
accounts_table = {f'recMockId{username}': {'fields': {'Followers': []}} for username in existing_usernames}
process_user_mock('test_user', 'recTestUser', driver, headers, all_updates, existing_usernames, accounts_table)
