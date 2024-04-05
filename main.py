import tweepy
import os
import sys
import dotenv
import requests
import json
import logging
import time
import pickle
import csv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

dotenv.load_dotenv()
log_file_path = "app.log"
logging.basicConfig(
    filename=log_file_path,
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
# Load environment variables
bearer_token = os.getenv("Bearer")

# Twitter API headers
headers = {"Authorization": f"Bearer {bearer_token}"}

# Load environment variables from .env file
consumer_key = os.getenv("consumerKey")
consumer_secret = os.getenv("consumerSecret")
bearer_token = os.getenv("Bearer")
access_token = os.getenv("accessToken")
access_token_secret = os.getenv("accessTokenSecret")

from datetime import datetime
import os
import csv


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
    with open(
        incremental_file, mode="a", newline="", encoding="utf-8"
    ) as file:  # Append mode
        writer = csv.writer(file)
        for follow in new_follows:
            writer.writerow([timestamp, follow])


# Twitter API Authentication
def authenticate_twitter_api():
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True)
    try:
        api.verify_credentials()
        logging.info("Authentication OK")
        return api
    except Exception as e:
        logging.error(f"Error during authentication: {e}")
        return None


# Fetch List Members
def fetch_list_members(list_id):
    url = f"https://api.twitter.com/2/lists/{list_id}/members"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        members_data = response.json()
        logging.info(str(members_data))
        return [
            (member["username"], member["id"])
            for member in members_data.get("data", [])
        ]
    else:
        logging.error(f"Error fetching list members: {response.status_code}")
        logging.error(f"Response: {response.text}")
        return []


# Initialize Selenium WebDriver
def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1920, 1080)
    logging.info("WebDriver Initialized")
    return driver


# Load Cookies into WebDriver
def load_cookies(driver, cookie_path):
    driver.get("https://www.twitter.com")
    cookies = pickle.load(open(cookie_path, "rb"))
    for cookie in cookies:
        driver.add_cookie(cookie)
    logging.info("Cookies loaded into WebDriver.")
    driver.refresh()


def get_following(driver, handle, existing_follows, max_accounts=None):
    url = f"https://twitter.com/{handle}/following"
    driver.get(url)
    logging.info(f"Fetching new following for {handle}")
    time.sleep(10)  # Initial wait for page load

    # Check if initial links are loaded
    initial_elements = driver.find_elements(
        By.XPATH, "//div[@aria-label='Timeline: Following']//a[contains(@href, '/')]"
    )
    if not initial_elements:
        logging.error("No following links loaded on the page. Exiting function.")
        return list(existing_follows)

    scroll_pause_time = 10  # Increased pause time to ensure page loading
    incremental_scroll = 100  # Gradual scroll to load more data
    extracted_handles = set(existing_follows)
    logging.info(f"Existing handles: {len(existing_follows)}")
    try:
        # Use a different approach to detect end of scrolling
        # Check for the presence of a "You’re caught up" or similar message
        # or no new elements found after scroll
        previous_handles_count = len(extracted_handles)
        while True:
            driver.execute_script(
                f"window.scrollBy(0, {incremental_scroll});"
            )  # Gradual scrolling
            time.sleep(scroll_pause_time)  # Wait for the page to load

            elements = driver.find_elements(
                By.XPATH,
                "//div[@aria-label='Timeline: Following']//a[contains(@href, '/')]",
            )
            current_handles = {
                el.get_attribute("href").split("/")[-1]
                for el in elements
                if "/following" not in el.get_attribute("href")
                and "search?q=%23" not in el.get_attribute("href")
            }

            new_handles = current_handles.difference(extracted_handles)
            logging.info(f"Found {len(new_handles)} new handles.")
            extracted_handles.update(new_handles)

            # Debugging: Log current state of extracted handles
            logging.info(f"Current total extracted handles: {len(extracted_handles)}")

            # Check if no new handles were found in the last scroll
            if len(extracted_handles) == previous_handles_count:
                logging.info("No new data to load or reached the end of the page.")
                break
            previous_handles_count = len(extracted_handles)

            # Check for max accounts limit
            if max_accounts and len(extracted_handles) >= max_accounts:
                logging.info(f"Reached max accounts limit of {max_accounts}")
                break

    except Exception as e:
        logging.error(f"An error occurred while fetching following for {handle}: {e}")

    return list(extracted_handles)


def send_to_webhook(url, data):
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  # This will raise an exception for HTTP errors
        logging.info(f"Data successfully sent to webhook: {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending data to webhook: {e}")


def read_csv_data(filename):
    data = {}
    try:
        with open(filename, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            for row in reader:
                if row:
                    handle, follows = row[0], row[1:]
                    data[handle] = follows
    except FileNotFoundError:
        logging.error(f"File not found: {filename}")
    return data


def load_old_data(filename):
    """Load previously saved following data."""
    old_data = {}
    try:
        with open(filename, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            for row in reader:
                if row:
                    handle, follows = row[0], row[1:]
                    old_data[handle] = set(follows)
    except FileNotFoundError:
        pass
    return old_data


def save_new_data(filename, data):
    """Save new following data."""
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        for handle, follows in data.items():
            writer.writerow([handle] + list(follows))
    logging.info("New data saved.")


def main():
    list_id = os.getenv("list_id")
    list_members = fetch_list_members(list_id)

    if not list_members:
        logging.error("Failed to fetch list members.")
        return

    total_members = len(list_members)
    processed_members = 0

    driver = init_driver()
    cookie_path = os.getenv("cookie_path")
    load_cookies(driver, cookie_path)

    old_data = load_old_data("following.csv")
    new_data = {}

    for username, _ in list_members:
        try:
            existing_follows = old_data.get(username, set())
            logging.info(f"Existing follows: {existing_follows}")
            new_follows = get_following(
                driver, username, existing_follows, max_accounts=None
            )

            # Identify new follows by comparing with the old data
            new_follows_set = set(new_follows)
            old_follows_set = set(existing_follows)
            truly_new_follows = new_follows_set.difference(old_follows_set)

            # Save incremental updates if there are truly new follows
            if truly_new_follows:
                save_incremental_updates(username, truly_new_follows)

            # Always update the cumulative follows file
            save_cumulative_follows(username, new_follows)

            processed_members += 1
            remaining_members = total_members - processed_members
            logging.info(
                f"Processed {processed_members}/{total_members}. Remaining: {remaining_members}"
            )

        except Exception as e:
            logging.error(f"Error processing {username}: {e}")

    if new_data:
        save_new_data("following.csv", new_data)
        logging.info("Following data updated.")
    else:
        logging.info("No new followings to update.")
    # Log details of the output from the run in a file
    logging.info("Data collection complete. Check the output file.")

    driver.quit()


if __name__ == "__main__":
    main()
