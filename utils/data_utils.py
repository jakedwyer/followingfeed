import os
import csv
from datetime import datetime

def ensure_user_directory_exists(handle):
    """Ensure that a directory exists for the user."""
    user_dir = os.path.join("output", handle)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return user_dir

def save_cumulative_follows(handle, follows):
    """Save the cumulative list of follows for a user."""
    user_dir = ensure_user_directory_exists(handle)
    cumulative_file = os.path.join(user_dir, "cumulative_follows.csv")
    with open(cumulative_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        for follow in follows:
            writer.writerow([follow])

def save_incremental_updates(handle, new_follows):
    """Save the incremental updates of new follows for a user."""
    if not new_follows:  # Skip if no new follows
        return
    user_dir = ensure_user_directory_exists(handle)
    incremental_file = os.path.join(user_dir, "incremental_updates.csv")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(incremental_file, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        for follow in new_follows:
            writer.writerow([timestamp, follow])

