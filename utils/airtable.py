import pandas as pd
from pyairtable import Api, formulas
from pyairtable.formulas import match
import os
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()
logging.info("Environment variables loaded.")

# Get Airtable API key and base ID from environment
ACCESS_TOKEN = os.getenv('AIRTABLE_TOKEN')
BASE_ID = os.getenv('AIRTABLE_BASE_ID')

# Ensure the environment variables are not None
if not ACCESS_TOKEN or not BASE_ID:
    raise ValueError("Airtable API key and Base ID must be set in environment variables.")

# Initialize Airtable API
api = Api(ACCESS_TOKEN)
logging.info("Airtable API initialized.")

# Get table instances
accounts_table = api.table(BASE_ID, 'Accounts')
followers_table = api.table(BASE_ID, 'Followers')
incremental_updates_table = api.table(BASE_ID, 'Incremental Updates')
logging.info("Table instances retrieved.")

def load_data_from_airtable(table_name):
    table = api.table(BASE_ID, table_name)
    records = table.all()
    data = [record['fields'] for record in records]
    return pd.DataFrame(data)

def save_data_to_airtable(table_name, data):
    table = api.table(BASE_ID, table_name)
    for record in data.to_dict('records'):
        table.create(record)

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

                # Update the followers field in the accounts table
                account_record_id = account_id_to_record_id[row['id']]
                account_record = accounts_table.get(account_record_id)
                existing_followers = account_record['fields'].get('Followers', [])
                if follower_id not in existing_followers:
                    existing_followers.append(follower_id)
                    accounts_table.update(account_record_id, {'Followers': existing_followers})
                    logging.info(f"Added follower {follower_id} to account {account_record_id}.")

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
            'First Appearance': row['first_appearance'],
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