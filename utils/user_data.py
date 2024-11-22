import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

USER_DETAILS_FILE = "user_details.json"


def load_user_details() -> Dict[str, Any]:
    """Load user details from JSON file."""
    try:
        if Path(USER_DETAILS_FILE).exists():
            with open(USER_DETAILS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading user details: {str(e)}")
    return {}


def save_user_details(details: Dict[str, Any]) -> None:
    """Save user details to JSON file."""
    try:
        with open(USER_DETAILS_FILE, "w") as f:
            json.dump(details, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving user details: {str(e)}")


def get_user_details(username: str) -> Optional[Dict[str, Any]]:
    """Get details for a specific user."""
    details = load_user_details()
    return details.get(username)


def update_user_details(username: str, data: Dict[str, Any]) -> None:
    """Update details for a specific user."""
    details = load_user_details()
    details[username] = {"data": data}
    save_user_details(details)
