import logging
import os
import requests
from utils.config import load_env_variables
from utils.logging_setup import setup_logging
from twitter.twitter import fetch_list_members
from scraping.scraping import init_driver, load_cookies, get_following
from twitter_update import (
    airtable_api_request, fetch_records_with_empty_account_id, 
    update_airtable_records, delete_airtable_record, get_user_details
)

setup_logging()  # Set up logging to app.log

def activate_virtualenv():
    """Activate the virtual environment if not already activated."""
    venv_path = '/root/followfeed/xfeed/bin/activate_this.py'
    if not os.getenv('VIRTUAL_ENV') and os.path.exists(venv_path):
        with open(venv_path) as f:
            exec(f.read(), {'__file__': venv_path})

# Fetch records from Airtable
def fetch_records(table_id, headers):
    base_id = 'appYCZWcmNBXB2uUS'
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    records, offset = [], None
    while True:
        params = {'offset': offset} if offset else {}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            records.extend(data.get('records', []))
            offset = data.get('offset')
            if not offset:
                break
        else:
            logging.error(f"Failed to fetch records from {table_id}. Status code: {response.status_code}")
            logging.error(f"Response content: {response.content}")
            return []
    return records

# Batch request for creating or updating records
def batch_request(url, headers, records, method):
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        response = method(url, headers=headers, json={"records": batch})
        if response.status_code in [200, 201]:
            logging.info(f"{method.__name__.capitalize()}d {len(batch)} entries in the {url.split('/')[-1]} table.")
        else:
            logging.error(f"Failed to {method.__name__} entries in {url.split('/')[-1]} table. Status code: {response.status_code}")
            logging.error(f"Response content: {response.content}")

# Update records in Airtable
def update_records(records, table_id, headers):
    base_id = 'appYCZWcmNBXB2uUS'
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    batch_request(url, headers, records, requests.patch)

# Create records in Airtable
def create_records(records, table_id, headers):
    base_id = 'appYCZWcmNBXB2uUS'
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    batch_request(url, headers, records, requests.post)

# Fetch and update accounts in Airtable
def fetch_and_update_accounts(usernames, headers, accounts):
    new_entries = [{"fields": {"Username": username}} for username in usernames if username not in accounts]
    if new_entries:
        create_records(new_entries, 'tblJCXhcrCxDUJR3F', headers)
        updated_records = fetch_records('tblJCXhcrCxDUJR3F', headers)
        accounts.update({record['fields']['Username'].lower(): record['id'] for record in updated_records if 'Username' in record['fields']})
    return accounts

# Fetch existing followed accounts for a follower
def fetch_existing_follows(record_id, headers):
    base_id = 'appYCZWcmNBXB2uUS'
    url = f"https://api.airtable.com/v0/{base_id}/tbl7bEfNVnCEQvUkT/{record_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return set(response.json().get('fields', {}).get('Followed Accounts', []))
    else:
        logging.error(f"Failed to fetch existing follows for record ID {record_id}. Status code: {response.status_code}")
        logging.error(f"Response content: {response.content}")
        return set()

# Process a single user
def process_user(username, follower_record_id, driver, headers, accounts):
    existing_follows = fetch_existing_follows(follower_record_id, headers)
    new_follows = get_following(driver, username, existing_follows)
    all_follows = {uname.lower() for uname in existing_follows.union(new_follows)}
    accounts = fetch_and_update_accounts(all_follows, headers, accounts)
    followed_account_ids = [accounts[uname] for uname in all_follows if uname in accounts]

    follower_update = {
        'id': follower_record_id,
        'fields': {'Account': followed_account_ids}
    }
    update_records([follower_update], 'tbl7bEfNVnCEQvUkT', headers)

    return accounts, len(new_follows)

# Main function
def main():
    activate_virtualenv()
    env_vars = load_env_variables()
    logging.info("Main function started")
    headers = {"Authorization": f"Bearer {env_vars['airtable_token']}"}
    twitter_headers = {"Authorization": f"Bearer {env_vars['bearer_token']}"}

    list_members = fetch_list_members(env_vars['list_id'], twitter_headers)
    if not list_members:
        logging.error("Failed to fetch list members.")
        return

    existing_followers = fetch_records('tbl7bEfNVnCEQvUkT', headers)
    followers = {record['fields']['Username'].lower(): record['id'] for record in existing_followers if 'Username' in record['fields']}

    new_followers = [{"fields": {"Account ID": member['id'], "Username": member['username']}} for member in list_members if member['username'].lower() not in followers]
    create_records(new_followers, 'tbl7bEfNVnCEQvUkT', headers)

    updated_followers = fetch_records('tbl7bEfNVnCEQvUkT', headers)
    followers.update({record['fields']['Username'].lower(): record['id'] for record in updated_followers if 'Username' in record['fields']})

    existing_accounts = fetch_records('tblJCXhcrCxDUJR3F', headers)
    accounts = {record['fields']['Username'].lower(): record['id'] for record in existing_accounts if 'Username' in record['fields']}
    driver = init_driver()
    load_cookies(driver, env_vars['cookie_path'])

    total_new_handles = 0
    for member in list_members:
        username = member['username'].lower()
        record_id = followers.get(username)
        if record_id:
            try:
                accounts, new_handles = process_user(username, record_id, driver, headers, accounts)
                total_new_handles += new_handles
            except Exception as e:
                logging.error(f"Error processing {username}: {e}")

    driver.quit()
    logging.info(f"Total new handles found: {total_new_handles}")

    max_requests = 500
    request_count = 0

    # Fetch records from Airtable with empty Account ID
    records = fetch_records_with_empty_account_id('tblJCXhcrCxDUJR3F', headers)
    logging.info(f"Fetched {len(records)} records with empty Account ID from Airtable.")

    # Fetch user details from Twitter and update records
    for record in records:
        if request_count >= max_requests:
            logging.info("Reached the maximum number of requests to Twitter API. Stopping the script.")
            break

        username = record['fields'].get('Username')
        if username:
            try:
                user_details = get_user_details(username, twitter_headers)
                request_count += 1

                if user_details and 'data' in user_details:
                    record['fields']['Account ID'] = user_details['data']['id']
                    update_airtable_records([record], 'tblJCXhcrCxDUJR3F', headers)
                    logging.info(f"Updated record for {username} in Airtable.")
                else:
                    logging.error(f"Failed to fetch user details or missing 'data' key for {username}")
                    logging.error(f"User details response: {user_details}")
                    delete_airtable_record(record['id'], 'tblJCXhcrCxDUJR3F', headers)
                    logging.info(f"Deleted record for {username} from Airtable.")
            except Exception as e:
                logging.error(f"Stopping script due to error: {e}")
                break
        else:
            logging.error(f"Username not found in record: {record}")

if __name__ == "__main__":
    main()