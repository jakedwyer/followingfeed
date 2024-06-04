import pandas as pd
from pyairtable import Api, formulas
from pyairtable.formulas import match
import os
import numpy as np
from dotenv import load_dotenv
import logging
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

# Get table instances
accounts_table = api.table(BASE_ID, 'Accounts')
followers_table = api.table(BASE_ID, 'Followers')
logging.info("Table instances retrieved.")

def load_csv_files():
    logging.info("Loading CSV files...")
    target_accounts_df = pd.read_csv('/root/followfeed/joined_accounts.csv')
    list_members_df = pd.read_csv('/root/followfeed/list_members.csv')

    username_to_id = dict(zip(list_members_df['Username'], list_members_df['ID']))

    target_accounts_df.replace([np.inf, -np.inf], None, inplace=True)
    target_accounts_df.where(pd.notnull(target_accounts_df), None, inplace=True)

    logging.info("CSV files loaded.")
    return target_accounts_df, username_to_id

def load_processed_records(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def save_processed_records(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f)

def push_followers_to_airtable(df, account_id_to_record_id, username_to_id, processed_records):
    logging.info("Pushing followers data to Airtable...")
    for _, row in df.iterrows():
        if str(row['id']) in processed_records:
            continue  # Skip already processed records

        followers = row['followed_by'].split(', ') if pd.notnull(row['followed_by']) else []
        
        for follower in followers:
            follower_id = username_to_id.get(follower)
            if follower_id:
                formula = match({'Account ID': str(follower_id), 'Username': follower})
                existing_follower = followers_table.first(formula=formula)
                
                if existing_follower:
                    existing_accounts = existing_follower['fields'].get('Account', [])
                    if account_id_to_record_id[row['id']] not in existing_accounts:
                        existing_accounts.append(account_id_to_record_id[row['id']])
                    follower_data = {
                        'Account ID': str(follower_id),
                        'Account': existing_accounts,
                        'Username': follower,
                    }
                    followers_table.update(existing_follower['id'], follower_data)
                    logging.info(f"Updated follower {follower}.")
                else:
                    follower_data = {
                        'Account ID': str(follower_id),
                        'Account': [account_id_to_record_id[row['id']]],
                        'Username': follower,
                    }
                    followers_table.create(follower_data)
                    logging.info(f"Created new follower {follower}.")

        processed_records[str(row['id'])] = True

    logging.info("Followers data pushed to Airtable.")
    return processed_records

def push_data_to_airtable(df, processed_records):
    account_id_to_record_id = {}
    
    for _, row in df.iterrows():
        if str(row['id']) in processed_records:
            continue  # Skip already processed records

        account_data = {
            'Account ID': str(row['id']),
            'Username': row['username'],
            'Full Name': row['name'],
            'Description': row['description'],
            'Followers Count': row['followers_count'],
            'Listed Count': row['listed_count'],
            'Created At': row['created_at'],
        }
        
        formula = match({'Account ID': str(row['id'])})
        existing_account = accounts_table.first(formula=formula)
        
        if existing_account:
            account_record = accounts_table.update(existing_account['id'], account_data)
        else:
            account_record = accounts_table.create(account_data)
        
        account_id_to_record_id[row['id']] = account_record['id']
        processed_records[str(row['id'])] = True
    
    return account_id_to_record_id, processed_records

def main():
    processed_records_file = 'processed_records.json'
    processed_records = load_processed_records(processed_records_file)

    target_accounts_df, username_to_id = load_csv_files()

    account_id_to_record_id, processed_records = push_data_to_airtable(target_accounts_df, processed_records)
    processed_records = push_followers_to_airtable(target_accounts_df, account_id_to_record_id, username_to_id, processed_records)

    save_processed_records(processed_records_file, processed_records)

if __name__ == "__main__":
    main()