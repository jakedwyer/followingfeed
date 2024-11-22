import logging
from typing import Dict, List, Set, Any, Optional
from datetime import datetime
import requests
import time

logger = logging.getLogger(__name__)


def normalize_username(username: str) -> str:
    """
    Normalize the username to ensure consistency.
    - Lowercase
    - Strip leading/trailing whitespace
    """
    return username.strip().lower()


def batch_request(
    url: str, headers: Dict[str, str], records: List[Dict], method
) -> List[Dict]:
    """
    Make batched requests to an API endpoint.
    """
    results = []
    BATCH_SIZE = 10
    RATE_LIMIT_DELAY = 0.2  # 200ms between requests

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + 10]
        try:
            response = method(url, headers=headers, json={"records": batch})
            response.raise_for_status()
            results.extend(response.json().get("records", []))
            logger.debug(f"Successfully processed batch of {len(batch)} records.")
            time.sleep(RATE_LIMIT_DELAY)
        except requests.HTTPError as e:
            logger.error(
                f"Failed to process batch at index {i}: {e.response.status_code}"
            )
            logger.debug(f"Response content: {e.response.text}")
            logger.debug(f"Failed batch: {batch}")

    return results


def prepare_update_record(
    record_id: str, username: str, data: Dict[str, Any], existing_fields: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Prepare the payload for updating a record in Airtable.
    """
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
