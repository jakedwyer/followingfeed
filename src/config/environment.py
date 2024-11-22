import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

AIRTOP_API_KEY = os.getenv("AIRTOP_API_KEY")
if not AIRTOP_API_KEY:
    raise ValueError("AIRTOP_API_KEY environment variable is not set")
