import pandas as pd
from pyairtable import Api, formulas
from pyairtable.formulas import match
import os
import numpy as np
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load the environment variables
load_dotenv()
logging.info("Environment variables loaded.")

# Get the Airtable API key and base ID from the environment
ACCESS_TOKEN = os.getenv('AIRTABLE_TOKEN')
BASE_ID = os.getenv('AIRTABLE_BASE_ID')
ACCOUNTS_TABLE_NAME = 'Accounts'
FOLLOWERS_TABLE_NAME = 'Followers'

# Initialize Airtable API with access token
api = Api(ACCESS_TOKEN)
logging.info("Airtable API initialized.")

# Get the table instances
accounts_table = api.table(BASE_ID, ACCOUNTS_TABLE_NAME)
followers_table = api.table(BASE_ID, FOLLOWERS_TABLE_NAME)
logging.info("Table instances retrieved.")

def load_csv_files():
    logging.info("Loading CSV files...")
    # Load the target_accounts.csv file
    csv_file_path = '/root/followfeed/joined_accounts.csv'
    target_accounts_df = pd.read_csv(csv_file_path)

    # Load the list_members.csv file
    list_members_file_path = '/root/followfeed/list_members.csv'
    list_members_df = pd.read_csv(list_members_file_path)

    # Create a mapping from username to ID
    username_to_id = dict(zip(list_members_df['Username'], list_members_df['ID']))

    # Replace out of range float values with None
    target_accounts_df = target_accounts_df.replace([np.inf, -np.inf], None)
    target_accounts_df = target_accounts_df.where(pd.notnull(target_accounts_df), None)

    logging.info("CSV files loaded.")
    return target_accounts_df, username_to_id

# Function to push followers data to Airtable
def push_followers_to_airtable(df, account_id_to_record_id, username_to_id):
    logging.info("Pushing followers data to Airtable...")
    for index, row in df.iterrows():
        # Split the 'followed_by' column into a list of followers
        followers = row['followed_by'].split(', ') if pd.notnull(row['followed_by']) else []
        
        for follower in followers:
            follower_id = username_to_id.get(follower)
            if follower_id:
                follower_data = {
                    'fldn8HytJBk8AMCEA': [follower_id],  # Link to the Followers table
                    'fldGbi3dD2dfUl7Qm': [account_id_to_record_id[row['id']]],  # Link to the Accounts table
                    'fldzwVDGrXalAbvp7': follower,  # Username
                    'fldFLzHrEuaiyMlcb': 'Follower of ' + row['username'],  # Description
                }
                
                # Check if follower already exists
                formula = match({'Account ID': account_id_to_record_id[row['id']], 'Username': follower})
                existing_follower = followers_table.first(formula=formula)
                if existing_follower:
                    # Update existing follower
                    followers_table.update(existing_follower['id'], follower_data)
                    logging.info(f"Updated follower {follower}.")
                else:
                    # Create new follower
                    followers_table.create(follower_data)
                    logging.info(f"Created new follower {follower}.")

    logging.info("Followers data pushed to Airtable.")

# Load CSV files
target_accounts_df, username_to_id = load_csv_files()

# Dummy account_id_to_record_id for testing
account_id_to_record_id = {row['id']: 'recDummyId' for index, row in target_accounts_df.iterrows()}

# Call the function to push followers data
push_followers_to_airtable(target_accounts_df, account_id_to_record_id, username_to_id)