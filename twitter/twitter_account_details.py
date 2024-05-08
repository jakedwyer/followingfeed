import requests
import os
import csv
import logging

def get_user_details(username, headers):
    """Fetch detailed information of a specific Twitter user."""
    user_fields = "id,name,username,created_at,description,public_metrics,verified"
    url = f"https://api.twitter.com/2/users/by/username/{username}?user.fields={user_fields}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        response_data = response.json()
        if 'errors' in response_data:
            logging.error(f"Error fetching user details for {username}: {response_data['errors']}")
            return None
        else:
            logging.info(f"User details for {username} fetched successfully.")
            return response_data
    else:
        logging.error(f"Failed to retrieve user details: {response.status_code}")
        return None

def save_user_details_to_csv(filename, user_details):
    """Save detailed Twitter user information to a CSV file."""
    user_data = {
        'id': user_details['data']['id'],
        'name': user_details['data']['name'],
        'username': user_details['data']['username'],
        'created_at': user_details['data']['created_at'],
        'description': user_details['data']['description'],
        'followers_count': user_details['data']['public_metrics']['followers_count'],
        'listed_count': user_details['data']['public_metrics']['listed_count']
    }
    fieldnames = ['id', 'name', 'username', 'created_at', 'description', 'followers_count', 'listed_count']
    with open(filename, 'a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if file.tell() == 0:
            writer.writeheader()
        writer.writerow(user_data)

def fetch_and_save_accounts(unique_usernames, filename, headers):
    """Fetch user details for each unique username and store them."""
    for username in unique_usernames:
        user_details = get_user_details(username, headers)
        if user_details:  # Check if the response was successful
            save_user_details_to_csv(filename, user_details)
