import requests
import logging
from typing import Dict, List, Optional, Any


def fetch_list_members(list_id, headers):
    url = f"https://api.twitter.com/2/lists/{list_id}/members"
    members = []
    params = {
        "max_results": 100
    }

    while True:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            members_data = response.json()
            members.extend([
                {"username": member["username"], "id": member["id"]}
                for member in members_data.get("data", [])
            ])
            next_token = members_data.get("meta", {}).get("next_token")
            if not next_token:
                break
            params["pagination_token"] = next_token
        else:
            logging.error(f"Error fetching list members: {response.status_code}")
            logging.error(f"Response: {response.text}")
            break

    return members

def fetch_twitter_data_api(username: str, bearer_token: str) -> Optional[Dict[str, Any]]:
    url = f"https://api.twitter.com/2/users/by/username/{username}"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent": "TwitterDevSampleCode"
    }
    params = {"user.fields": "id,name,username,created_at,description,public_metrics"}
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('data')
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data from Twitter API for {username}: {e}")
        return None