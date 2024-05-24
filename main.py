import logging
from utils.config import load_env_variables
from utils.logging_setup import setup_logging
from utils.data_utils import ensure_user_directory_exists, save_cumulative_follows, save_incremental_updates
from twitter.twitter import fetch_list_members
from scraping.scraping import init_driver, load_cookies, get_following
from twitter.twitter_account_details import fetch_and_save_accounts
from utils.cumulative_analysis import process_accounts
import pandas as pd
from datetime import datetime
import os
import csv
import requests

def process_user(username, driver, headers, all_updates):
    user_dir = ensure_user_directory_exists(username)
    cumulative_file = os.path.join(user_dir, "cumulative_follows.csv")
    existing_follows = set()

    try:
        with open(cumulative_file, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            for row in reader:
                if row:
                    existing_follows.add(row[0])
    except FileNotFoundError:
        logging.info(f"No existing follows file found for {username}, starting fresh.")

    new_follows = get_following(driver, username, existing_follows, max_accounts=None)
    truly_new_follows = set(new_follows).difference(existing_follows)

    if truly_new_follows:
        save_incremental_updates(username, truly_new_follows)
        for follow in truly_new_follows:
            all_updates.append({'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'account': follow, 'followed by': username})

    save_cumulative_follows(username, new_follows)

def update_incremental_updates(all_updates):
    try:
        existing_df = pd.read_csv('incremental_updates_list.csv')
    except FileNotFoundError:
        existing_df = pd.DataFrame(columns=['timestamp', 'account', 'followed by'])

    new_updates_df = pd.DataFrame(all_updates)
    combined_df = pd.concat([existing_df, new_updates_df], ignore_index=True)
    deduped_df = combined_df.drop_duplicates(subset=['account', 'followed by'])
    deduped_df.to_csv('incremental_updates_list.csv', index=False)
    logging.info("Incremental updates list saved to 'incremental_updates_list.csv'.")

def send_file_via_webhook(file_path, webhook_url):
    with open(file_path, 'rb') as f:
        response = requests.post(webhook_url, files={'file': f})
    return response

def main():
    env_vars = load_env_variables()
    setup_logging()
    headers = {"Authorization": f"Bearer {env_vars['bearer_token']}"}
    list_members = fetch_list_members(env_vars['list_id'], headers)

    if not list_members:
        logging.error("Failed to fetch list members.")
        return

    driver = init_driver()
    load_cookies(driver, env_vars['cookie_path'])
    all_updates = []

    for username, _ in list_members:
        try:
            process_user(username, driver, headers, all_updates)
            logging.info(f"Processed {username}")
        except Exception as e:
            logging.error(f"Error processing {username}: {e}")

    if all_updates:
        update_incremental_updates(all_updates)
    else:
        logging.info("No new followings to update.")

    unique_usernames = {update['account'] for update in all_updates}
    fetch_and_save_accounts(unique_usernames, 'target_accounts.csv', headers)
    driver.quit()
    process_accounts()

    response = send_file_via_webhook('joined_accounts.csv', 'https://hooks.zapier.com/hooks/catch/14552359/3v03fym/')
    if response.status_code == 200:
        logging.info("File sent successfully.")
    else:
        logging.error(f"Failed to send file. Status code: {response.status_code}")

if __name__ == "__main__":
    main()
