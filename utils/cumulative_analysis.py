import pandas as pd
from collections import defaultdict
from utils.airtable import load_data_from_airtable, save_data_to_airtable

def process_accounts():
    # Load target accounts
    target_accounts_df = load_data_from_airtable('Accounts')
    target_accounts = target_accounts_df.set_index('Account ID').to_dict('index')

    # Load incremental updates and build the followers list and first appearance timestamp
    incremental_updates_df = load_data_from_airtable('Incremental Updates')
    followers = defaultdict(list)
    first_appearance = {}

    for _, row in incremental_updates_df.iterrows():
        timestamp, account_id, followed_by = row['timestamp'], row['account'], row['followed by']
        followers[account_id].append(followed_by)
        if account_id not in first_appearance:
            first_appearance[account_id] = timestamp

    # Prepare the joined data
    joined_data = []
    for account_id, account in target_accounts.items():
        account['followed_by'] = followers[account_id]
        account['first_appearance'] = first_appearance.get(account_id, 'N/A')
        joined_data.append(account)

    # Save the joined data to Airtable
    save_data_to_airtable('Joined Accounts', pd.DataFrame(joined_data))