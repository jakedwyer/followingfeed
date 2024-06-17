import requests
import logging

def airtable_api_request(method, table_id, headers, data=None, record_id=None, params=None):
    """Generalized Airtable API request function."""
    url = f"https://api.airtable.com/v0/appYCZWcmNBXB2uUS/{table_id}"
    if record_id:
        url += f"/{record_id}"
    try:
        response = requests.request(method, url, headers=headers, json=data, params=params)
        response.raise_for_status()
        if response.status_code in [200, 201, 204]:  # 204 No Content for DELETE
            return response.json() if response.content else {}
        else:
            logging.error(f"Unexpected status code {response.status_code} when {method} records in {table_id}.")
            logging.error(f"Response content: {response.content}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error occurred when {method} records in {table_id}: {e}")
        return None

def fetch_records_with_empty_account_id(table_id, headers):
    """Fetch records from Airtable where the Account ID is empty."""
    records = []
    offset = None
    while True:
        params = {'offset': offset, 'filterByFormula': "NOT({Account ID})"} if offset else {'filterByFormula': "NOT({Account ID})"}
        data = airtable_api_request('GET', table_id, headers, params=params)
        if data:
            records.extend(data.get('records', []))
            offset = data.get('offset')
            if not offset:
                break
        else:
            logging.error(f"Failed to fetch records with empty Account ID from {table_id}.")
            break
    return records

def update_airtable_records(records, table_id, headers):
    """Update records in a specified Airtable table."""
    for i in range(0, len(records), 10):
        batch = [{"id": record['id'], "fields": record['fields']} for record in records[i:i+10]]
        if not airtable_api_request('PATCH', table_id, headers, data={"records": batch}):
            logging.error(f"Failed to update records in {table_id}.")

def get_user_details(username, headers):
    """Fetch detailed information of a specific Twitter user."""
    user_fields = "id,name,username,created_at,description,public_metrics,verified"
    url = f"https://api.twitter.com/2/users/by/username/{username}?user.fields={user_fields}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            logging.error("Rate limit exceeded. Stopping the script.")
            raise Exception("Rate limit exceeded")
        else:
            logging.error(f"Unexpected status code {response.status_code} when retrieving user details for {username}.")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error occurred when retrieving user details for {username}: {e}")
        return None

def delete_airtable_record(record_id, table_id, headers):
    """Delete a record from a specified Airtable table."""
    airtable_api_request('DELETE', table_id, headers, record_id=record_id)