import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Default port settings
DEFAULT_API_PORT = 8000
DEFAULT_NITTER_PORT = 8081

# Get port settings from environment variables or use defaults
API_PORT = int(os.getenv("API_PORT", DEFAULT_API_PORT))
NITTER_PORT = int(os.getenv("NITTER_PORT", DEFAULT_NITTER_PORT))


def get_api_port():
    """Get the port for the FastAPI application"""
    return API_PORT


def get_nitter_port():
    """Get the port for the Nitter application"""
    return NITTER_PORT
