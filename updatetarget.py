import pandas as pd
import logging
import time
from twitter.twitter_account_details import get_user_details, save_user_details_to_csv
from utils.config import load_env_variables
from utils.logging_setup import setup_logging

# Initialize environment and logging
env_vars = load_env_variables()
setup_logging()

# Set up Twitter API headers
headers = {"Authorization": f"Bearer {env_vars['bearer_token']}"}

# Load existing and updated account data
existing_target_df = pd.read_csv('target_accounts.csv')
updates_df = pd.read_csv('incremental_updates_list.csv')

# Determine new accounts to process
existing_usernames = set(existing_target_df['username'])
unique_accounts_from_updates = set(updates_df['account'].unique())
new_accounts = unique_accounts_from_updates.difference(existing_usernames)

# API request management
api_request_count = 0
api_request_limit = 450  # Twitter API rate limit
rate_limit_reset_time = 900  # 15 minutes

# Process new accounts
for account in new_accounts:
    if api_request_count >= api_request_limit:
        logging.info(f"Rate limit reached. Pausing for {rate_limit_reset_time} seconds.")
        time.sleep(rate_limit_reset_time)
        api_request_count = 0

    user_details = get_user_details(account, headers)
    if user_details:
        save_user_details_to_csv('target_accounts.csv', user_details)
        api_request_count += 1
