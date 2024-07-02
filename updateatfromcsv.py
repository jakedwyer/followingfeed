import csv
import requests
import json
import os
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from a .env file
load_dotenv()
logging.info("Environment variables loaded.")

# Airtable API configuration using environment variables
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

# Load Airtable schema
with open('airtableschema.json', 'r') as schema_file:
    airtable_schema = json.load(schema_file)
logging.info("Airtable schema loaded.")

# Airtable API URL
AIRTABLE_API_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Accounts"

# Function to retrieve all records from Airtable
def get_all_airtable_records():
    records = []
    offset = ""
    while True:
        url = f"{AIRTABLE_API_URL}?offset={offset}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            records.extend(data.get('records', []))
            offset = data.get('offset', "")
            if not offset:
                break
        else:
            logging.error(f"Failed to retrieve records. Response: {response.text}")
            break
    logging.info(f"Retrieved {len(records)} records from Airtable.")
    return records

# Function to batch update records in Airtable
def batch_update_airtable_records(records):
    url = AIRTABLE_API_URL
    data = {
        "records": records
    }
    response = requests.patch(url, headers=HEADERS, data=json.dumps(data))
    if response.status_code == 200:
        logging.info(f"Successfully updated {len(records)} records in Airtable.")
    else:
        logging.error(f"Failed to perform batch update. Response: {response.text}")

# Retrieve all records from Airtable
airtable_records = get_all_airtable_records()
airtable_records_map = {record['fields'].get('Username', '').lower(): record for record in airtable_records}
logging.info(f"Created map of {len(airtable_records_map)} Airtable records.")

# Read joined_accounts.csv and prepare records for batch update
records_to_update = []
with open('joined_accounts.csv', 'r') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    headers = csv_reader.fieldnames
    logging.info(f"CSV Headers: {headers}")
    for row in csv_reader:
        username = row['username'].lower()
        airtable_record = airtable_records_map.get(username)
        if airtable_record and not airtable_record['fields'].get('Account ID'):
            record_id = airtable_record['id']
            fields = {
                "Description": row['description'],
                "Account ID": row['id'],
                "Full Name": row['name'],
                "Followers Count": int(row['followers_count']),
                "Listed Count": int(row['listed_count']),
                "Created At": row['created_at'],
            }
            records_to_update.append({"id": record_id, "fields": fields})

            # Perform batch update in chunks of 10
            if len(records_to_update) == 10:
                batch_update_airtable_records(records_to_update)
                records_to_update = []

# Update any remaining records
if records_to_update:
    batch_update_airtable_records(records_to_update)

logging.info("Script execution completed.")