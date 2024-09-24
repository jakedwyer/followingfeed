import logging
from utils.logging_setup import setup_logging  # Import early for logging configuration

setup_logging()  # Initialize logging before other imports

import requests
import sys
import fcntl
from typing import Dict, List, Set
from selenium import webdriver
from utils.airtable import (
    fetch_records_from_airtable,
    post_airtable_records,
    update_airtable_records,
    update_followers_field,
)
from utils.config import load_env_variables
from twitter.twitter import fetch_list_members
from scraping.scraping import (
    init_driver,
    load_cookies,
    get_following,
)
from scrape_empty_accounts import main as scrape_empty_accounts_main
from fetch_profile import main as fetch_profile_main

# Global constants
env_vars = load_env_variables()
BASE_ID = env_vars["airtable_base_id"]
LOCK_FILE = "/tmp/your_script_lock"


def acquire_lock():
    global lock_fd
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.lockf(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        logging.error("Another instance is already running. Exiting.")
        sys.exit(1)


def release_lock():
    global lock_fd
    fcntl.lockf(lock_fd, fcntl.LOCK_UN)
    lock_fd.close()


def batch_request(url: str, headers: Dict[str, str], records: List[Dict], method):
    for i in range(0, len(records), 10):
        batch = records[i : i + 10]
        try:
            response = method(url, headers=headers, json={"records": batch})
            response.raise_for_status()
            logging.debug(
                f"{method.__name__.capitalize()}d {len(batch)} entries in the {url.split('/')[-1]} table."
            )
        except requests.HTTPError as e:
            logging.error(
                f"Failed to {method.__name__} entries in {url.split('/')[-1]} table. Status code: {e.response.status_code}"
            )
            logging.debug(f"Response content: {e.response.content.decode('utf-8')}")


def normalize_username(username: str) -> str:
    return username.strip().lower()


def fetch_and_update_accounts(
    usernames: Set[str], headers: Dict[str, str], accounts: Dict[str, str]
) -> Dict[str, str]:
    normalized_usernames = {normalize_username(username) for username in usernames}
    new_usernames = normalized_usernames - set(accounts.keys())
    new_entries = [{"fields": {"Username": username}} for username in new_usernames]
    if new_entries:
        post_airtable_records(new_entries, "tblJCXhcrCxDUJR3F", headers)
        updated_records = fetch_records_from_airtable("tblJCXhcrCxDUJR3F", headers)
        accounts.update(
            {
                normalize_username(record["fields"]["Username"]): record["id"]
                for record in updated_records
                if "Username" in record["fields"]
            }
        )
    return accounts


def fetch_existing_follows(
    follower_record_id: str,
    headers: Dict[str, str],
    record_id_to_username: Dict[str, str],
) -> Set[str]:
    url = (
        f"https://api.airtable.com/v0/{BASE_ID}/tbl7bEfNVnCEQvUkT/{follower_record_id}"
    )
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        logging.debug(f"Fetched follower record {follower_record_id}: {data}")
        linked_account_ids = data["fields"].get("Account", [])
        follows = {
            record_id_to_username.get(acc_id, "").lower()
            for acc_id in linked_account_ids
        }
        logging.debug(f"Existing follows for follower {follower_record_id}: {follows}")
        return follows
    else:
        logging.error(
            f"Failed to fetch follower record {follower_record_id}. Status code: {response.status_code}"
        )
        logging.error(f"Response: {response.text}")
        return set()


def process_user(
    username: str,
    follower_record_id: str,
    driver: webdriver.Chrome,
    headers: Dict[str, str],
    accounts: Dict[str, str],
    record_id_to_username: Dict[str, str],
) -> tuple[Dict[str, str], int]:
    existing_follows = fetch_existing_follows(
        follower_record_id, headers, record_id_to_username
    )
    new_follows = get_following(driver, username, existing_follows)
    all_follows = {uname.lower() for uname in existing_follows.union(new_follows)}

    accounts = fetch_and_update_accounts(all_follows, headers, accounts)

    followed_account_ids = [
        accounts[uname] for uname in all_follows if uname in accounts
    ]

    follower_update = {
        "id": follower_record_id,
        "fields": {"Account": followed_account_ids},
    }
    update_airtable_records([follower_update], "tbl7bEfNVnCEQvUkT", headers)

    for account_id in followed_account_ids:
        update_followers_field(account_id, follower_record_id, headers)

    return accounts, len(new_follows)


def process_list_members(
    list_members, followers, driver, headers, accounts, record_id_to_username
):
    total_new_handles = 0
    for member in list_members:
        username = member["username"].lower()
        record_id = followers.get(username)
        if record_id:
            try:
                accounts, new_handles = process_user(
                    username,
                    record_id,
                    driver,
                    headers,
                    accounts,
                    record_id_to_username,
                )
                total_new_handles += new_handles
            except Exception as e:
                logging.error(f"Error processing {username}: {e}")
    return total_new_handles


def main():
    setup_logging()
    acquire_lock()
    try:
        env_vars = load_env_variables()
        logger = logging.getLogger(__name__)
        logger.info("Main function started")

        headers = {"Authorization": f"Bearer {env_vars['airtable_token']}"}
        twitter_headers = {
            "Authorization": f"Bearer {env_vars['twitter_bearer_token']}"
        }
        cookie_path = env_vars.get("cookie_path")
        list_members = fetch_list_members(env_vars["list_id"], twitter_headers)
        if not list_members:
            logger.error("Failed to fetch list members.")
            return

        existing_followers = fetch_records_from_airtable("tbl7bEfNVnCEQvUkT", headers)
        followers = {
            record["fields"]["Username"].lower(): record["id"]
            for record in existing_followers
            if "Username" in record["fields"]
        }

        existing_accounts = fetch_records_from_airtable("tblJCXhcrCxDUJR3F", headers)
        accounts = {
            record["fields"]["Username"].lower(): record["id"]
            for record in existing_accounts
            if "Username" in record["fields"]
        }
        record_id_to_username = {
            record["id"]: record["fields"]["Username"].lower()
            for record in existing_accounts
            if "Username" in record["fields"]
        }

        new_followers = [
            {
                "fields": {
                    "Account ID": member["id"],
                    "Username": member["username"],
                }
            }
            for member in list_members
            if member["username"].lower() not in followers
        ]

        if new_followers:
            post_airtable_records(new_followers, "tbl7bEfNVnCEQvUkT", headers)
            updated_followers = fetch_records_from_airtable(
                "tbl7bEfNVnCEQvUkT", headers
            )
            followers.update(
                {
                    record["fields"]["Username"].lower(): record["id"]
                    for record in updated_followers
                    if "Username" in record["fields"]
                }
            )

        driver = init_driver()

        if cookie_path:
            load_cookies(driver, cookie_path)
            logger.info(f"Cookies loaded from {cookie_path}")
        else:
            logger.warning(
                "COOKIE_PATH is not set in environment variables. Skipping cookie loading."
            )

        total_new_handles = process_list_members(
            list_members, followers, driver, headers, accounts, record_id_to_username
        )
        logger.info(f"Total new handles found: {total_new_handles}")

        fetch_profile_main()
        scrape_empty_accounts_main()

    except Exception as e:
        logger.exception("An error occurred during execution.")
    finally:
        release_lock()


if __name__ == "__main__":
    main()
