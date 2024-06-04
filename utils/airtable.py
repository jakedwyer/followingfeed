import pandas as pd
from pyairtable import Api
from pyairtable.formulas import match
import os
import numpy as np
from dotenv import load_dotenv
import logging
from time import sleep
from requests.exceptions import HTTPError
import json

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()
logging.info("Environment variables loaded.")

# Get Airtable API key and base ID from environment
ACCESS_TOKEN = os.getenv('AIRTABLE_TOKEN')
BASE_ID = os.getenv('AIRTABLE_BASE_ID')

# Initialize Airtable API
api = Api(ACCESS_TOKEN)
logging.info("Airtable API initialized.")

# Table names or IDs
ACCOUNTS_TABLE_ID = 'tblJCXhcrCxDUJR3F'
FOLLOWERS_TABLE_ID = 'tbl7bEfNVnCEQvUkT'

# Get table instances
accounts_table = api.table(BASE_ID, ACCOUNTS_TABLE_ID)
followers_table = api.table(BASE_ID, FOLLOWERS_TABLE_ID)
logging.info("Table instances retrieved.")

def load_csv_files():
    logging.info("Loading CSV files...")
    target_accounts_df = pd.read_csv('/root/followfeed/joined_accounts.csv')
    list_members_df = pd.read_csv('/root/followfeed/list_members.csv')

    username_to_id = dict(zip(list_members_df['Username'], list_members_df['ID']))

    target_accounts_df.replace([np.inf, -np.inf], None, inplace=True)
    target_accounts_df.where(pd.notnull(target_accounts_df), None, inplace=True)

    logging.info("CSV files loaded successfully.")
    return target_accounts_df, username_to_id

def retry_request(func, *args, retries=3, **kwargs):
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except HTTPError as e:
            logging.warning(f"Attempt {attempt + 1} failed with error: {e}")
            sleep(2 ** attempt)  # Exponential backoff
    raise Exception("API request failed after multiple retries")

def batch_upsert_records(table, records, key_field):
    batch_size = 10
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        to_create = []
        to_update = []
        for record in batch:
            key_value = record['fields'][key_field]
            existing_record = retry_request(table.first, formula=match({key_field: key_value}))
            if existing_record:
                existing_fields = existing_record['fields']
                # Merge existing linked accounts with new ones
                if 'Account' in existing_fields and 'Account' in record['fields']:
                    existing_accounts = existing_fields['Account']
                    new_accounts = record['fields']['Account']
                    record['fields']['Account'] = list(set(existing_accounts + new_accounts))
                if not any(r['id'] == existing_record['id'] for r in to_update):
                    to_update.append({'id': existing_record['id'], 'fields': record['fields']})
            else:
                to_create.append(record)
        if to_create:
            logging.info(f"Creating batch of {len(to_create)} records.")
            retry_request(table.batch_create, to_create)
        if to_update:
            logging.info(f"Updating batch of {len(to_update)} records.")
            retry_request(table.batch_update, to_update)

def load_airtable_ids(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def save_airtable_ids(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f)

def push_data_to_airtable(df, airtable_ids):
    records_to_upsert = []
    
    for _, row in df.iterrows():
        account_data = {
            'Account ID': str(row['id']),  # Ensure the Account ID is treated as a string
            'Username': row['username'],
            'Full Name': row['name'],
            'Description': row['description'],
            'Followers Count': row['followers_count'],
            'Listed Count': row['listed_count'],
            'Created At': row['created_at'],
        }
        records_to_upsert.append({'fields': account_data})
    
    logging.info(f"Upserting {len(records_to_upsert)} account records.")
    batch_upsert_records(accounts_table, records_to_upsert, 'Account ID')
    
    for record in accounts_table.all():
        airtable_ids['Accounts'][record['fields']['Account ID']] = record['id']
    
    return airtable_ids

def push_followers_to_airtable(df, airtable_ids, username_to_id):
    records_to_upsert = []
    existing_follower_ids = set()
    
    for _, row in df.iterrows():
        followers = row['followed_by'].split(', ') if pd.notnull(row['followed_by']) else []
        
        for follower in followers:
            follower_id = username_to_id.get(follower)
            account_record_id = airtable_ids['Accounts'].get(str(row['id']))
            if follower_id and account_record_id:
                follower_data = {
                    'Account ID': str(follower_id),  # Ensure the Account ID is treated as a string
                    'Account': [account_record_id],
                    'Username': follower
                }
                records_to_upsert.append({'fields': follower_data})
                existing_follower_ids.add((follower_id, account_record_id))
    
    logging.info(f"Upserting {len(records_to_upsert)} follower records.")
    for record in records_to_upsert:
        logging.info(f"Follower record to upsert: {record}")
    
    batch_upsert_records(followers_table, records_to_upsert, 'Account ID')

def main():
    logging.info("Starting the process.")
    airtable_ids_file = 'airtable_ids.json'
    airtable_ids = load_airtable_ids(airtable_ids_file)
    if 'Accounts' not in airtable_ids:
        airtable_ids['Accounts'] = {}
    
    target_accounts_df, username_to_id = load_csv_files()
    logging.info("CSV files processed.")
    
    airtable_ids = push_data_to_airtable(target_accounts_df, airtable_ids)
    logging.info("Account data pushed to Airtable.")
    
    push_followers_to_airtable(target_accounts_df, airtable_ids, username_to_id)
    logging.info("Follower data pushed to Airtable.")
    
    save_airtable_ids(airtable_ids_file, airtable_ids)
    logging.info("Airtable IDs saved.")

if __name__ == "__main__":
    main()
