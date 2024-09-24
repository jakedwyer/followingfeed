import logging
import json
from utils.config import load_env_variables
from utils.logging_setup import setup_logging
from utils.airtable import (
    fetch_records_from_airtable,
    update_airtable_records,
)
from scraping.scraping import clean_text


def clean_and_update_records():
    setup_logging()
    logger = logging.getLogger(__name__)
    env_vars = load_env_variables()

    # Set up Airtable API headers
    headers = {
        "Authorization": f"Bearer {env_vars['airtable_token']}",
        "Content-Type": "application/json",
    }

    try:
        # Load user details from JSON file
        with open("user_details.json", "r", encoding="utf-8") as file:
            user_details = json.load(file)

        # Fetch all records from Airtable
        all_records = fetch_records_from_airtable(
            env_vars["airtable_accounts_table"], headers
        )

        records_to_update = []

        # Iterate over user details and clean text fields
        for username, user_info in user_details.items():
            user_data = user_info.get("data", {})
            full_name = user_data.get("Full Name", "")
            description = user_data.get("Description", "")

            cleaned_full_name = clean_text(full_name)
            cleaned_description = clean_text(description)

            # Update the record in Airtable if cleaning was necessary
            if full_name != cleaned_full_name or description != cleaned_description:
                record_id = user_info.get("id")
                if record_id:
                    fields_to_update = {
                        "Full Name": cleaned_full_name,
                        "Description": cleaned_description,
                    }
                    records_to_update.append(
                        {"id": record_id, "fields": fields_to_update}
                    )
                    logger.info(
                        f"Prepared update for record {record_id} with cleaned data."
                    )

        # Update records in batches
        update_airtable_records(
            records_to_update, env_vars["airtable_accounts_table"], headers
        )

        logger.info("Cleaning and updating process completed successfully.")

    except Exception as e:
        logger.error(f"An error occurred during the cleaning and updating process: {e}")


if __name__ == "__main__":
    clean_and_update_records()
