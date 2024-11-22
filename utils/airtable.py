import logging
import requests
from typing import Dict, List, Set, Any, Optional
from utils.config import load_env_variables
from utils.helpers import normalize_username, batch_request
import time

logger = logging.getLogger(__name__)

# Load environment variables once at module level
env_vars = load_env_variables()
BASE_ID = env_vars["airtable_base_id"]
AIRTABLE_API_KEY = env_vars["airtable_token"]
AIRTABLE_ACCOUNTS_TABLE = env_vars["airtable_accounts_table"]
AIRTABLE_FOLLOWERS_TABLE = env_vars["airtable_followers_table"]


def airtable_api_request(
    method: str,
    table_id: str,
    headers: Dict[str, str],
    data: Optional[Dict] = None,
    record_id: Optional[str] = None,
    params: Optional[Dict] = None,
) -> Optional[Dict]:
    """
    Make a request to the Airtable API.

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE)
        table_id: The ID of the table to interact with
        headers: Request headers including authorization
        data: Optional data payload for POST/PATCH requests
        record_id: Optional record ID for single-record operations
        params: Optional query parameters

    Returns:
        Optional[Dict]: The JSON response from Airtable or None if request failed
    """
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"
    if record_id:
        url += f"/{record_id}"

    try:
        response = requests.request(
            method, url, headers=headers, json=data, params=params
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        logger.error(
            f"Failed to {method} records in {table_id}. Status code: {e.response.status_code}"
        )
        logger.error(f"Response content: {e.response.content}")
        logger.error(f"Request URL: {url}")
        logger.error(f"Request headers: {headers}")
        logger.error(f"Request data: {data}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in airtable_api_request: {str(e)}")
        return None


def fetch_records_from_airtable(
    table_id: str, headers: Dict[str, str], formula: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetch records from Airtable with support for pagination and filtering."""
    records = []
    offset = None
    base_url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"

    while True:
        params = {"offset": offset} if offset else {}
        if formula:
            params["filterByFormula"] = formula

        try:
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            records.extend(data.get("records", []))
            offset = data.get("offset")

            if not offset:
                break

        except Exception as e:
            logger.error(f"Error fetching records: {str(e)}")
            break

    return records


def update_airtable_followers(
    follower_record_id: str, account_ids: List[str], headers: Dict[str, str]
) -> bool:
    """Update the Followers table with the new list of account IDs."""
    follower_update = {"id": follower_record_id, "fields": {"Account": account_ids}}
    try:
        response = requests.patch(
            f"https://api.airtable.com/v0/{BASE_ID}/{AIRTABLE_FOLLOWERS_TABLE}",
            headers=headers,
            json={"records": [follower_update]},
        )
        response.raise_for_status()
        logger.info(
            f"Successfully updated follower {follower_record_id} with {len(account_ids)} accounts."
        )
        return True
    except requests.HTTPError as e:
        logger.error(
            f"Failed to update follower {follower_record_id}: {e.response.text}"
        )
        return False


def fetch_existing_follows(
    record_id: str, headers: Dict[str, str], record_id_to_username: Dict[str, str]
) -> Set[str]:
    """Fetch existing follows for a given follower."""
    try:
        response = requests.get(
            f"https://api.airtable.com/v0/{BASE_ID}/{AIRTABLE_FOLLOWERS_TABLE}/{record_id}",
            headers=headers,
        )
        response.raise_for_status()
        record = response.json()
        existing_account_ids = record["fields"].get("Account", [])
        existing_usernames = {
            record_id_to_username.get(acc_id, "").lower()
            for acc_id in existing_account_ids
        }
        existing_usernames.discard("")
        return existing_usernames
    except Exception as e:
        logger.error(f"Error fetching follows: {str(e)}")
        return set()


def fetch_and_update_accounts(
    usernames: Set[str], headers: Dict[str, str], accounts: Dict[str, str]
) -> Dict[str, str]:
    """Fetch or create accounts for usernames."""
    normalized_usernames = {normalize_username(username) for username in usernames}

    # Fetch existing accounts
    formula = (
        "OR("
        + ",".join(
            [f"LOWER({{Username}}) = '{username}'" for username in normalized_usernames]
        )
        + ")"
    )
    existing_records = fetch_records_from_airtable(
        AIRTABLE_ACCOUNTS_TABLE, headers, formula
    )

    for record in existing_records:
        username = normalize_username(record["fields"].get("Username", ""))
        if username:
            accounts[username] = record["id"]

    # Create new accounts
    new_usernames = normalized_usernames - set(accounts.keys())
    if new_usernames:
        new_entries = [{"fields": {"Username": username}} for username in new_usernames]
        created_records = batch_request(
            f"https://api.airtable.com/v0/{BASE_ID}/{AIRTABLE_ACCOUNTS_TABLE}",
            headers,
            new_entries,
            requests.post,
        )

        for record in created_records:
            username = normalize_username(record["fields"].get("Username", ""))
            if username:
                accounts[username] = record["id"]

    return accounts


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

            updated = batch_response.get("records", [])
            logging.info(
                f"Batch {i//10 + 1}: Successfully updated {len(updated)} records."
            )
        except requests.HTTPError as e:
            logging.error(
                f"Failed to update batch {i//10 + 1}: {e.response.status_code}, {e.response.text}"
            )
            all_successful = False
        except Exception as e:
            logging.error(
                f"Unexpected error updating batch {i//10 + 1}: {str(e)}", exc_info=True
            )
            all_successful = False

        # Rate limiting protection
        time.sleep(0.2)  # 200ms between requests

    return all_successful


def delete_airtable_record(record_id: str) -> bool:
    """
    Delete a record from Airtable by ID.

    Args:
        record_id: The ID of the record to delete.

    Returns:
        True if deletion was successful, False otherwise.
    """
    try:
        response = requests.delete(
            f"https://api.airtable.com/v0/{BASE_ID}/{AIRTABLE_ACCOUNTS_TABLE}/{record_id}",
            headers={"Authorization": f"Bearer {AIRTABLE_API_KEY}"},
        )
        response.raise_for_status()
        logger.info(f"Successfully deleted record {record_id}")
        return True
    except requests.HTTPError as e:
        logger.error(f"Failed to delete record {record_id}: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting record {record_id}: {str(e)}")
        return False


def post_airtable_records(
    records: List[Dict], table_id: str, headers: Dict[str, str]
) -> List[Dict]:
    """
    Post records to Airtable in batches.

    Args:
        records: List of records to post
        table_id: The ID of the table to post to
        headers: Headers containing authorization

    Returns:
        List of created records
    """
    results = []
    for i in range(0, len(records), 10):
        batch = records[i : i + 10]
        try:
            response = requests.post(
                f"https://api.airtable.com/v0/{BASE_ID}/{table_id}",
                headers=headers,
                json={"records": batch},
            )
            response.raise_for_status()
            results.extend(response.json().get("records", []))
            logger.debug(f"Posted {len(batch)} entries to {table_id}")
            time.sleep(0.2)  # Rate limiting protection
        except requests.HTTPError as e:
            logger.error(
                f"Failed to post entries to {table_id}. Status code: {e.response.status_code}"
            )
            logger.debug(f"Response content: {e.response.content.decode('utf-8')}")
    return results


def update_airtable_records(
    records: List[Dict], table_id: str, headers: Dict[str, str]
) -> bool:
    """
    Update multiple records in Airtable.

    Args:
        records: List of records to update
        table_id: The ID of the table to update
        headers: Headers containing authorization

    Returns:
        bool: True if all updates were successful
    """
    formatted_records = []

    for record in records:
        if "id" not in record:
            logger.warning(f"Record missing ID, skipping: {record}")
            continue

        formatted_record = {"id": record["id"], "fields": record.get("fields", {})}
        formatted_records.append(formatted_record)

    if not formatted_records:
        logger.info("No valid records to update")
        return True

    success = True
    for i in range(0, len(formatted_records), 10):
        batch = formatted_records[i : i + 10]
        try:
            response = requests.patch(
                f"https://api.airtable.com/v0/{BASE_ID}/{table_id}",
                headers=headers,
                json={"records": batch},
            )
            response.raise_for_status()
            logger.info(f"Successfully updated batch {i//10 + 1}")
        except requests.HTTPError as e:
            logger.error(f"Failed to update batch {i//10 + 1}: {e.response.text}")
            success = False
        except Exception as e:
            logger.error(f"Unexpected error updating batch {i//10 + 1}: {str(e)}")
            success = False

        # Rate limiting protection
        time.sleep(0.2)

    return success
