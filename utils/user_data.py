import json
from typing import Dict, Any
from datetime import datetime
import os
import logging
import tempfile
import shutil
from filelock import FileLock, Timeout

USER_DETAILS_FILE = "user_details.json"
LOCK_FILE = "user_details.json.lock"

logger = logging.getLogger(__name__)


def load_user_details() -> Dict[str, Any]:
    if os.path.exists(USER_DETAILS_FILE):
        try:
            with FileLock(LOCK_FILE, timeout=5):
                with open(USER_DETAILS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Timeout:
            logger.error(
                f"Timeout occurred while trying to acquire lock for {USER_DETAILS_FILE}."
            )
            return {}
        except json.JSONDecodeError as e:
            logger.error(
                f"Invalid JSON format in {USER_DETAILS_FILE} at line {e.lineno}, column {e.colno}: {e.msg}. Initializing empty user details."
            )
            return {}
        except Exception as e:
            logger.error(
                f"Unexpected error while loading {USER_DETAILS_FILE}: {e}. Initializing empty user details."
            )
            return {}
    else:
        return {}


def save_user_details(data: Dict[str, Any]) -> None:
    try:
        with FileLock(LOCK_FILE, timeout=5):
            with tempfile.NamedTemporaryFile(
                "w", delete=False, encoding="utf-8"
            ) as tmp_file:
                json.dump(data, tmp_file, indent=2)
                temp_name = tmp_file.name
            shutil.move(temp_name, USER_DETAILS_FILE)
    except Timeout:
        logger.error(
            f"Timeout occurred while trying to acquire lock for {USER_DETAILS_FILE}."
        )
    except Exception as e:
        logger.error(f"Failed to save user details to {USER_DETAILS_FILE}: {e}")


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
