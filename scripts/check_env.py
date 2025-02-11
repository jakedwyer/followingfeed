#!/usr/bin/env python3
import os
from utils.config import load_env_variables


def check_environment():
    print("Checking environment variables...")

    # Try loading from config
    try:
        env_vars = load_env_variables()
        print("\nFrom load_env_variables():")
        for key in ["airtable_token", "airtable_base_id", "airtable_accounts_table"]:
            value = env_vars.get(key)
            if value:
                print(
                    f"{key}: {'*' * 8}{value[-4:]}"
                    if "token" in key
                    else f"{key}: {value}"
                )
            else:
                print(f"{key}: NOT SET")
    except Exception as e:
        print(f"Error loading from config: {str(e)}")

    # Check direct environment variables
    print("\nFrom os.environ:")
    for key in ["AIRTABLE_TOKEN", "AIRTABLE_BASE_ID", "AIRTABLE_ACCOUNTS_TABLE"]:
        value = os.environ.get(key)
        if value:
            print(
                f"{key}: {'*' * 8}{value[-4:]}" if "TOKEN" in key else f"{key}: {value}"
            )
        else:
            print(f"{key}: NOT SET")


if __name__ == "__main__":
    check_environment()
