from sys import api_version
import pandas as pd
import requests
import logging
import os

logging.basicConfig(level=logging.INFO)
#  load environment variables for authentication with the api_version
from dotenv import load_dotenv
load_dotenv()

bearer_token = os.getenv("Bearer")
headers = { "Authorization": f"Bearer {bearer_token}" }
url = "https://api.twitter.com/2/users/by/username/"

def gather_twitter_data(usernames):
    """Fetch join date, followers count, description, and website for given usernames."""
    user_data = []
    for username in usernames:
        try:
            response = requests.get(f"{url}{username}", headers=headers)
            user = response.json()['data']
            user_info = {
                'username': username,
                'join_date': user['created_at'],
                'followers_count': user['public_metrics']['followers_count'],
                'description': user['description'],
                'website': user['entities']['url']['urls'][0]['expanded_url'] if 'url' in user['entities'] else None
            }
            user_data.append(user_info)
        except Exception as e:
            logging.error(f"Failed to fetch data for {username}: {e}")
    return user_data

def authenticate_twitter_api():
    """Authenticate with Twitter API using Bearer Token."""
    bearer_token = os.getenv("Bearer")
    headers = {"Authorization": f"Bearer {bearer_token}"}
    try:
        response = requests.get("https://api.twitter.com/2/users/me", headers=headers)
        if response.status_code == 200:
            logging.info("Authentication OK")
            return headers
        else:
            logging.error(f"Error during authentication: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Error during authentication: {e}")
        return None

def main_aggregate():
    # Authenticate with Twitter API
    headers = authenticate_twitter_api()
    if headers is None:
        logging.error("Twitter API authentication failed.")
        return

    # Read all usernames from the incremental updates list
    df = pd.read_csv('incremental_updates_list.csv')
    unique_usernames = df['account'].unique()

    # Gather data from Twitter
    twitter_data = gather_twitter_data(unique_usernames)

    # Convert to DataFrame and save
    twitter_df = pd.DataFrame(twitter_data)
    twitter_df.to_csv('twitter_user_data.csv', index=False)
    logging.info("Twitter user data saved to 'twitter_user_data.csv'.")

if __name__ == "__main__":
    main_aggregate()
