import logging
import requests
from utils.config import load_env_variables
from utils.logging_setup import setup_logging
from twitter.twitter import fetch_list_members
from scraping.scraping import init_driver, load_cookies, get_following

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

def batch_request(url, headers, records, method):
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        response = method(url, headers=headers, json={"records": batch})
        if response.status_code in [200, 201]:
            logging.info(f"{method.__name__.capitalize()} {len(batch)} entries in the {url.split('/')[-1]} table.")
        else:
            logging.error(f"Failed to {method.__name__} entries in {url.split('/')[-1]} table. Status code: {response.status_code}")
            logging.error(f"Response content: {response.content}")

def update_airtable_records(records, table_id, headers):
    base_id = 'appYCZWcmNBXB2uUS'
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    batch_request(url, headers, records, requests.patch)

def create_airtable_records(records, table_id, headers):
    base_id = 'appYCZWcmNBXB2uUS'
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    batch_request(url, headers, records, requests.post)

def fetch_and_update_accounts(usernames, headers, accounts_usernames):
    new_entries = [{"fields": {"Username": username}} for username in usernames if username not in accounts_usernames]
    if new_entries:
        create_airtable_records(new_entries, 'tblJCXhcrCxDUJR3F', headers)
        updated_records = fetch_records_from_airtable('tblJCXhcrCxDUJR3F', headers)
        accounts_usernames.update({record['fields']['Username']: record['id'] for record in updated_records if 'Username' in record['fields']})
    return accounts_usernames

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

def process_user(username, follower_record_id, driver, headers, followers_usernames, accounts_usernames):
    existing_follows_usernames = fetch_existing_follows(follower_record_id, headers)
    new_follows_usernames = get_following(driver, username, existing_follows_usernames)
    all_follows_usernames = existing_follows_usernames.union(new_follows_usernames)

    accounts_usernames = fetch_and_update_accounts(all_follows_usernames, headers, accounts_usernames)

    # Map the followed usernames to their record IDs
    followed_account_ids = [accounts_usernames[username] for username in all_follows_usernames if username in accounts_usernames]

    # Update Follower's "Account" field with the full list of account record IDs they follow
    follower_update = {
        'id': follower_record_id,
        'fields': {'Account': followed_account_ids}
    }
    update_airtable_records([follower_update], 'tbl7bEfNVnCEQvUkT', headers)

def main():
    env_vars = load_env_variables()
    setup_logging()
    headers = {"Authorization": f"Bearer {env_vars['airtable_token']}"}
    twitter_headers = {"Authorization": f"Bearer {env_vars['bearer_token']}"}
    
    list_members = fetch_list_members(env_vars['list_id'], twitter_headers)
    if not list_members:
        logging.error("Failed to fetch list members.")
        return

    existing_followers = fetch_records_from_airtable('tbl7bEfNVnCEQvUkT', headers)
    followers_usernames = {record['fields']['Username']: record['id'] for record in existing_followers if 'Username' in record['fields']}
    
    new_followers = [{"fields": {"Account ID": member['id'], "Username": member['username']}} for member in list_members if member['username'] not in followers_usernames]
    create_airtable_records(new_followers, 'tbl7bEfNVnCEQvUkT', headers)
    
    updated_followers = fetch_records_from_airtable('tbl7bEfNVnCEQvUkT', headers)
    followers_usernames.update({record['fields']['Username']: record['id'] for record in updated_followers if 'Username' in record['fields']})
    
    existing_accounts = fetch_records_from_airtable('tblJCXhcrCxDUJR3F', headers)
    accounts_usernames = {record['fields']['Username']: record['id'] for record in existing_accounts if 'Username' in record['fields']}

    driver = init_driver()
    load_cookies(driver, env_vars['cookie_path'])

    for member in list_members:
        username = member['username']
        record_id = followers_usernames.get(username)
        if record_id:
            try:
                process_user(username, record_id, driver, headers, followers_usernames, accounts_usernames)
            except Exception as e:
                logging.error(f"Error processing {username}: {e}")

    driver.quit()

if __name__ == "__main__":
    main()
