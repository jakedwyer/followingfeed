import logging
import requests
import json
from typing import Dict, List, Any, Optional, Set
from utils.config import load_env_variables
from datetime import datetime
import time
import os
import pickle

logger = logging.getLogger(__name__)

# Load environment variables once at module level
env_vars = load_env_variables()
BASE_ID = env_vars["airtable_base_id"]
AIRTABLE_API_KEY = env_vars["airtable_token"]
AIRTABLE_ACCOUNTS_TABLE = env_vars["airtable_accounts_table"]
AIRTABLE_FOLLOWERS_TABLE = env_vars["airtable_followers_table"]
# Common headers used across functions
AIRTABLE_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}

# Cache settings
CACHE_DIR = ".cache"
ACCOUNTS_CACHE_FILE = os.path.join(CACHE_DIR, "accounts_cache.pkl")
CACHE_EXPIRY_HOURS = 24  # Cache expires after 24 hours


def load_cached_accounts() -> Optional[Dict[str, Dict]]:
    """Load cached accounts if available and not expired."""
    try:
        if not os.path.exists(ACCOUNTS_CACHE_FILE):
            return None

        # Check if cache is expired
        cache_mtime = os.path.getmtime(ACCOUNTS_CACHE_FILE)
        if (time.time() - cache_mtime) > (CACHE_EXPIRY_HOURS * 3600):
            logger.info("Accounts cache has expired")
            return None

        with open(ACCOUNTS_CACHE_FILE, "rb") as f:
            cache = pickle.load(f)
            logger.info(f"Loaded {len(cache)} accounts from cache")
            return cache
    except Exception as e:
        logger.error(f"Error loading accounts cache: {str(e)}")
        return None


def save_accounts_cache(accounts: Dict[str, Dict]) -> None:
    """Save accounts to cache."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(ACCOUNTS_CACHE_FILE, "wb") as f:
            pickle.dump(accounts, f)
        logger.info(f"Saved {len(accounts)} accounts to cache")
    except Exception as e:
        logger.error(f"Error saving accounts cache: {str(e)}")


def fetch_accounts_by_usernames(
    usernames: Set[str], headers: Dict[str, str]
) -> Dict[str, Dict]:
    """Fetch only the accounts that match the given usernames."""
    normalized_usernames = {username.lower() for username in usernames}

    # First check cache
    cached_accounts = load_cached_accounts() or {}

    # Filter out usernames we already have in cache
    missing_usernames = {
        username for username in normalized_usernames if username not in cached_accounts
    }

    if not missing_usernames:
        logger.info("All requested accounts found in cache")
        return {
            username: cached_accounts[username]
            for username in normalized_usernames
            if username in cached_accounts
        }

    # Fetch only missing accounts from Airtable
    formula = " OR ".join(
        [f"LOWER({{Username}}) = '{username}'" for username in missing_usernames]
    )
    if formula:
        formula = f"OR({formula})"

    new_accounts = {}
    records = fetch_records_from_airtable(AIRTABLE_ACCOUNTS_TABLE, headers, formula)

    for record in records:
        username = record["fields"].get("Username", "").lower()
        if username:
            new_accounts[username] = record
            cached_accounts[username] = record

    # Update cache with new accounts
    save_accounts_cache(cached_accounts)

    # Return only the requested accounts
    return {
        username: cached_accounts[username]
        for username in normalized_usernames
        if username in cached_accounts
    }


def fetch_and_update_accounts(
    usernames: Set[str], headers: Dict[str, str], accounts: Dict[str, str]
) -> Dict[str, str]:
    """
    Fetch or create accounts using Airtable's upsert functionality.
    Now with caching support.
    """
    normalized_usernames = {normalize_username(username) for username in usernames}

    # First, try to get accounts from cache/Airtable
    existing_accounts = fetch_accounts_by_usernames(normalized_usernames, headers)

    # Update our accounts dictionary with what we found
    for username, record in existing_accounts.items():
        accounts[username] = record["id"]

    # Determine which accounts we need to create
    missing_usernames = normalized_usernames - set(existing_accounts.keys())

    if missing_usernames:
        # Prepare records for upsert
        records_to_upsert = [
            {
                "fields": {
                    "Username": uname,
                }
            }
            for uname in missing_usernames
        ]

        # Process in batches of 10 as per Airtable's limit
        for i in range(0, len(records_to_upsert), 10):
            batch = records_to_upsert[i : i + 10]
            try:
                response = requests.post(
                    f"https://api.airtable.com/v0/{BASE_ID}/{AIRTABLE_ACCOUNTS_TABLE}",
                    headers=headers,
                    json={
                        "performUpsert": {"fieldsToMergeOn": ["Username"]},
                        "records": batch,
                    },
                )
                response.raise_for_status()
                result = response.json()

                # Update our accounts dictionary and cache with created/updated records
                new_records = {}
                for record in result.get("records", []):
                    username = normalize_username(record["fields"].get("Username", ""))
                    if username:
                        accounts[username] = record["id"]
                        new_records[username] = record

                # Update cache with new records
                cached_accounts = load_cached_accounts() or {}
                cached_accounts.update(new_records)
                save_accounts_cache(cached_accounts)

                # Log the results
                created = len(result.get("createdRecords", []))
                updated = len(result.get("updatedRecords", []))
                if created or updated:
                    logging.info(
                        f"Batch processed: {created} accounts created, {updated} accounts updated"
                    )

            except requests.HTTPError as e:
                logging.error(f"Failed to upsert batch: {str(e)}")
                logging.debug(f"Response content: {e.response.text}")
                logging.debug(f"Failed batch: {batch}")

            # Rate limiting protection
            time.sleep(0.2)

    return accounts


def airtable_api_request(
    method, table_id, headers, data=None, record_id=None, params=None
):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"
    if record_id:
        url += f"/{record_id}"

    response = requests.request(method, url, headers=headers, json=data, params=params)

    if response.status_code in [200, 201]:
        return response.json()

    logger.error(
        f"Failed to {method} records in {table_id}. Status code: {response.status_code}"
    )
    logger.error(f"Response content: {response.content}")
    logger.error(f"Request URL: {url}")
    logger.error(f"Request headers: {headers}")
    logger.error(f"Request data: {data}")
    return None


def fetch_records_from_airtable(
    table_id: str, headers: Dict[str, str], formula: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetch records from Airtable with support for pagination and filtering.

    Args:
        table_id: The ID or name of the table to fetch from
        headers: Request headers including authorization
        formula: Optional filterByFormula string for Airtable API

    Returns:
        List of record dictionaries from Airtable
    """
    records = []
    offset = None

    while True:
        try:
            params = {"offset": offset} if offset else {}
            if formula:
                params["filterByFormula"] = formula

            data = airtable_api_request("GET", table_id, headers, params=params)
            if not data:
                logger.error(f"Failed to fetch records from table {table_id}")
                return []

            records.extend(data.get("records", []))
            logger.debug(
                f"Fetched {len(data.get('records', []))} records from {table_id}"
            )

            offset = data.get("offset")
            if not offset:
                break

            # Rate limiting protection
            time.sleep(0.2)

        except Exception as e:
            logger.error(
                f"Error fetching records from {table_id}: {str(e)}", exc_info=True
            )
            return []

    logger.info(f"Total records fetched from {table_id}: {len(records)}")
    return records


def post_airtable_records(records, table_id, headers):
    for i in range(0, len(records), 10):
        batch = records[i : i + 10]
        airtable_api_request("POST", table_id, headers, data={"records": batch})


def update_followers_field(follow_record_id, follower_record_id, headers):
    data = airtable_api_request(
        "GET", AIRTABLE_ACCOUNTS_TABLE, headers, record_id=follow_record_id
    )
    if not data:
        logger.error(
            f"Failed to retrieve Account record {follow_record_id} for updating Followers field."
        )
        return

    followers = data.get("fields", {}).get("Followers", [])
    if follower_record_id not in followers:
        followers.append(follower_record_id)
        update_payload = {"fields": {"Followers": followers}}
        airtable_api_request(
            "PATCH",
            AIRTABLE_ACCOUNTS_TABLE,
            headers,
            data=update_payload,
            record_id=follow_record_id,
        )
        logger.debug(
            f"Updated Followers field for Account ID {follow_record_id} with Follower ID {follower_record_id}."
        )


def update_airtable_records(records, table_id, headers):
    formatted_records = []

    # Load user details once
    with open("user_details.json", "r") as f:
        user_details = json.load(f)

    for record in records:
        username = record["fields"].get("Username", "").lower()
        user_data = user_details.get(username, {}).get("data", {})

        formatted_record = {
            "id": record["id"],
            "fields": {
                "Account ID": user_data.get("Account ID", ""),
                "Full Name": user_data.get("Full Name", ""),
                "Description": user_data.get("Description", ""),
                "Location": user_data.get("Location", ""),
                "Website": user_data.get("Website", ""),
                "Created At": user_data.get("Created At", ""),
                "Followers Count": user_data.get("Followers Count", 0),
                "Following Count": user_data.get("Following Count", 0),
                "Tweet Count": user_data.get("Tweet Count", 0),
                "Listed Count": user_data.get("Listed Count", 0),
                "Like Count": user_data.get("Like Count", 0),
            },
        }

        if any(value for value in formatted_record["fields"].values()):
            formatted_records.append(formatted_record)

    for i in range(0, len(formatted_records), 10):
        batch = formatted_records[i : i + 10]
        response = airtable_api_request(
            "PATCH", table_id, headers, data={"records": batch}
        )
        if response is None:
            logger.error(f"Failed to update batch {i//10 + 1}")
        else:
            logger.info(f"Successfully updated batch {i//10 + 1}")


def prepare_update_record(
    record_id: str, username: str, data: Dict[str, Any], existing_fields: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    formatted_data = {}
    field_mapping = {
        "Username": "Username",
        "Full Name": "Full Name",
        "Description": "Description",
        "Location": "Location",
        "Website": "Website",
        "Created At": "Created At",
        "Followers Count": "Followers Count",
        "Following Count": "Following Count",
        "Tweet Count": "Tweet Count",
        "Listed Count": "Listed Count",
        "Account ID": "Account ID",
    }

    for data_field, airtable_field in field_mapping.items():
        new_value = data.get(data_field)
        if new_value and new_value != existing_fields.get(airtable_field):
            if airtable_field == "Created At":
                try:
                    datetime.strptime(new_value, "%Y-%m-%d")
                    formatted_data[airtable_field] = new_value
                except ValueError:
                    logger.warning(f"Invalid date format for {username}: {new_value}")
            else:
                formatted_data[airtable_field] = new_value

    if not formatted_data:
        logger.debug(f"No updateable data for {username}")
        return None

    return {"id": record_id, "fields": formatted_data}


def update_airtable(records_to_update: List[Dict], headers: Dict[str, str]) -> bool:
    """
    Bulk update records in Airtable in batches of 10.

    Args:
        records_to_update: List of record dictionaries to update.
        headers: HTTP headers with authorization.

    Returns:
        True if all batches are successfully updated, False otherwise.
    """
    if not records_to_update:
        logging.info("No records to update.")
        return True

    all_successful = True
    for i in range(0, len(records_to_update), 10):
        batch = records_to_update[i : i + 10]
        try:
            response = requests.patch(
                f"https://api.airtable.com/v0/{BASE_ID}/{AIRTABLE_ACCOUNTS_TABLE}",
                headers=headers,
                json={"records": batch},
            )
            response.raise_for_status()
            batch_response = response.json()

            updated = batch_response.get("updatedRecords", [])
            created = batch_response.get("createdRecords", [])
            errors = batch_response.get("errors", [])

            logging.info(
                f"Batch {i//10 +1}: Successfully updated {len(updated)} records, created {len(created)} records."
            )
            if errors:
                logging.error(f"Batch {i//10 +1}: Encountered {len(errors)} errors.")
                all_successful = False
        except requests.HTTPError as e:
            logging.error(
                f"Failed to update batch {i//10 +1}: {e.response.status_code}, {e.response.text}"
            )
            all_successful = False
        except Exception as e:
            logging.error(
                f"Unexpected error updating batch {i//10 +1}: {str(e)}", exc_info=True
            )
            all_successful = False
    return all_successful


def delete_airtable_record(record_id: str) -> None:
    endpoint = (
        f"https://api.airtable.com/v0/{BASE_ID}/{AIRTABLE_ACCOUNTS_TABLE}/{record_id}"
    )

    try:
        response = requests.delete(endpoint, headers=AIRTABLE_HEADERS)
        response.raise_for_status()
        logger.info(f"Successfully deleted record {record_id} from Airtable.")
    except requests.exceptions.HTTPError as http_err:
        logger.error(
            f"HTTP error occurred while deleting record {record_id}: {http_err}"
        )
    except Exception as err:
        logger.error(f"An error occurred while deleting record {record_id}: {err}")


def normalize_username(username: str) -> str:
    return username.strip().lower()


def batch_request(
    url: str, headers: Dict[str, str], records: List[Dict], method
) -> List[Dict]:
    successful_records = []
    BATCH_SIZE = 10
    RATE_LIMIT_DELAY = 0.2  # 200ms between requests

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        try:
            response = method(url, headers=headers, json={"records": batch})
            response.raise_for_status()
            successful_records.extend(response.json().get("records", []))
            logging.debug(f"Successfully processed batch of {len(batch)} records.")
            time.sleep(RATE_LIMIT_DELAY)
        except requests.HTTPError as e:
            logging.error(
                f"Failed to process batch at index {i}: {e.response.status_code}"
            )
            logging.debug(f"Response content: {e.response.text}")
            logging.debug(f"Failed batch: {batch}")

    return successful_records


def fetch_existing_follows(
    record_id: str, headers: Dict[str, str], record_id_to_username: Dict[str, str]
) -> Set[str]:
    """
    Fetch existing follows for a given follower.

    Args:
        record_id: The record ID of the Follower in Airtable
        headers: HTTP headers with authorization
        record_id_to_username: Dictionary mapping record IDs to usernames

    Returns:
        Set of usernames that the follower is currently following
    """
    try:
        response = requests.get(
            f"https://api.airtable.com/v0/{BASE_ID}/{AIRTABLE_FOLLOWERS_TABLE}/{record_id}",
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
        # Remove empty strings that might have been added due to missing mappings
        existing_usernames.discard("")
        logger.debug(
            f"Found {len(existing_usernames)} existing follows for record {record_id}"
        )
        return existing_usernames
    except requests.HTTPError as e:
        logger.error(
            f"Failed to fetch existing follows for record {record_id}: {e.response.text}"
        )
        return set()
    except Exception as e:
        logger.error(
            f"Unexpected error fetching follows for record {record_id}: {str(e)}"
        )
        return set()
