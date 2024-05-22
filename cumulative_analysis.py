import os
import pandas as pd
from datetime import datetime

# Define the base path to the extracted data
base_path = 'output'  # Update this path as needed

# Get the list of all users' incremental_updates.csv files
users = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
incremental_files = [os.path.join(base_path, user, 'incremental_updates.csv') for user in users]

# Initialize a dictionary to store the data
follow_updates = {}

# Process incremental_updates.csv files to populate the follow_updates dictionary
for file in incremental_files:
    df = pd.read_csv(file)
    for i, row in df.iterrows():
        timestamp = datetime.strptime(row.iloc[0], '%Y-%m-%d %H:%M:%S')  # Use .iloc for positional indexing
        account = row.iloc[1]  # Use .iloc for positional indexing
        if account not in follow_updates:
            follow_updates[account] = {}
        date = timestamp.date()
        if date not in follow_updates[account]:
            follow_updates[account][date] = 1
        else:
            follow_updates[account][date] += 1

# Convert the follow_updates dictionary to a DataFrame
follow_updates_df = pd.DataFrame.from_dict(follow_updates, orient='index').fillna(0)
follow_updates_df.index.name = 'Account'

# Convert column names back to string format for display
follow_updates_df.columns = follow_updates_df.columns.astype(str)

# Add a new column to represent the sum of follows for each account
follow_updates_df['Total Follows'] = follow_updates_df.sum(axis=1)

# Sort the DataFrame by the Total Follows column in descending order
sorted_follow_updates_df = follow_updates_df.sort_values(by='Total Follows', ascending=False)

# Save the sorted DataFrame to a CSV file
sorted_follow_updates_df.to_csv('sorted_follow_updates.csv')

# Display the sorted DataFrame (for local testing purposes)
print(sorted_follow_updates_df.head())

import csv
from collections import defaultdict

# Load target accounts
target_accounts = {}
with open('target_accounts.csv', mode='r', encoding='utf-8') as file:
    reader = csv.DictReader(file, delimiter=',')
    for row in reader:
        target_accounts[row['username']] = row

# Load incremental updates and build the followers list
followers = defaultdict(list)
with open('incremental_updates_list.csv', mode='r', encoding='utf-8') as file:
    reader = csv.reader(file, delimiter=',')
    for row in reader:
        if len(row) < 3:
            continue
        timestamp, username, follower = row[0], row[1], row[2]
        followers[username].append(follower)

# Write the joined data to a new CSV file
with open('joined_accounts.csv', mode='w', newline='', encoding='utf-8') as file:
    fieldnames = ['id', 'name', 'username', 'created_at', 'description', 'followers_count', 'listed_count', 'followed_by']
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()

    for username, account in target_accounts.items():
        account['followed_by'] = ', '.join(followers[username])
        writer.writerow(account)