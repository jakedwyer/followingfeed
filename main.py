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

# Constants from environment variables
FOLLOWERS_TABLE_ID = env_vars["airtable_followers_table"]
ACCOUNTS_TABLE_ID = env_vars["airtable_accounts_table"]


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
    results = []
    for i in range(0, len(records), 10):
        batch = records[i : i + 10]
        try:
            response = method(url, headers=headers, json={"records": batch})
            response.raise_for_status()
            results.extend(response.json().get("records", []))
            logging.debug(
                f"{method.__name__.capitalize()}d {len(batch)} entries in the {url.split('/')[-1]} table."
            )
        except requests.HTTPError as e:
            logging.error(
                f"Failed to {method.__name__} entries in {url.split('/')[-1]} table. Status code: {e.response.status_code}"
            )
            logging.debug(f"Response content: {e.response.content.decode('utf-8')}")
    return results


def normalize_username(username: str) -> str:
    return username.strip().lower()


def fetch_and_update_accounts(
    usernames: Set[str], headers: Dict[str, str], accounts: Dict[str, str]
) -> Dict[str, str]:
    """
    Fetch or create accounts for all usernames, including existing ones not in accounts dict.
    """
    normalized_usernames = {normalize_username(username) for username in usernames}

    # First, fetch ALL existing accounts from Airtable that match our usernames
    formula = (
        "OR("
        + ",".join(
            [f"LOWER({{Username}}) = '{username}'" for username in normalized_usernames]
        )
        + ")"
    )
    existing_records = fetch_records_from_airtable(
        "tblJCXhcrCxDUJR3F", headers, formula=formula  # Accounts table
    )

    # Update accounts dict with any existing accounts we didn't know about
    for record in existing_records:
        username = normalize_username(record["fields"].get("Username", ""))
        if username:
            accounts[username] = record["id"]
            logging.debug(f"Found existing account: {username} -> {record['id']}")

    # Now create any truly new accounts
    new_usernames = normalized_usernames - set(accounts.keys())
    if new_usernames:
        logging.info(f"Creating {len(new_usernames)} new accounts")
        new_entries = [{"fields": {"Username": username}} for username in new_usernames]

        # Create new accounts in batches
        created_records = batch_request(
            f"https://api.airtable.com/v0/{BASE_ID}/tblJCXhcrCxDUJR3F",
            headers,
            new_entries,
            requests.post,
        )

        # Update accounts dictionary with new records
        if created_records:
            for record in created_records:
                username = normalize_username(record["fields"].get("Username", ""))
                if username:
                    accounts[username] = record["id"]
                    logging.debug(f"Created new account: {username} -> {record['id']}")

    return accounts


def fetch_existing_follows(
    record_id: str, headers: Dict[str, str], record_id_to_username: Dict[str, str]
) -> Set[str]:
    """
    Fetch existing follows for a given follower.
    """
    try:
        response = requests.get(
            f"https://api.airtable.com/v0/{BASE_ID}/{FOLLOWERS_TABLE_ID}/{record_id}",
            headers=headers,
        )
        response.raise_for_status()
        record = response.json()
        existing_account_ids = record["fields"].get("Account", [])
        # Reverse map to usernames if needed
        existing_usernames = {
            record_id_to_username.get(acc_id, "").lower()
            for acc_id in existing_account_ids
        }
        return existing_usernames
    except requests.HTTPError as e:
        logging.error(
            f"Failed to fetch existing follows for record {record_id}: {e.response.text}"
        )
        return set()


def prepare_follower_update(record_id: str, account_ids: List[str]) -> Dict:
    """
    Prepare the payload for updating a follower's Account field.
    """
    return {
        "id": record_id,
        "fields": {
            "Account": account_ids  # Ensure this field is a Linked Record field in Airtable
        },
    }


def update_airtable_followers(
    follower_record_id: str, account_ids: List[str], headers: Dict[str, str]
) -> bool:
    """
    Update the Followers table with the new list of account IDs.
    """
    follower_update = {"id": follower_record_id, "fields": {"Account": account_ids}}
    try:
        response = requests.patch(
            f"https://api.airtable.com/v0/{BASE_ID}/{FOLLOWERS_TABLE_ID}",
            headers=headers,
            json={"records": [follower_update]},
        )
        response.raise_for_status()
        logging.info(
            f"Successfully updated follower {follower_record_id} with {len(account_ids)} accounts."
        )
        return True
    except requests.HTTPError as e:
        logging.error(
            f"Failed to update follower {follower_record_id}: {e.response.text}"
        )
        return False


def process_user(
    username: str,
    follower_record_id: str,
    driver: webdriver.Chrome,
    headers: Dict[str, str],
    accounts: Dict[str, str],
    record_id_to_username: Dict[str, str],
) -> tuple[Dict[str, str], int]:
    """
    Process a user's following list and update Airtable accordingly.
    """
    existing_follows = fetch_existing_follows(
        follower_record_id, headers, record_id_to_username
    )
    logging.info(f"Existing follows for {username}: {len(existing_follows)}")

    new_follows = get_following(driver, username, existing_follows)
    all_follows = {
        normalize_username(uname) for uname in existing_follows.union(new_follows)
    }
    logging.info(f"Total follows for {username}: {len(all_follows)}")

    # Update accounts dictionary with any new accounts
    accounts = fetch_and_update_accounts(all_follows, headers, accounts)

    # Get account IDs for all follows
    followed_account_ids = []
    missing_accounts = []
    for uname in all_follows:
        normalized_uname = normalize_username(uname)
        if normalized_uname in accounts:
            followed_account_ids.append(accounts[normalized_uname])
        else:
            missing_accounts.append(uname)
            logging.warning(f"Account not found: {uname}")

    if missing_accounts:
        logging.error(f"Missing accounts: {missing_accounts}")

    # Update follower record with ALL account IDs
    if followed_account_ids:
        success = update_airtable_followers(
            follower_record_id, followed_account_ids, headers
        )
        if not success:
            logging.error(f"Failed to update all accounts for follower {username}.")
        else:
            logging.info(
                f"Successfully updated {username} with {len(followed_account_ids)} follows"
            )

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
    # Set up logging
    logging.basicConfig(
        filename="main.log",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    try:
        # Initialize the driver before the loop
        driver = init_driver()
        cookie_path = env_vars.get("cookie_path")
        if cookie_path:
            load_cookies(driver, cookie_path)
            logger.info(f"Cookies loaded from {cookie_path}")

        headers = {
            "Authorization": f"Bearer {env_vars['airtable_token']}",
            "Content-Type": "application/json",
        }

        # Fetch existing followers
        existing_followers = fetch_records_from_airtable(FOLLOWERS_TABLE_ID, headers)
        followers = {
            record["fields"]["Username"].lower(): record["id"]
            for record in existing_followers
            if "Username" in record["fields"]
        }

        # Fetch existing accounts
        existing_accounts = fetch_records_from_airtable(ACCOUNTS_TABLE_ID, headers)
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

        # Process each follower
        for username, record_id in followers.items():
            try:
                accounts, new_handles = process_user(
                    username,
                    record_id,
                    driver,
                    headers,
                    accounts,
                    record_id_to_username,
                )
                logger.info(f"Processed {new_handles} new handles for {username}.")
            except Exception as e:
                logger.error(
                    f"Error processing follower {username}: {str(e)}", exc_info=True
                )

    except Exception as e:
        logger.exception("An error occurred during execution")
    finally:
        if "driver" in locals():
            driver.quit()
        logger.info("Main function completed.")


if __name__ == "__main__":
    main()
