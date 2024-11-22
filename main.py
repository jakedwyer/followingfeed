import logging
from utils.logging_setup import setup_logging  # Import early for logging configuration

setup_logging()  # Initialize logging before other imports

import requests
import sys
import fcntl
from typing import Dict, List, Set, Optional, Any
from selenium import webdriver
from selenium.webdriver.remote.webdriver import (
    WebDriver,
)  # Standardized WebDriver import
from utils.airtable import (
    fetch_records_from_airtable,
    update_airtable_followers,
    fetch_existing_follows,
    fetch_and_update_accounts,
    update_airtable,
)
from utils.helpers import normalize_username, prepare_update_record
from utils.config import load_env_variables
from utils.twitter_helpers import get_following
from twitter.twitter import fetch_list_members
from scrape_empty_accounts import main as scrape_empty_accounts_main
from airtop import (
    Airtop as AirtopClient,
    SessionConfig,
)  # Correctly import AirtopClient
from utils.airtop_selenium import (
    init_airtop_driver,
    cleanup_airtop_session,
)  # Ensure correct import
import json

# Global constants
env_vars = load_env_variables()
BASE_ID = env_vars["airtable_base_id"]
LOCK_FILE = "/tmp/your_script_lock"
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


def scrape_with_airtop(username: str, driver, client, session, window_info):
    try:
        # Navigate to profile
        driver.get(f"https://x.com/{username}")

        # Use Airtop's AI scraping
        scrape_result = client.windows.scrape_content(
            session_id=session.data.id,
            window_id=window_info.data.window_id,
            time_threshold_seconds=30,
        )

        return scrape_result.data.model_response
    except Exception as e:
        logging.error(f"Failed to scrape {username}: {e}")
        return None


def fetch_profile(
    username: str, driver, client: AirtopClient, session, window_info
) -> Optional[Dict[str, Any]]:
    profile_data = scrape_with_airtop(username, driver, client, session, window_info)
    if profile_data:
        return dict(profile_data)  # Convert ScrapeResponseOutput to dictionary
    return None


def process_user(
    username: str,
    follower_record_id: str,
    driver: WebDriver,
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


def update_user_profile(
    username: str,
    profile: Dict[str, Any],
    accounts: Dict[str, str],
    headers: Dict[str, str],
) -> None:
    """
    Update a user's profile in Airtable.

    Args:
        username (str): The username of the profile to update
        profile (Dict[str, Any]): The profile data to update
        accounts (Dict[str, str]): Mapping of usernames to Airtable record IDs
        headers (Dict[str, str]): Headers for Airtable API requests
    """
    try:
        normalized_username = normalize_username(username)
        record_id = accounts.get(normalized_username)

        if not record_id:
            logging.error(f"No Airtable record found for username: {username}")
            return

        # Get existing record to compare fields
        response = requests.get(
            f"https://api.airtable.com/v0/{BASE_ID}/{ACCOUNTS_TABLE_ID}/{record_id}",
            headers=headers,
        )
        response.raise_for_status()
        existing_record = response.json()
        existing_fields = existing_record.get("fields", {})

        # Prepare update payload
        update_record = prepare_update_record(
            record_id=record_id,
            username=username,
            data=profile,
            existing_fields=existing_fields,
        )

        if update_record:
            response = requests.patch(
                f"https://api.airtable.com/v0/{BASE_ID}/{ACCOUNTS_TABLE_ID}",
                headers=headers,
                json={"records": [update_record]},
            )
            response.raise_for_status()
            logging.info(f"Successfully updated profile for {username}")
        else:
            logging.info(f"No updates needed for {username}")

    except requests.HTTPError as e:
        logging.error(f"Failed to update profile for {username}: {e.response.text}")
    except Exception as e:
        logging.error(f"Error updating profile for {username}: {str(e)}")


def main():
    logger = logging.getLogger(__name__)

    try:
        acquire_lock()

        # Initialize Airtop Client with proper configuration
        client = AirtopClient(api_key=env_vars["airtop_api_key"])

        # Create Airtop session with specific parameters
        session = client.sessions.create(
            configuration=SessionConfig(
                base_profile_id=env_vars["airtop_profile"],
                timeout_minutes=30,  # Increase timeout
                skip_wait_session_ready=False,  # Ensure session is ready
            )
        )

        try:
            # Initialize the Airtop-Selenium driver with retries
            driver, window_info = init_airtop_driver(
                env_vars["airtop_api_key"], client, session, max_retries=3
            )

            # Set up headers for Airtable
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
            # Enrich new Accounts running scrape_empty_accounts.py
            scrape_empty_accounts_main()

            # Example usage of the new fetch_profile
            # You might want to parameterize this or remove in production
            username = "exampleuser"
            profile = fetch_profile(
                username, driver, client, session, window_info
            )  # Pass client, session, window_info as parameters
            if profile:
                update_user_profile(
                    username, profile, accounts, headers
                )  # Pass accounts and headers as parameters
                # Continue with updating Airtable records as per your existing logic

        finally:
            # Clean up resources
            if "driver" in locals():
                driver.quit()

            # Always terminate the Airtop session
            client.sessions.terminate(session.data.id)

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        sys.exit(1)
    finally:
        release_lock()


if __name__ == "__main__":
    main()
