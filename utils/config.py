import os
from dotenv import load_dotenv

def load_env_variables():
    print(f"Current working directory: {os.getcwd()}")
    load_dotenv()
    print("Environment variables loaded from .env file")
    env_vars = {
        'bearer_token': os.getenv('BEARER_TOKEN'),
        'consumer_key': os.getenv('CONSUMER_KEY'),
        'consumer_secret': os.getenv('CONSUMER_SECRET'),
        'access_token': os.getenv('ACCESS_TOKEN'),
        'access_token_secret': os.getenv('ACCESS_TOKEN_SECRET'),
        'list_id': os.getenv('LIST_ID'),
        'cookie_path': os.getenv('COOKIE_PATH'),
        'airtable_token': os.getenv('AIRTABLE_TOKEN'),
        'airtable_base_id': os.getenv('AIRTABLE_BASE_ID')
    }
    return env_vars
