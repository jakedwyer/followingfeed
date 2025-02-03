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
from pathlib import Path
from dotenv import load_dotenv

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

# Add absolute path handling
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))


def log_memory_usage():
    """Log current memory usage of the process"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    logging.info(f"Memory usage: {memory_info.rss / 1024 / 1024:.2f} MB")


def acquire_lock(lock_file):
    """Acquire a lock file with proper error handling"""
    try:
        if os.path.exists(lock_file):
            # Check if the process is actually running
            with open(lock_file, "r") as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, 0)  # Check if process is running
                raise LockError(f"Process {pid} is still running")
            except OSError:
                # Process not running, safe to remove stale lock
                os.unlink(lock_file)

        # Create new lock file
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        raise LockError(f"Failed to acquire lock: {str(e)}")


def release_lock(lock_file):
    """Release the lock file"""
    try:
        if os.path.exists(lock_file):
            os.unlink(lock_file)
    except Exception as e:
        logging.error(f"Failed to release lock: {str(e)}")


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

        if session:
            # Use session directly for async operation
            try:
                async with session.post(
                    f"https://api.airtable.com/v0/{BASE_ID}/{ACCOUNTS_TABLE_ID}",
                    headers=headers,
                    json={"records": new_entries},
                ) as response:
                    if response.status == 200:
                        created_records = await response.json()
                        created_records = created_records.get("records", [])
                        # Only successfully created accounts are added
                        for record in created_records:
                            username = normalize_username(
                                record["fields"].get("Username", "")
                            )
                            if username:
                                accounts[username] = record["id"]
                                logging.debug(
                                    f"Created new account: {username} -> {record['id']}"
                                )
            except Exception as e:
                logging.error(f"Failed to create new accounts: {str(e)}")
        else:
            # Fallback to synchronous operation if no session provided
            try:
                response = requests.post(
                    f"https://api.airtable.com/v0/{BASE_ID}/{ACCOUNTS_TABLE_ID}",
                    headers=headers,
                    json={"records": new_entries},
                )
                response.raise_for_status()
                created_records = response.json().get("records", [])
                for record in created_records:
                    username = normalize_username(record["fields"].get("Username", ""))
                    if username:
                        accounts[username] = record["id"]
                        logging.debug(
                            f"Created new account: {username} -> {record['id']}"
                        )
            except Exception as e:
                logging.error(f"Failed to create new accounts: {str(e)}")

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
                    if session:
                        async with session.patch(
                            f"https://api.airtable.com/v0/{BASE_ID}/{ACCOUNTS_TABLE_ID}",
                            headers=headers,
                            json={"records": batch},
                        ) as response:
                            if response.status == 200:
                                logging.info(
                                    f"Successfully updated Followers field for batch of {len(batch)} accounts"
                                )
                    await asyncio.sleep(0.2)  # Rate limiting protection
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
) -> List[Dict]:
    """Asynchronous version of batch_request"""
    results = []
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        try:
            if isinstance(method, aiohttp.ClientSession):
                # If method is a session, use it directly
                async with method.post(
                    url, headers=headers, json={"records": batch}
                ) as response:
                    if response.status == 200:
                        response_json = await response.json()
                        results.extend(response_json.get("records", []))
            elif asyncio.iscoroutinefunction(method):
                # If method is an async function
                async with method(
                    url, headers=headers, json={"records": batch}
                ) as response:
                    if response.status == 200:
                        response_json = await response.json()
                        results.extend(response_json.get("records", []))
            else:
                # For synchronous methods (requests)
                response = method(url, headers=headers, json={"records": batch})
                response.raise_for_status()
                results.extend(response.json().get("records", []))

            logging.debug(
                f"Processed {len(batch)} entries in the {url.split('/')[-1]} table."
            )
            await asyncio.sleep(0.2)  # Rate limiting protection
        except Exception as e:
            logging.error(
                f"Failed to process entries in {url.split('/')[-1]} table: {str(e)}"
            )
            logging.debug(f"Failed batch data: {batch}")
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
    max_retries = 3
    retry_count = 0

    try:
        log_memory_usage()

        while retry_count < max_retries:
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
                existing_followers = fetch_records_from_airtable(
                    FOLLOWERS_TABLE_ID, headers
                )
                followers = {
                    record["fields"]["Username"].lower(): record["id"]
                    for record in existing_followers
                    if "Username" in record["fields"]
                }

                # Fetch existing accounts
                existing_accounts = fetch_records_from_airtable(
                    ACCOUNTS_TABLE_ID, headers
                )
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
                processed_count = 0
                total_followers = len(followers.items())

                async with aiohttp.ClientSession() as session:
                    async with asyncio.TaskGroup() as tg:
                        for i in range(0, total_followers, BATCH_SIZE):
                            batch = list(followers.items())[i : i + BATCH_SIZE]
                            batch_tasks = []

                            for username, record_id in batch:
                                try:
                                    task = tg.create_task(
                                        process_user(
                                            username,
                                            record_id,
                                            driver,
                                            headers,
                                            accounts,
                                            record_id_to_username,
                                            session,
                                        )
                                    )
                                    batch_tasks.append(task)
                                    processed_count += 1

                                    if processed_count % 10 == 0:
                                        logger.info(
                                            f"Progress: {processed_count}/{total_followers} followers processed"
                                        )

                                    # Add a small delay between user task creation
                                    await asyncio.sleep(0.5)
                                except Exception as e:
                                    logger.error(
                                        f"Error processing follower {username}: {str(e)}",
                                        exc_info=True,
                                    )
                                    # If WebDriver error, break the loop to restart driver
                                    if "Connection refused" in str(e):
                                        raise Exception("WebDriver connection lost")

                            # Process tasks in the batch
                            for task, username in zip(
                                batch_tasks, [item[0] for item in batch]
                            ):
                                try:
                                    result = await task
                                    new_accounts, new_handles = result
                                    accounts.update(new_accounts)
                                    logger.info(
                                        f"Processed {new_handles} new handles for {username}."
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Task failed for {username}: {str(e)}",
                                        exc_info=True,
                                    )

                            # Add delay between batches
                            await asyncio.sleep(2)

                            # Memory management after each batch
                            gc.collect()
                            log_memory_usage()

                # If we get here, everything worked
                break

            except Exception as e:
                retry_count += 1
                logger.error(f"Attempt {retry_count} failed: {str(e)}")
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = None
                if retry_count < max_retries:
                    logger.info(f"Retrying in 30 seconds...")
                    await asyncio.sleep(30)
                else:
                    logger.error("Max retries reached. Exiting.")
                    raise

        # Enrich new Accounts running scrape_empty_accounts.py
        scrape_empty_accounts_main()

    except Exception as e:
        logger.exception("An error occurred during execution")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        log_memory_usage()
        logger.info("Main function completed.")


def main():
    """Entry point that runs the async main function"""
    try:
        # Change to the script's directory
        os.chdir(BASE_DIR)

        # Set up logging with absolute paths
        log_file = os.path.join(BASE_DIR, "logs", "main.log")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Initialize logging
        setup_logging()
        logger = logging.getLogger(__name__)

        # Load environment variables
        load_env()

        # Create lock file with absolute path
        lock_file = os.path.join(BASE_DIR, ".script.lock")
        try:
            acquire_lock(lock_file)
            logger.info("Starting scheduled execution")
            asyncio.run(main_async())
            logger.info("Scheduled execution completed successfully")
        except LockError:
            logger.warning("Another instance is already running")
            sys.exit(1)
        except Exception as e:
            logger.exception("Failed to run main_async")
            sys.exit(1)
        finally:
            release_lock(lock_file)
            logger.info("Lock released")
    except Exception as e:
        print(f"Critical error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def load_env():
    """Load environment variables from .env file"""
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        raise Exception(".env file not found in application directory")


class LockError(Exception):
    """Raised when lock cannot be acquired"""

    pass


def setup_logging():
    """Configure logging with both file and console handlers"""
    log_file = os.path.join(BASE_DIR, "logs", "main.log")

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove any existing handlers
    root_logger.handlers = []

    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


if __name__ == "__main__":
    main()
