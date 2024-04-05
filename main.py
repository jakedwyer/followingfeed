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

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO)
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


# Twitter API Authentication
def authenticate_twitter_api():
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True)
    try:
        api.verify_credentials()
        print("Authentication OK")
        return api
    except Exception as e:
        print(f"Error during authentication: {e}")
        return None


# Fetch List Members
def fetch_list_members(list_id):
    url = f"https://api.twitter.com/2/lists/{list_id}/members"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        members_data = response.json()
        print(members_data)
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
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service("/usr/local/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1920, 1080)
    print("WebDriver Initialized")
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
    time.sleep(5)

    scroll_pause_time = 10  # Increased pause time to ensure page loading
    incremental_scroll = 100  # Gradual scroll to load more data
    last_height = driver.execute_script("return document.body.scrollHeight")
    logging.info("Scrolling to the bottom of the page to load all data.")
    extracted_handles = set(existing_follows)
    logging.info(f"Existing handles: {len(existing_follows)}")
    try:
        while True:
            driver.execute_script(
                f"window.scrollBy(0, {incremental_scroll});"
            )  # Gradual scrolling
            time.sleep(scroll_pause_time)  # Wait for the page to load
            new_height = driver.execute_script("return document.body.scrollHeight")

            if new_height == last_height:
                logging.info("Reached the bottom of the page or no new data to load.")
                break
            last_height = new_height

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
            logging.info(f"Esisting follows: {existing_follows}")
            new_follows = get_following(
                driver, username, existing_follows, max_accounts=None
            )
            if set(new_follows) != existing_follows:
                new_data[username] = new_follows

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
