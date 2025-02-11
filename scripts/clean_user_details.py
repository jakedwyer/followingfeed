import json
import logging
import sys
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_user_details(json_file_path: str):
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"Loaded {len(data)} entries from {json_file_path}")
    except FileNotFoundError:
        logger.error(f"File {json_file_path} not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {json_file_path}: {e}")
        sys.exit(1)

    cleaned_data = {}

    for username, user_info in data.items():
        if not isinstance(user_info, dict):
            logger.warning(f"Skipping entry for '{username}': data is not a dict")
            continue

        # Ensure the username key is a string
        if not isinstance(username, str):
            username = str(username)

        if "data" not in user_info:
            # Wrap user_info inside 'data' key
            cleaned_entry = {
                "data": user_info,
                "last_updated": datetime.utcnow().isoformat() + "Z",
            }
            logger.debug(f"Wrapped data for '{username}' inside 'data' key")
        else:
            cleaned_entry = user_info
            # Ensure 'last_updated' key exists
            if "last_updated" not in cleaned_entry:
                cleaned_entry["last_updated"] = datetime.utcnow().isoformat() + "Z"
                logger.debug(f"Added 'last_updated' for '{username}'")
        cleaned_data[username] = cleaned_entry

    # Write the cleaned data back to the JSON file
    try:
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Cleaned data saved to {json_file_path}")
    except Exception as e:
        logger.error(f"Error writing to {json_file_path}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Replace 'user_details.json' with your actual file path if different
    json_file = "user_details.json"
    clean_user_details(json_file)
