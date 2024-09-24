import json
from typing import Dict, Any
from datetime import datetime

USER_DETAILS_FILE = "user_details.json"


def load_user_details() -> Dict[str, Any]:
    try:
        with open(USER_DETAILS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_user_details(data: Dict[str, Any]) -> None:
    with open(USER_DETAILS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def update_user_details(username: str, new_data: Dict[str, Any]) -> None:
    user_details = load_user_details()
    username_lower = username.lower()

    if username_lower not in user_details:
        user_details[username_lower] = {"data": {}, "last_updated": ""}

    user_details[username_lower]["data"].update(new_data)
    user_details[username_lower]["last_updated"] = datetime.now().isoformat()

    save_user_details(user_details)


def get_user_details(username: str) -> Dict[str, Any]:
    user_details = load_user_details()
    return user_details.get(username.lower(), {}).get("data", {})
