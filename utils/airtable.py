import logging
import requests
import json
from typing import Dict, List, Any, Optional
from utils.config import load_env_variables
from datetime import datetime

logger = logging.getLogger(__name__)

# Load environment variables
env_vars = load_env_variables()

# Use environment variables
BASE_ID = env_vars["airtable_base_id"]
AIRTABLE_API_KEY = env_vars["airtable_token"]
AIRTABLE_ACCOUNTS_TABLE = env_vars["airtable_accounts_table"]


def airtable_api_request(
    method, table_id, headers, data=None, record_id=None, params=None
):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"
    if record_id:
        url += f"/{record_id}"

    response = requests.request(method, url, headers=headers, json=data, params=params)

    if response.status_code in [200, 201]:
        return response.json()
    else:
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
    records = []
    offset = None

    while True:
        params = {"offset": offset} if offset else {}
        if formula:
            params["filterByFormula"] = formula
        data = airtable_api_request("GET", table_id, headers, params=params)
        if data:
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break
        else:
            return []
    return records


def post_airtable_records(records, table_id, headers):
    for i in range(0, len(records), 10):
        batch = records[i : i + 10]
        airtable_api_request("POST", table_id, headers, data={"records": batch})


def update_followers_field(follow_record_id, follower_record_id, headers):
    data = airtable_api_request(
        "GET", AIRTABLE_ACCOUNTS_TABLE, headers, record_id=follow_record_id
    )
    if data:
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
    else:
        logger.error(
            f"Failed to retrieve Account record {follow_record_id} for updating Followers field."
        )


def update_airtable_records(records, table_id, headers):
    formatted_records = []
    for record in records:
        username = record["fields"].get("Username", "").lower()
        with open("user_details.json", "r") as f:
            user_details = json.load(f)
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

        # Filter out records with no enriched fields
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
                # Ensure the date is in the correct format
                try:
                    datetime.strptime(new_value, "%Y-%m-%d")
                    formatted_data[airtable_field] = new_value
                except ValueError:
                    logger.warning(f"Invalid date format for {username}: {new_value}")
            else:
                formatted_data[airtable_field] = new_value

    if formatted_data:
        return {"id": record_id, "fields": formatted_data}
    else:
        logger.debug(f"No updateable data for {username}")
        return None


def update_airtable(records_to_update: List[Dict[str, Any]]) -> None:
    if not records_to_update:
        logger.debug("No records to update.")
        return

    endpoint = f"https://api.airtable.com/v0/{BASE_ID}/{AIRTABLE_ACCOUNTS_TABLE}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {"records": records_to_update, "typecast": True}

    response = requests.patch(endpoint, json=data, headers=headers)
    if response.status_code == 200:
        logger.info(
            f"Successfully updated {len(records_to_update)} records in Airtable."
        )
    else:
        logger.error(
            f"Failed to update Airtable: {response.status_code}, {response.text}"
        )


def delete_airtable_record(record_id: str) -> None:
    endpoint = (
        f"https://api.airtable.com/v0/{BASE_ID}/{AIRTABLE_ACCOUNTS_TABLE}/{record_id}"
    )
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.delete(endpoint, headers=headers)
        response.raise_for_status()
        logger.info(f"Successfully deleted record {record_id} from Airtable.")
    except requests.exceptions.HTTPError as http_err:
        logger.error(
            f"HTTP error occurred while deleting record {record_id}: {http_err}"
        )
    except Exception as err:
        logger.error(f"An error occurred while deleting record {record_id}: {err}")
