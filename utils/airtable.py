import pandas as pd
from pyairtable import Api, formulas
from pyairtable.formulas import match
import os
import numpy as np
from dotenv import load_dotenv
import logging

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

def push_followers_to_airtable(df, account_id_to_record_id, username_to_id):
    logging.info("Pushing followers data to Airtable...")
    for _, row in df.iterrows():
        followers = row['followed_by'].split(', ') if pd.notnull(row['followed_by']) else []
        
        for follower in followers:
            follower_id = username_to_id.get(follower)
            if follower_id:
                follower_data = {
                    'Account ID': follower_id,
                    'Account': [account_id_to_record_id[row['id']]],
                    'Username': follower,
                    'Description': '',
                }
                
                formula = match({'Account ID': follower_id, 'Username': follower})
                existing_follower = followers_table.first(formula=formula)
                
                if existing_follower:
                    followers_table.update(existing_follower['id'], follower_data)
                    logging.info(f"Updated follower {follower}.")
                else:
                    followers_table.create(follower_data)
                    logging.info(f"Created new follower {follower}.")

    logging.info("Followers data pushed to Airtable.")

def push_data_to_airtable(df):
    account_id_to_record_id = {}
    
    for _, row in df.iterrows():
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
    
    return account_id_to_record_id

# Load CSV files
target_accounts_df, username_to_id = load_csv_files()

# Push data to Airtable and get account_id_to_record_id mapping
account_id_to_record_id = push_data_to_airtable(target_accounts_df)

# Push followers data
push_followers_to_airtable(target_accounts_df, account_id_to_record_id, username_to_id)