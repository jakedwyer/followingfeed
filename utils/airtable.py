import logging
import requests

BASE_ID = 'appYCZWcmNBXB2uUS'
import logging
import requests

BASE_ID = 'appYCZWcmNBXB2uUS'

def airtable_api_request(method, table_id, headers, data=None, record_id=None, params=None):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"
    if record_id:
        url += f"/{record_id}"
    
    response = requests.request(method, url, headers=headers, json=data, params=params)
    
    if response.status_code in [200, 201]:
        return response.json()
    else:
        logging.error(f"Failed to {method} records in {table_id}. Status code: {response.status_code}")
        logging.error(f"Response content: {response.content}")
        logging.error(f"Request URL: {url}")
        logging.error(f"Request headers: {headers}")
        logging.error(f"Request data: {data}")
        return None

def fetch_records_from_airtable(table_id, headers):
    records = []
    offset = None

    while True:
        params = {'offset': offset} if offset else {}
        data = airtable_api_request('GET', table_id, headers, params=params)
        if data:
            records.extend(data.get('records', []))
            offset = data.get('offset')
            if not offset:
                break
        else:
            return []
    return records

def post_airtable_records(records, table_id, headers):
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        airtable_api_request('POST', table_id, headers, data={"records": batch})

def update_followers_field(follow_record_id, follower_record_id, headers):
    data = airtable_api_request('GET', 'tblJCXhcrCxDUJR3F', headers, record_id=follow_record_id)
    if data:
        account_data = data.get('fields', {})
        existing_followers = account_data.get('Followers', [])
        if follower_record_id not in existing_followers:
            existing_followers.append(follower_record_id)
            update_payload = {'fields': {'Followers': existing_followers}}
            airtable_api_request('PATCH', 'tblJCXhcrCxDUJR3F', headers, data=update_payload, record_id=follow_record_id)

def update_airtable_records(records, table_id, headers):
    for i in range(0, len(records), 10):
        batch = records[i:i+10]
        formatted_records = [{"id": record["id"], "fields": record["fields"]} for record in batch]
        response = airtable_api_request('PATCH', table_id, headers, data={"records": formatted_records})
        if response is None:
            logging.error(f"Failed to update batch {i//10 + 1}")
        else:
            logging.info(f"Successfully updated batch {i//10 + 1}")
