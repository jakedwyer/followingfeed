import json


def should_delete_record(user_data):
    """Check if a record should be deleted based on specified criteria."""
    if not user_data["data"].get("Full Name"):
        return True

    fields_to_check = ["Followers Count", "Following Count", "Like Count"]
    return any(user_data["data"].get(field, 0) == 0 for field in fields_to_check)


def clean_user_details():
    # Load the JSON file
    with open("user_details.json", "r") as file:
        user_details = json.load(file)

    # Filter out records that meet the deletion criteria
    cleaned_user_details = {
        username: data
        for username, data in user_details.items()
        if not should_delete_record(data)
    }

    # Save the cleaned data back to the file
    with open("user_details.json", "w") as file:
        json.dump(cleaned_user_details, file, indent=2)

    print(
        f"Cleaned user_details.json. Removed {len(user_details) - len(cleaned_user_details)} records."
    )


if __name__ == "__main__":
    clean_user_details()
