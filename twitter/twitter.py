import tweepy
import requests
import logging

def authenticate_twitter_api(consumer_key, consumer_secret, access_token, access_token_secret):
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True)
    try:
        api.verify_credentials()
        logging.info("Authentication OK")
        return api
    except Exception as e:
        logging.error(f"Error during authentication: {e}")
        return None

def fetch_list_members(list_id, headers):
    url = f"https://api.twitter.com/2/lists/{list_id}/members"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        members_data = response.json()
        logging.info(str(members_data))
        return [
            (member["username"], member["id"])
            for member in members_data.get("data", [])
        ]
    else:
        logging.error(f"Error fetching list members: {response.status_code}")
        logging.error(f"Response: {response.text}")
        return []
