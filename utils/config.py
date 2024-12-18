import os
from dotenv import load_dotenv
import logging


def load_env_variables():
    logging.info(f"Current working directory: {os.getcwd()}")

    # Print all environment variables before loading .env
    logging.debug("Environment variables before loading .env:")
    for key, value in os.environ.items():
        if "AIRTABLE" in key:
            logging.debug(f"{key}: {value}")

    load_dotenv()
    logging.info("Environment variables loaded from .env file")

    # Print all environment variables after loading .env
    logging.debug("Environment variables after loading .env:")
    for key, value in os.environ.items():
        if "AIRTABLE" in key:
            logging.debug(f"{key}: {value}")

    env_vars = {
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "twitter_api_key": os.getenv("TWITTER_API_KEY"),
        "twitter_api_secret": os.getenv("TWITTER_API_SECRET"),
        "twitter_bearer_token": os.getenv("TWITTER_BEARER_TOKEN"),
        "twitter_access_token": os.getenv("TWITTER_ACCESS_TOKEN"),
        "twitter_access_token_secret": os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
        "list_id": os.getenv("LIST_ID"),
        "cookie_path": os.getenv("COOKIE_PATH"),
        "airtable_base_id": os.getenv("AIRTABLE_BASE_ID"),
        "airtable_token": os.getenv("AIRTABLE_TOKEN"),
        "airtable_followers_table": os.getenv("AIRTABLE_FOLLOWERS_TABLE"),
        "airtable_accounts_table": os.getenv("AIRTABLE_ACCOUNTS_TABLE"),
        "airtable_api_endpoint": os.getenv("AIRTABLE_API_ENDPOINT"),
        "airtable_batch_size": int(os.getenv("AIRTABLE_BATCH_SIZE", 10)),
        "airtable_rate_limit": int(os.getenv("AIRTABLE_RATE_LIMIT", 5)),
        "notion_token": os.getenv("NOTION_TOKEN"),
        "field_username": os.getenv("FIELD_USERNAME"),
        "field_account": os.getenv("FIELD_ACCOUNT"),
        "field_account_id": os.getenv("FIELD_ACCOUNT_ID"),
        "field_followed_accounts": os.getenv("FIELD_FOLLOWED_ACCOUNTS"),
        "lock_file": os.getenv("LOCK_FILE"),
        "venv_path": os.getenv("VENV_PATH"),
        "log_file": os.getenv("LOG_FILE"),
    }
    return env_vars
