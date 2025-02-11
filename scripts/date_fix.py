import json
from datetime import datetime
from typing import Union

INPUT_JSON_FILE = "user_details.json"
OUTPUT_JSON_FILE = "standardized_user_details_fixed_dates.json"


def parse_date(date_string: Union[str, None]) -> str:
    if not date_string:
        return ""

    date_string = date_string.strip()

    # Handle "Joined" format
    if date_string.startswith("Joined"):
        date_string = date_string.replace("Joined", "").strip()

    # Try parsing various date formats
    date_formats = [
        "%B %Y",  # e.g., "November 2017"
        "%Y-%m-%d",  # e.g., "2017-11-01"
        "%Y-%m-%d %H:%M:%S",  # e.g., "2017-11-01 12:00:00"
    ]

    for date_format in date_formats:
        try:
            date_obj = datetime.strptime(date_string, date_format)
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # If all parsing attempts fail, return the original string
    print(f"Warning: Could not parse date '{date_string}'. Keeping original value.")
    return date_string


def fix_created_at_dates(data):
    for username, user_data in data.items():
        if "data" in user_data and isinstance(user_data["data"], dict):
            # Check for 'Created At' field
            created_at = user_data["data"].get("Created At")
            if created_at:
                parsed_created_at = parse_date(created_at)
                if parsed_created_at:
                    user_data["data"]["Created At"] = parsed_created_at
                else:
                    user_data["data"].pop("Created At", None)

            # Check for 'data_Created At' field
            data_created_at = user_data["data"].get("data_Created At")
            if data_created_at:
                user_data["data"]["data_Created At"] = parse_date(data_created_at)

            # Check for 'Join Date' field
            join_date = user_data["data"].get("Join Date")
            if join_date:
                parsed_join_date = parse_date(join_date)
                # If 'Created At' doesn't exist or is empty, use 'Join Date' as 'Created At'
                if not created_at or not user_data["data"].get("Created At"):
                    user_data["data"]["Created At"] = parsed_join_date
                # Remove the 'Join Date' field
                user_data["data"].pop("Join Date", None)

            # Remove 'Created At' if it's empty after all processing
            if (
                "Created At" in user_data["data"]
                and not user_data["data"]["Created At"]
            ):
                user_data["data"].pop("Created At", None)

    return data


def main():
    try:
        with open(INPUT_JSON_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {INPUT_JSON_FILE} not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: {INPUT_JSON_FILE} is not a valid JSON file.")
        return

    fixed_data = fix_created_at_dates(data)

    with open(OUTPUT_JSON_FILE, "w") as f:
        json.dump(fixed_data, f, indent=2)

    print(f"Fixed data has been written to {OUTPUT_JSON_FILE}")


if __name__ == "__main__":
    main()
