import logging
import os
import sys
import fcntl
import requests
from typing import Dict, List, Set
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from utils.airtable import (
    fetch_records_from_airtable,
    post_airtable_records,
    update_airtable_records,
    update_followers_field
)
from utils.config import load_env_variables
from utils.logging_setup import setup_logging
from twitter.twitter import fetch_list_members, fetch_twitter_data_api
from scraping.scraping import init_driver, load_cookies, get_following
from scrape_empty_accounts import main as scrape_empty_accounts_main

# Global constants
BASE_ID = 'appYCZWcmNBXB2uUS'
LOCK_FILE = '/tmp/your_script_lock'
VENV_PATH = '/root/followfeed/xfeed/bin/activate'

def acquire_lock():
    global lock_fd
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.lockf(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        logging.error("Another instance is already running. Exiting.")
        sys.exit(1)

def release_lock():
    global lock_fd
    fcntl.lockf(lock_fd, fcntl.LOCK_UN)
    lock_fd.close()

def activate_virtualenv():
    """Activate the virtual environment if not already activated."""
    if not os.getenv('VIRTUAL_ENV') and os.path.exists(VENV_PATH):
        with open(VENV_PATH) as f:
            exec(f.read(), {'__file__': VENV_PATH})


def batch_request(url: str, headers: Dict[str, str], records: List[Dict], method):
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        response = method(url, headers=headers, json={"records": batch})
        if response.status_code in [200, 201]:
            logging.info(f"{method.__name__.capitalize()}d {len(batch)} entries in the {url.split('/')[-1]} table.")
        else:
            logging.error(f"Failed to {method.__name__} entries in {url.split('/')[-1]} table. Status code: {response.status_code}")
            logging.error(f"Response content: {response.content}")

def fetch_and_update_accounts(usernames: Set[str], headers: Dict[str, str], accounts: Dict[str, str]) -> Dict[str, str]:
    new_entries = [{"fields": {"Username": username}} for username in usernames if username not in accounts]
    if new_entries:
        post_airtable_records(new_entries, 'tblJCXhcrCxDUJR3F', headers)
        updated_records = fetch_records_from_airtable('tblJCXhcrCxDUJR3F', headers)
        accounts.update({record['fields']['Username'].lower(): record['id'] for record in updated_records if 'Username' in record['fields']})
    return accounts

def fetch_existing_follows(record_id: str, headers: Dict[str, str]) -> Set[str]:
    url = f"https://api.airtable.com/v0/{BASE_ID}/tbl7bEfNVnCEQvUkT/{record_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return set(response.json().get('fields', {}).get('Followed Accounts', []))
    else:
        logging.error(f"Failed to fetch existing follows for record ID {record_id}. Status code: {response.status_code}")
        logging.error(f"Response content: {response.content}")
        return set()

def process_user(username: str, follower_record_id: str, driver: webdriver.Chrome, headers: Dict[str, str], accounts: Dict[str, str]) -> tuple[Dict[str, str], int]:
    existing_follows = fetch_existing_follows(follower_record_id, headers)
    new_follows = get_following(driver, username, existing_follows)
    all_follows = {uname.lower() for uname in existing_follows.union(new_follows)}
    accounts = fetch_and_update_accounts(all_follows, headers, accounts)
    followed_account_ids = [accounts[uname] for uname in all_follows if uname in accounts]

    follower_update = {
        'id': follower_record_id,
        'fields': {'Account': followed_account_ids}
    }
    update_airtable_records([follower_update], 'tbl7bEfNVnCEQvUkT', headers)

    # Update the Followers field for each followed account
    for account_id in followed_account_ids:
        update_followers_field(account_id, follower_record_id, headers)

    return accounts, len(new_follows)

def main():
    acquire_lock()
    try:
        activate_virtualenv()
        env_vars = load_env_variables()
        setup_logging()
        logging.info("Main function started")
        headers = {"Authorization": f"Bearer {env_vars['airtable_token']}"}
        twitter_headers = {"Authorization": f"Bearer {env_vars['bearer_token']}"}

        list_members = fetch_list_members(env_vars['list_id'], twitter_headers)
        if not list_members:
            logging.error("Failed to fetch list members.")
            return

        existing_followers = fetch_records_from_airtable('tbl7bEfNVnCEQvUkT', headers)
        followers = {record['fields']['Username'].lower(): record['id'] for record in existing_followers if 'Username' in record['fields']}

        new_followers = [{"fields": {"Account ID": member['id'], "Username": member['username']}} for member in list_members if member['username'].lower() not in followers]
        post_airtable_records(new_followers, 'tbl7bEfNVnCEQvUkT', headers)
        updated_followers = fetch_records_from_airtable('tbl7bEfNVnCEQvUkT', headers)
        existing_accounts = fetch_records_from_airtable('tblJCXhcrCxDUJR3F', headers)        
        followers.update({record['fields']['Username'].lower(): record['id'] for record in updated_followers if 'Username' in record['fields']})
        accounts = {record['fields']['Username'].lower(): record['id'] for record in existing_accounts if 'Username' in record['fields']}
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        try:
            service = Service(ChromeDriverManager().install())
        except Exception as e:
            logging.error(f"Failed to set up Chrome WebDriver: {str(e)}")
            raise

        with webdriver.Chrome(service=service, options=chrome_options) as driver:
            if env_vars['cookie_path'] is not None:
                load_cookies(driver, env_vars['cookie_path'])
            else:
                logging.warning("Cookie path is None, skipping load_cookies.")

            total_new_handles = 0
            for member in list_members:
                username = member['username'].lower()
                if record_id := followers.get(username):
                    try:
                        accounts, new_handles = process_user(username, record_id, driver, headers, accounts)
                        total_new_handles += new_handles
                    except Exception as e:
                        logging.error(f"Error processing {username}: {e}")

            logging.info(f"Total new handles found: {total_new_handles}")
            scrape_empty_accounts_main()

    finally:
        release_lock()

if __name__ == "__main__":
    main()
