import pandas as pd
import logging
import time
from datetime import datetime
import os
import csv
from twitter.twitter import authenticate_twitter_api, fetch_list_members, get_user_details
from twitter.twitter_account_details import fetch_and_save_accounts, save_user_details_to_csv
from utils.config import load_env_variables
from utils.logging_setup import setup_logging
from utils.data_utils import ensure_user_directory_exists, save_cumulative_follows, save_incremental_updates
from scraping.scraping import init_driver, load_cookies, get_following

# Load environment variables
env_vars = load_env_variables()

# Setup logging
setup_logging()

# Twitter API Headers
headers = {"Authorization": f"Bearer {env_vars['bearer_token']}"}

# Load the existing target accounts
existing_target_df = pd.read_csv('target_accounts.csv')
existing_usernames = set(existing_target_df['username'].values)

# Load the incremental updates list
updates_df = pd.read_csv('incremental_updates_list.csv')
unique_accounts_from_updates = set(updates_df['account'].unique())

# Identify new accounts not already in target_accounts.csv
new_accounts = unique_accounts_from_updates.difference(existing_usernames)

# Initialize a counter for API requests
api_request_count = 0
api_request_limit = 450  # Set based on Twitter API rate limit for your app
rate_limit_reset_time = 900  # 15 minutes in seconds

# Fetch and save details for new accounts
for account in new_accounts:
    if api_request_count >= api_request_limit:
        logging.info(f"Rate limit reached. Pausing for {rate_limit_reset_time} seconds.")
        time.sleep(rate_limit_reset_time)
        api_request_count = 0  # Reset the request counter after the wait

    user_details = get_user_details(account, headers)
    if user_details:
        save_user_details_to_csv('target_accounts.csv', user_details)
        api_request_count += 1  # Increment the request count after each successful API call
