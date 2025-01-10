import logging
from utils.logging_setup import setup_logging  # Import early for logging configuration

setup_logging()  # Initialize logging before other imports

import requests
import sys
import fcntl
import gc
import psutil
import os
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Set, Tuple, Optional
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
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCK_FILE = "/tmp/followfeed_script.lock"

# Constants from environment variables
FOLLOWERS_TABLE_ID = env_vars["airtable_followers_table"]
ACCOUNTS_TABLE_ID = env_vars["airtable_accounts_table"]

# Performance optimization constants
MAX_CONCURRENT_PROCESSES = 2  # Conservative setting for 4 vCPUs
BATCH_SIZE = 5  # Reduced from 10 to be more memory-efficient


def log_memory_usage():
    """Log current memory usage of the process"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    logging.info(f"Memory usage: {memory_info.rss / 1024 / 1024:.2f} MB")


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
    """Normalize username by stripping whitespace and converting to lowercase."""
    return username.strip().lower()


async def fetch_and_update_accounts(
    usernames: Set[str],
    headers: Dict[str, str],
    accounts: Dict[str, str],
    session: Optional[aiohttp.ClientSession] = None,
) -> Dict[str, str]:
    """Fetch or create accounts for all usernames, including existing ones not in accounts dict."""
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
        ACCOUNTS_TABLE_ID, headers, formula=formula
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
        created_records = await batch_request_async(
            f"https://api.airtable.com/v0/{BASE_ID}/{ACCOUNTS_TABLE_ID}",
            headers,
            new_entries,
            session.post if session else requests.post,
        )

        # Only successfully created accounts are added
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


async def process_user(
    username: str,
    follower_record_id: str,
    driver: webdriver.Chrome,
    headers: Dict[str, str],
    accounts: Dict[str, str],
    record_id_to_username: Dict[str, str],
    session: Optional[aiohttp.ClientSession] = None,
) -> tuple[Dict[str, str], int]:
    """Process a user's following list and update Airtable accordingly."""
    try:
        # Get the accounts this user is already following
        existing_follows = await fetch_existing_follows_async(
            follower_record_id, headers, record_id_to_username, session
        )
        logging.info(f"Existing follows for {username}: {len(existing_follows)}")

        # Get new follows from Twitter
        new_follows = get_following(driver, username, existing_follows)
        if not new_follows:
            logging.info(f"No new follows found for {username}")
            return accounts, 0

        logging.info(f"Found {len(new_follows)} new follows for {username}")

        # Convert list to set and process in smaller batches
        new_follows_set = set(new_follows)
        accounts = await fetch_and_update_accounts(
            new_follows_set, headers, accounts, session
        )

        # Update the Followers field for each account while preserving existing followers
        accounts_to_update = []
        for uname in new_follows:
            normalized_uname = normalize_username(uname)
            if normalized_uname in accounts:
                account_id = accounts[normalized_uname]
                try:
                    # Fetch current followers for this account
                    if session:
                        async with session.get(
                            f"https://api.airtable.com/v0/{BASE_ID}/{ACCOUNTS_TABLE_ID}/{account_id}",
                            headers=headers,
                        ) as response:
                            if response.status == 200:
                                record = await response.json()
                                current_followers = record["fields"].get(
                                    "Followers", []
                                )
                                if follower_record_id not in current_followers:
                                    accounts_to_update.append(
                                        {
                                            "id": account_id,
                                            "fields": {
                                                "Followers": current_followers
                                                + [follower_record_id]
                                            },
                                        }
                                    )
                except Exception as e:
                    logging.error(
                        f"Failed to fetch followers for account {account_id}: {str(e)}"
                    )

        if accounts_to_update:
            # Update in smaller batches
            for i in range(0, len(accounts_to_update), BATCH_SIZE):
                batch = accounts_to_update[i : i + BATCH_SIZE]
                try:
                    await batch_request_async(
                        f"https://api.airtable.com/v0/{BASE_ID}/{ACCOUNTS_TABLE_ID}",
                        headers,
                        batch,
                        session.patch if session else requests.patch,
                    )
                    logging.info(
                        f"Successfully updated Followers field for batch of {len(batch)} accounts"
                    )
                    # Add a small delay between batches to respect rate limits
                    await asyncio.sleep(0.2)
                except Exception as e:
                    logging.error(
                        f"Failed to update Followers field for accounts batch: {str(e)}"
                    )

        # Clean up memory
        gc.collect()
        return accounts, len(new_follows)
    except Exception as e:
        logging.error(f"Error processing user {username}: {str(e)}")
        return accounts, 0


async def batch_request_async(
    url: str, headers: Dict[str, str], records: List[Dict], method
):
    """Asynchronous version of batch_request"""
    results = []
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        try:
            if asyncio.iscoroutinefunction(method):
                async with method(
                    url, headers=headers, json={"records": batch}
                ) as response:
                    if response.status == 200:
                        response_json = await response.json()
                        results.extend(response_json.get("records", []))
            else:
                response = method(url, headers=headers, json={"records": batch})
                response.raise_for_status()
                results.extend(response.json().get("records", []))

            logging.debug(
                f"Processed {len(batch)} entries in the {url.split('/')[-1]} table."
            )
        except Exception as e:
            logging.error(
                f"Failed to process entries in {url.split('/')[-1]} table: {str(e)}"
            )
    return results


async def fetch_existing_follows_async(
    record_id: str,
    headers: Dict[str, str],
    record_id_to_username: Dict[str, str],
    session: Optional[aiohttp.ClientSession] = None,
) -> Set[str]:
    """Asynchronous version of fetch_existing_follows"""
    try:
        if session:
            async with session.get(
                f"https://api.airtable.com/v0/{BASE_ID}/{FOLLOWERS_TABLE_ID}/{record_id}",
                headers=headers,
            ) as response:
                if response.status == 200:
                    record = await response.json()
                    existing_account_ids = record["fields"].get("Account", [])
                    existing_usernames = {
                        record_id_to_username.get(acc_id, "").lower()
                        for acc_id in existing_account_ids
                    }
                    return existing_usernames

        # Fallback to synchronous request if no session provided
        response = requests.get(
            f"https://api.airtable.com/v0/{BASE_ID}/{FOLLOWERS_TABLE_ID}/{record_id}",
            headers=headers,
        )
        response.raise_for_status()
        record = response.json()
        existing_account_ids = record["fields"].get("Account", [])
        existing_usernames = {
            record_id_to_username.get(acc_id, "").lower()
            for acc_id in existing_account_ids
        }
        return existing_usernames
    except Exception as e:
        logging.error(
            f"Failed to fetch existing follows for record {record_id}: {str(e)}"
        )
        return set()  # Return empty set instead of None


def fetch_current_account_ids(record_id: str, headers: Dict[str, str]) -> List[str]:
    """
    Fetch current Account IDs for a given follower record.
    """
    try:
        response = requests.get(
            f"https://api.airtable.com/v0/{BASE_ID}/{FOLLOWERS_TABLE_ID}/{record_id}",
            headers=headers,
        )
        response.raise_for_status()
        record = response.json()
        return record["fields"].get("Account", [])
    except requests.HTTPError as e:
        logging.error(
            f"Failed to fetch current account IDs for record {record_id}: {e.response.text}"
        )
        return []


async def process_list_members(
    list_members: List[Dict],
    followers: Dict[str, str],
    driver: webdriver.Chrome,
    headers: Dict[str, str],
    accounts: Dict[str, str],
    record_id_to_username: Dict[str, str],
) -> int:
    """Process list members asynchronously in batches"""
    total_new_handles = 0
    # Only process members that have a valid record_id
    members_to_process = [
        (member["username"].lower(), record_id)
        for member in list_members
        if (record_id := followers.get(member["username"].lower())) is not None
    ]

    # Process members in batches
    for i in range(0, len(members_to_process), BATCH_SIZE):
        batch = members_to_process[i : i + BATCH_SIZE]
        try:
            async with aiohttp.ClientSession() as session:
                for username, record_id in batch:
                    try:
                        accounts, new_handles = await process_user(
                            username,
                            record_id,  # Now we know record_id is not None
                            driver,
                            headers,
                            accounts,
                            record_id_to_username,
                            session,
                        )
                        total_new_handles += new_handles
                        # Add a small delay between users
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logging.error(f"Error processing {username}: {str(e)}")

            # Add delay between batches
            await asyncio.sleep(2)

            # Memory management after each batch
            gc.collect()
            log_memory_usage()

        except Exception as e:
            logging.error(f"Error processing batch starting at index {i}: {str(e)}")

    return total_new_handles


async def process_batch_of_followers(
    batch: List[Tuple[str, str]],
    driver: webdriver.Chrome,
    headers: Dict[str, str],
    accounts: Dict[str, str],
    record_id_to_username: Dict[str, str],
) -> Dict[str, str]:
    """Process a batch of followers asynchronously"""
    async with aiohttp.ClientSession() as session:
        for username, record_id in batch:
            try:
                accounts, new_handles = await process_user(
                    username,
                    record_id,
                    driver,
                    headers,
                    accounts,
                    record_id_to_username,
                    session,
                )
                logging.info(f"Processed {new_handles} new handles for {username}.")
                # Add a small delay between users to prevent rate limiting
                await asyncio.sleep(0.5)
            except Exception as e:
                logging.error(
                    f"Error processing follower {username}: {str(e)}", exc_info=True
                )
    return accounts


async def main_async():
    """Asynchronous version of main function"""
    logger = logging.getLogger(__name__)
    driver = None

    try:
        log_memory_usage()

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

        # Process followers in batches
        followers_items = list(followers.items())
        for i in range(0, len(followers_items), BATCH_SIZE):
            batch = followers_items[i : i + BATCH_SIZE]
            try:
                accounts = await process_batch_of_followers(
                    batch, driver, headers, accounts, record_id_to_username
                )
                logger.info(
                    f"Completed batch {i//BATCH_SIZE + 1} of {len(followers_items)//BATCH_SIZE + 1}"
                )

                # Memory management after each batch
                gc.collect()
                log_memory_usage()

                # Add delay between batches
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error processing batch: {str(e)}", exc_info=True)

        # Enrich new Accounts running scrape_empty_accounts.py
        scrape_empty_accounts_main()

    except Exception as e:
        logger.exception("An error occurred during execution")
    finally:
        if driver:
            driver.quit()
        log_memory_usage()
        logger.info("Main function completed.")


def main():
    """Entry point that runs the async main function"""
    # Set up logging
    logging.basicConfig(
        filename="main.log",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        acquire_lock()
        asyncio.run(main_async())
    except Exception as e:
        logging.exception("Failed to run main_async")
    finally:
        release_lock()


if __name__ == "__main__":
    main()
