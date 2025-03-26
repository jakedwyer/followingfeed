from wsgiref import headers
import requests
import logging
from utils.airtable import fetch_records_from_airtable, update_airtable_records


def get_user_details(username, headers):
    """Fetch detailed information of a specific Twitter user, handling rate limits."""
    user_fields = "id,name,username,created_at,description,public_metrics,verified"
    url = f"https://api.twitter.com/2/users/by/username/{username}?user.fields={user_fields}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        response_data = response.json()
        if "errors" in response_data:
            logging.error(
                f"Error fetching user details for {username}: {response_data['errors']}"
            )
            return None
        logging.info(f"User details for {username} fetched successfully.")
        return response_data
    elif response.status_code == 429:
        logging.info(f"Rate limit exceeded. Max accounts have been pulled for the day.")
        return None
    else:
        logging.error(f"Failed to retrieve user details: {response.status_code}")
        return None


def save_user_details_to_airtable(user_details):
    """Save detailed Twitter user information to Airtable."""
    user_data = {
        "Account ID": user_details["data"]["id"],
        "Full Name": user_details["data"]["name"],
        "Username": user_details["data"]["username"],
        "Created At": user_details["data"]["created_at"],
        "Description": user_details["data"]["description"],
        "Followers Count": user_details["data"]["public_metrics"]["followers_count"],
        "Listed Count": user_details["data"]["public_metrics"]["listed_count"],
    }
    update_airtable_records([user_data], "tblJCXhcrCxDUJR3F", headers)


def fetch_and_save_accounts(usernames, headers):
    for username in usernames:
        user_details = get_user_details(username, headers)
        if user_details:
            save_user_details_to_airtable(user_details)
