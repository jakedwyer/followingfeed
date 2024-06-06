import logging
import requests
from utils.config import load_env_variables
from utils.logging_setup import setup_logging
from twitter.twitter import fetch_list_members
from scraping.scraping import init_driver, load_cookies, get_following

def send_file_via_webhook(file_path, webhook_url):
    with open(file_path, 'rb') as f:
        return requests.post(webhook_url, files={'file': f})

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
        response = requests.patch(url, headers=headers, json={"records": batch})
        if response.status_code == 200:
            logging.info(f"Updated {len(batch)} entries in the {table_id} table.")
        else:
            logging.error(f"Failed to update entries in {table_id} table. Status code: {response.status_code}")
            logging.error(f"Response content: {response.content}")

def create_airtable_records(records, table_id, headers):
    base_id = 'appYCZWcmNBXB2uUS'
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        response = requests.post(url, headers=headers, json={"records": batch})
        if response.status_code == 200:
            logging.info(f"Created {len(batch)} entries in the {table_id} table.")
        else:
            logging.error(f"Failed to create entries in {table_id} table. Status code: {response.status_code}")
            logging.error(f"Response content: {response.content}")

def fetch_and_update_accounts(usernames, headers, existing_usernames):
    new_entries = [{"fields": {"Username": username, "Followers": []}} for username in usernames if username not in existing_usernames]
    if new_entries:
        create_airtable_records(new_entries, 'tblJCXhcrCxDUJR3F', headers)
    updated_records = fetch_records_from_airtable('tblJCXhcrCxDUJR3F', headers)
    return {record['fields']['Username']: record['id'] for record in updated_records if 'Username' in record['fields']}

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

def process_user(username, follower_record_id, driver, headers, existing_usernames):
    existing_follows = fetch_existing_follows(follower_record_id, headers)
    new_follows = get_following(driver, username, existing_follows)
    existing_usernames = fetch_and_update_accounts(new_follows, headers, existing_usernames)

    # Update Follower's "Followed Accounts" field with the full list of accounts they follow
    updated_followed_accounts = list(existing_follows.union(new_follows))
    follower_update = {
        'id': follower_record_id,
        'fields': {'Followed Accounts': updated_followed_accounts}
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
    existing_usernames = {record['fields']['Username']: record['id'] for record in existing_followers if 'Username' in record['fields']}
    new_followers = [{"fields": {"Account ID": member['id'], "Username": member['username']}} for member in list_members if member['username'] not in existing_usernames]
    create_airtable_records(new_followers, 'tbl7bEfNVnCEQvUkT', headers)
    updated_followers = fetch_records_from_airtable('tbl7bEfNVnCEQvUkT', headers)
    existing_usernames.update({record['fields']['Username']: record['id'] for record in updated_followers if 'Username' in record['fields']})
    existing_accounts = fetch_records_from_airtable('tblJCXhcrCxDUJR3F', headers)
    existing_usernames.update({record['fields']['Username']: record['id'] for record in existing_accounts if 'Username' in record['fields']})

    driver = init_driver()
    load_cookies(driver, env_vars['cookie_path'])

    for member in list_members:
        username = member['username']
        record_id = existing_usernames.get(username)
        if record_id:
            try:
                process_user(username, record_id, driver, headers, existing_usernames)
            except Exception as e:
                logging.error(f"Error processing {username}: {e}")

    driver.quit()

    response = send_file_via_webhook('joined_accounts.csv', 'https://hooks.zapier.com/hooks/catch/14552359/3v03fym/')
    logging.info("File sent successfully." if response.status_code == 200 else f"Failed to send file. Status code: {response.status_code}")

if __name__ == "__main__":
    main()
