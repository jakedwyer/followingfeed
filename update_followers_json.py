import requests
import json
import time
import os

# Configuration
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_TOKEN")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
TABLE_NAME = "Followers"  # Replace with your Table Name
JSON_FILE_PATH = "user_details.json"  # Path to your JSON file
FIELDS_TO_UPDATE = ["Full Name", "Description"]  # Fields you want to update

# Airtable API setup
AIRTABLE_ENDPOINT = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}


def load_json_data(json_path):
    """Load JSON data from a file."""
    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data


def get_all_records():
    """Retrieve all records from the Airtable table."""
    records = []
    params = {"pageSize": 100}
    while True:
        response = requests.get(AIRTABLE_ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            print(f"Error fetching records: {response.status_code} - {response.text}")
            break
        data = response.json()
        records.extend(data.get("records", []))
        if "offset" in data:
            params["offset"] = data["offset"]
            time.sleep(0.2)  # To respect rate limits
        else:
            break
    return records


def update_record(record_id, fields):
    """Update a single Airtable record."""
    url = f"{AIRTABLE_ENDPOINT}/{record_id}"
    payload = {"fields": fields}
    response = requests.patch(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 201]:
        print(f"Successfully updated record ID: {record_id}")
    else:
        print(
            f"Failed to update record ID: {record_id} - {response.status_code} - {response.text}"
        )


def main():
    # Load JSON data
    json_data = load_json_data(JSON_FILE_PATH)

    # Create a case-insensitive mapping from Account ID to its data for quick lookup
    account_data_map = {
        v["data"]["Account ID"].lower(): v["data"] for k, v in json_data.items()
    }

    # Fetch all Airtable records
    airtable_records = get_all_records()
    print(f"Total records fetched from Airtable: {len(airtable_records)}")

    # Iterate through Airtable records
    for record in airtable_records:
        record_id = record["id"]
        fields = record.get("fields", {})
        account_id = fields.get("Username")  # Adjust this field name if different

        if not account_id:
            print(f"Record ID {record_id} does not have a 'Username'. Skipping.")
            continue

        # Check if Account ID exists in JSON data (case-insensitive)
        if account_id.lower() not in account_data_map:
            print(f"Username '{account_id}' not found in JSON data. Skipping.")
            continue

        # Get corresponding data from JSON
        json_fields = account_data_map[account_id.lower()]

        # Prepare fields to update
        fields_to_update = {}
        for field in FIELDS_TO_UPDATE:
            if field not in fields or not fields[field]:
                # Get value from JSON
                value = json_fields.get(field)
                if value:
                    fields_to_update[field] = value

        if fields_to_update:
            print(f"Updating Record ID {record_id} with fields: {fields_to_update}")
            update_record(record_id, fields_to_update)
            time.sleep(0.2)  # To respect rate limits
        else:
            print(f"No updates required for Record ID {record_id}")


if __name__ == "__main__":
    main()
