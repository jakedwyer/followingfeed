"""Utility functions for the Twitter Network Analysis project."""

from .airtable import (
    fetch_records_from_airtable,
    post_airtable_records,
    update_airtable_records,
    fetch_existing_follows,
    fetch_and_update_accounts,
    update_airtable,
    delete_airtable_record,
    airtable_api_request,
)

from .helpers import (
    normalize_username,
    batch_request,
    prepare_update_record,
)

from .twitter_helpers import (
    get_following,
)

from .user_data import (
    get_user_details,
    update_user_details,
    load_user_details,
    save_user_details,
)

from .logging_setup import setup_logging

__all__ = [
    # Airtable functions
    "fetch_records_from_airtable",
    "post_airtable_records",
    "update_airtable_records",
    "fetch_existing_follows",
    "fetch_and_update_accounts",
    "update_airtable",
    "delete_airtable_record",
    "airtable_api_request",
    # Helper functions
    "normalize_username",
    "batch_request",
    "prepare_update_record",
    # Twitter helpers
    "get_following",
    # User data functions
    "get_user_details",
    "update_user_details",
    "load_user_details",
    "save_user_details",
    # Logging
    "setup_logging",
]
