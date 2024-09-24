import os
import requests
from dotenv import load_dotenv
import json


def get_airtable_base_schema():
    # Load environment variables from .env file
    load_dotenv()

    # Get the Airtable API token from .env
    airtable_token = os.getenv("AIRTABLE_TOKEN")

    # Get the base ID from .env or use the one from your current code
    base_id = os.getenv("AIRTABLE_BASE_ID", "appYCZWcmNBXB2uUS")

    # Set up the request headers
    headers = {
        "Authorization": f"Bearer {airtable_token}",
        "Content-Type": "application/json",
    }

    # Make the API request
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None


# Usage
schema = get_airtable_base_schema()
if schema:
    with open("airtableschema.json", "w") as f:
        json.dump(schema, f, indent=2)
