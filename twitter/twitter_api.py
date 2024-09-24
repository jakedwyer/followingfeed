# twitter/twitter_api.py
import logging
from typing import List, Dict, Any

import aiohttp
import os

logger = logging.getLogger(__name__)

TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN")
LIST_ID = os.environ.get("LIST_ID")


async def fetch_list_members_async(
    list_id: str, headers: Dict[str, str]
) -> List[Dict[str, str]]:
    """
    Fetch members of a Twitter list asynchronously.

    Args:
        list_id (str): The Twitter list ID.
        headers (Dict[str, str]): HTTP headers including authorization.

    Returns:
        List[Dict[str, str]]: List of members with 'username' and 'id'.
    """
    url = f"https://api.twitter.com/2/lists/{list_id}/members"
    members = []
    params = {"max_results": 100}

    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    members_data = await response.json()
                    data = members_data.get("data", [])
                    for member in data:
                        members.append(
                            {"username": member["username"], "id": member["id"]}
                        )
                    next_token = members_data.get("meta", {}).get("next_token")
                    if not next_token:
                        break
                    params["pagination_token"] = next_token
                else:
                    response_text = await response.text()
                    logger.error(f"Error fetching list members: {response.status}")
                    logger.error(f"Response: {response_text}")
                    break

    return members


async def fetch_twitter_data_api_async(
    username: str, bearer_token: str
) -> Dict[str, Any]:
    """
    Fetch user data from Twitter API asynchronously.

    Args:
        username (str): Twitter username.
        bearer_token (str): Twitter API bearer token.

    Returns:
        Dict[str, Any]: User data dictionary.
    """
    url = f"https://api.twitter.com/2/users/by/username/{username}"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent": "TwitterDevSampleCode",
    }
    params = {"user.fields": "id,name,username,created_at,description,public_metrics"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", {})
            else:
                response_text = await response.text()
                logger.error(f"Error fetching data for {username}: {response.status}")
                logger.error(f"Response: {response_text}")
                return {}
