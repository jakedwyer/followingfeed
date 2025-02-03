#!/usr/bin/env python3
import os
import logging
import time
from typing import Dict, Set
from utils.config import load_env_variables
from utils.airtable import (
    fetch_records_from_airtable,
    fetch_accounts_by_usernames,
    fetch_and_update_accounts,
)

# Set up logging with more verbose output
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


def test_fetch_records():
    """Test fetching records from Airtable"""
    try:
        logger.info("Loading environment variables...")
        env_vars = load_env_variables()

        # Check if required environment variables are present
        required_vars = [
            "airtable_token",
            "airtable_base_id",
            "airtable_accounts_table",
        ]
        for var in required_vars:
            if not env_vars.get(var):
                logger.error(f"Missing required environment variable: {var}")
                return False

        logger.info("Setting up headers...")
        headers = {
            "Authorization": f"Bearer {env_vars['airtable_token']}",
            "Content-Type": "application/json",
        }
        logger.debug(f"Using base_id: {env_vars['airtable_base_id']}")
        logger.debug(f"Using table_id: {env_vars['airtable_accounts_table']}")

        # Test basic fetch with retries
        logger.info("Testing basic record fetch...")
        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"Fetch attempt {attempt + 1}/{MAX_RETRIES}")
                records = fetch_records_from_airtable(
                    env_vars["airtable_accounts_table"], headers
                )
                if records:
                    logger.info(f"Successfully fetched {len(records)} records")
                    break
                else:
                    logger.error("Failed to fetch records")
                    if attempt < MAX_RETRIES - 1:
                        logger.debug(f"Retrying in {RETRY_DELAY} seconds...")
                        time.sleep(RETRY_DELAY)
                        continue
                    return False
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    time.sleep(RETRY_DELAY)
                    continue
                logger.error(f"All attempts failed: {str(e)}")
                return False

        # Test fetch with formula
        logger.info("Testing fetch with formula...")
        formula = "NOT({Full Name} = '')"
        filtered_records = fetch_records_from_airtable(
            env_vars["airtable_accounts_table"], headers, formula=formula
        )
        if filtered_records:
            logger.info(
                f"Successfully fetched {len(filtered_records)} filtered records"
            )
        else:
            logger.error("Failed to fetch filtered records")
            return False

        return True
    except Exception as e:
        logger.error(f"Error in test_fetch_records: {str(e)}", exc_info=True)
        return False


def test_fetch_accounts_by_usernames():
    """Test fetching accounts by usernames"""
    try:
        logger.info("Loading environment variables for username fetch...")
        env_vars = load_env_variables()
        headers = {
            "Authorization": f"Bearer {env_vars['airtable_token']}",
            "Content-Type": "application/json",
        }

        # Get some existing usernames from the table
        logger.info("Fetching records to test with...")
        formula = "RECORD_ID() != ''"  # Get any records
        records = fetch_records_from_airtable(
            env_vars["airtable_accounts_table"], headers, formula
        )
        if not records:
            logger.error("No records found to test with")
            return False

        # Take up to 5 usernames for testing
        test_usernames = {
            record["fields"].get("Username", "").lower()
            for record in records[:5]
            if "Username" in record["fields"]
        }
        logger.debug(f"Test usernames: {test_usernames}")

        logger.info(
            f"Testing fetch_accounts_by_usernames with {len(test_usernames)} usernames..."
        )
        accounts = fetch_accounts_by_usernames(test_usernames, headers)

        if accounts:
            logger.info(f"Successfully fetched {len(accounts)} accounts")
            return True
        else:
            logger.error("Failed to fetch accounts by usernames")
            return False

    except Exception as e:
        logger.error(
            f"Error in test_fetch_accounts_by_usernames: {str(e)}", exc_info=True
        )
        return False


def test_fetch_and_update_accounts():
    """Test fetching and updating accounts"""
    try:
        logger.info("Loading environment variables for update test...")
        env_vars = load_env_variables()
        headers = {
            "Authorization": f"Bearer {env_vars['airtable_token']}",
            "Content-Type": "application/json",
        }

        # Get an existing username from the table for testing
        logger.info("Fetching a record to test with...")
        formula = "RECORD_ID() != ''"  # Get any record
        records = fetch_records_from_airtable(
            env_vars["airtable_accounts_table"], headers, formula
        )
        if not records:
            logger.error("No records found to test with")
            return False

        # Use the first record's username
        test_username = records[0]["fields"].get("Username", "").lower()
        if not test_username:
            logger.error("No valid username found for testing")
            return False

        logger.debug(f"Testing with username: {test_username}")
        test_usernames: Set[str] = {test_username}
        accounts: Dict[str, str] = {}

        logger.info("Testing fetch_and_update_accounts...")
        updated_accounts = fetch_and_update_accounts(test_usernames, headers, accounts)

        if updated_accounts:
            logger.info(
                f"Successfully updated accounts dictionary with {len(updated_accounts)} entries"
            )
            return True
        else:
            logger.error("Failed to update accounts")
            return False

    except Exception as e:
        logger.error(
            f"Error in test_fetch_and_update_accounts: {str(e)}", exc_info=True
        )
        return False


def main():
    """Run all tests"""
    logger.info("Starting Airtable API tests...")

    tests = [
        ("Fetch Records", test_fetch_records),
        ("Fetch Accounts by Usernames", test_fetch_accounts_by_usernames),
        ("Fetch and Update Accounts", test_fetch_and_update_accounts),
    ]

    success_count = 0

    for test_name, test_func in tests:
        logger.info(f"\nRunning test: {test_name}")
        try:
            if test_func():
                logger.info(f"✅ {test_name} passed")
                success_count += 1
            else:
                logger.error(f"❌ {test_name} failed")
        except Exception as e:
            logger.error(
                f"❌ {test_name} failed with exception: {str(e)}", exc_info=True
            )

    logger.info(f"\nTest Summary: {success_count}/{len(tests)} tests passed")


if __name__ == "__main__":
    main()
