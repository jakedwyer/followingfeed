import logging
from utils.config import load_env_variables
from utils.logging_setup import setup_logging
from utils.airtable import save_data_to_airtable
from twitter.twitter import fetch_list_members
from scraping.scraping import init_driver, load_cookies, get_following
from twitter.twitter_account_details import fetch_and_save_accounts, get_user_details
from utils.cumulative_analysis import process_accounts
from datetime import datetime
import requests
import pandas as pd

def send_file_via_webhook(file_path, webhook_url):
    with open(file_path, 'rb') as f:
        response = requests.post(webhook_url, files={'file': f})
    return response

def fetch_records_from_airtable(table_id, headers):
    base_id = 'appYCZWcmNBXB2uUS'
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    records = []
    offset = None

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

def update_airtable_records(records, table_id, headers):
    base_id = 'appYCZWcmNBXB2uUS'
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        response = requests.post(url, headers=headers, json={"records": batch})
        if response.status_code == 200:
            logging.info(f"Added {len(batch)} new entries to the {table_id} table.")
        else:
            logging.error(f"Failed to add new entries to {table_id} table. Status code: {response.status_code}")
            logging.error(f"Response content: {response.content}")

def fetch_and_update_accounts(usernames, headers, existing_accounts):
    new_entries = []
    for username in usernames:
        if username not in existing_accounts:
            user_details = get_user_details(username, headers)
            if user_details:
                new_entry = {
                    "Username": user_details['data']['username'],
                    "Account ID": user_details['data']['id'],
                    "Full Name": user_details['data']['name'],
                    "Created At": user_details['data']['created_at'],
                    "Description": user_details['data']['description'],
                    "Followers Count": user_details['data']['public_metrics']['followers_count'],
                    "Listed Count": user_details['data']['public_metrics']['listed_count']
                }
                new_entries.append(new_entry)
    update_airtable_records(new_entries, 'tblJCXhcrCxDUJR3F', headers)
    
    # Fetch updated records to ensure all accounts are included
    updated_records = fetch_records_from_airtable('tblJCXhcrCxDUJR3F', headers)
    return {record['fields']['Username']: record['id'] for record in updated_records if 'Username' in record['fields']}

def fetch_existing_follows(record_id, headers):
    base_id = 'appYCZWcmNBXB2uUS'
    table_name = 'tbl7bEfNVnCEQvUkT'

    url = f"https://api.airtable.com/v0/{base_id}/{table_name}/{record_id}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        record = response.json()
        followed_accounts = record['fields'].get('Followed Accounts', [])
        return set(followed_accounts)
    else:
        logging.error(f"Failed to fetch existing follows for record ID {record_id}. Status code: {response.status_code}")
        logging.error(f"Response content: {response.content}")
        return set()

def process_user(username, follower_record_id, driver, headers, all_updates, existing_usernames):
    existing_follows = fetch_existing_follows(follower_record_id, headers)
    new_follows = get_following(driver, username, existing_follows, max_accounts=None)

    # Ensure all followed accounts are added to the Accounts table
    existing_usernames = fetch_and_update_accounts(new_follows, headers, existing_usernames)

    for follow_username in new_follows:
        follow_record_id = existing_usernames.get(follow_username)
        if not follow_record_id:
            logging.error(f"Record ID for followed account {follow_username} not found.")
            continue
        
        update = {
                'Account': [follow_record_id],
                'Followed By': [follower_record_id],
            }
        
        # Save the update to Airtable
        save_data_to_airtable('tbldJzvV7qiqk9L5J', pd.DataFrame([update]))
        logging.info(f"Saved update for {username} following {follow_username}")
        all_updates.append(update)

def main():
    env_vars = load_env_variables()
    setup_logging()
    headers = {
        "Authorization": f"Bearer {env_vars['airtable_token']}"
    }
    
    # Twitter API headers
    twitter_headers = {
        "Authorization": f"Bearer {env_vars['bearer_token']}"
    }
    
    list_members = fetch_list_members(env_vars['list_id'], twitter_headers)

    if not list_members:
        logging.error("Failed to fetch list members.")
        return

    # Fetch existing usernames and records
    existing_followers = fetch_records_from_airtable('tbl7bEfNVnCEQvUkT', headers)
    existing_usernames = {record['fields']['Username']: record['id'] for record in existing_followers if 'Username' in record['fields']}

    # Update the Followers table
    new_followers = [{"fields": {"Account ID": member['id'], "Username": member['username']}} for member in list_members if member['username'] not in existing_usernames]
    update_airtable_records(new_followers, 'tbl7bEfNVnCEQvUkT', headers)

    # Fetch updated usernames and accounts
    updated_followers = fetch_records_from_airtable('tbl7bEfNVnCEQvUkT', headers)
    existing_usernames.update({record['fields']['Username']: record['id'] for record in updated_followers if 'Username' in record['fields']})
    existing_accounts = fetch_records_from_airtable('tblJCXhcrCxDUJR3F', headers)
    existing_usernames.update({record['fields']['Username']: record['id'] for record in existing_accounts if 'Username' in record['fields']})

    driver = init_driver()
    load_cookies(driver, env_vars['cookie_path'])

    all_updates = []

    for member in list_members:
        username = member['username']
        record_id = existing_usernames.get(username)
        if record_id:
            try:
                process_user(username, record_id, driver, headers, all_updates, existing_usernames)
                logging.info(f"Processed {username}")
            except Exception as e:
                logging.error(f"Error processing {username}: {e}")

    unique_usernames = {update['fields']['Account'][0] for update in all_updates}
    fetch_and_save_accounts(unique_usernames, headers)
    driver.quit()
    
    # Call process_accounts to aggregate and save the final data
    process_accounts()

    response = send_file_via_webhook('joined_accounts.csv', 'https://hooks.zapier.com/hooks/catch/14552359/3v03fym/')
    if response.status_code == 200:
        logging.info("File sent successfully.")
    else:
        logging.error(f"Failed to send file. Status code: {response.status_code}")

if __name__ == "__main__":
    main()
