import logging
from utils.config import load_env_variables
from utils.logging_setup import setup_logging
from utils.data_utils import ensure_user_directory_exists, save_cumulative_follows, save_incremental_updates
from twitter.twitter import authenticate_twitter_api, fetch_list_members
from scraping.scraping import init_driver, load_cookies, get_following
from twitter.twitter_account_details import fetch_and_save_accounts
import pandas as pd
from datetime import datetime
import os
import csv

def main():
    # Load environment variables
    env_vars = load_env_variables()

    # Setup logging
    setup_logging()

    # Twitter API Headers
    headers = {"Authorization": f"Bearer {env_vars['bearer_token']}"}

    # Fetch list members
    list_members = fetch_list_members(env_vars['list_id'], headers)

    if not list_members:
        logging.error("Failed to fetch list members.")
        return

    total_members = len(list_members)
    processed_members = 0

    driver = init_driver()
    load_cookies(driver, env_vars['cookie_path'])

    new_data = {}
    all_updates = []

    for username, _ in list_members:
        try:
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

            new_follows_set = set(new_follows)
            truly_new_follows = new_follows_set.difference(existing_follows)

            if truly_new_follows:
                save_incremental_updates(username, truly_new_follows)
                for follow in truly_new_follows:
                    all_updates.append({'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'account': follow, 'followed by': username})

            save_cumulative_follows(username, new_follows)

            processed_members += 1
            remaining_members = total_members - processed_members
            logging.info(f"Processed {processed_members}/{total_members}. Remaining: {remaining_members}")

        except Exception as e:
            logging.error(f"Error processing {username}: {e}")

    if all_updates:
        # Create a DataFrame from the list of updates
        df = pd.DataFrame(all_updates)
        # Append the DataFrame to a CSV file without replacing the current contents and without the index column
        df.to_csv('incremental_updates_list.csv', mode='a', header=False, index=False)
        # Log the successful appending of the updates
        logging.info("Incremental updates list appended to 'incremental_updates_list.csv'.")
    else:
        # Log that there are no new followings to update if the all_updates list is empty
        logging.info("No new followings to update.")

    # Extract all unique usernames for detailed account fetching
    unique_usernames = set([update['account'] for update in all_updates])

    # Fetch user details and save them to a deduplicated output
    target_accounts_file = 'target_accounts.csv'
    fetch_and_save_accounts(unique_usernames, target_accounts_file, headers)

    driver.quit()
## Add the following line to the end of the main function to call the main function when the script is run
if __name__ == "__main__":
    main()
