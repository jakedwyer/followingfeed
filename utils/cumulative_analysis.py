import csv
from collections import defaultdict

def process_accounts():
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
