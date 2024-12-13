import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime
import time
import random
import pickle
import unicodedata
import re
from fake_useragent import UserAgent
from utils.user_data import update_user_details, get_user_details
from utils.airtable import (
    prepare_update_record,
    update_airtable,
    delete_airtable_record,
    fetch_existing_follows,
    fetch_and_update_accounts,
    update_followers_field,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DELETE_RECORD_INDICATOR = "DELETE_RECORD"


def retry_with_backoff(func):
    def wrapper(*args, max_retries=5, initial_wait=1, max_wait=60, **kwargs):
        wait = initial_wait
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except TimeoutException:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Max retries ({max_retries}) reached for {func.__name__}. Raising exception."
                    )
                    raise
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed. Retrying in {wait} seconds."
                )
                time.sleep(wait)
                wait = min(wait * 2, max_wait)
        logger.error(f"All {max_retries} attempts failed for {func.__name__}.")

    return wrapper


@retry_with_backoff
def clean_text(text: str) -> str:
    """
    Normalize and clean text, preserving special characters and ensuring proper encoding.
    """
    if not isinstance(text, str):
        logger.warning(f"Expected string, got {type(text)}. Converting to string.")
        text = str(text)

    # Normalize Unicode characters using NFC to preserve characters as they are
    text = unicodedata.normalize("NFC", text)

    # Replace common HTML entities if they appear in the text
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

    # Remove unwanted control characters while preserving necessary ones (like newlines and tabs)
    text = "".join(
        c for c in text if unicodedata.category(c)[0] != "C" or c in ("\n", "\t")
    )

    # Normalize whitespace within each line but preserve line breaks
    lines = text.split("\n")
    cleaned_lines = [re.sub(r"\s+", " ", line).strip() for line in lines]
    cleaned_text = "\n".join(cleaned_lines)

    return cleaned_text


def parse_date(date_str: str) -> str:
    try:
        # Try parsing as ISO format
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        try:
            # Try parsing "Joined Month Year" format
            dt = datetime.strptime(date_str.replace("Joined ", ""), "%B %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            # If parsing fails, return an empty string
            return ""


def parse_numeric_value(value: str) -> int:
    if not value:
        return 0
    value = value.replace(",", "").strip().lower()
    if value.endswith("k"):
        return int(float(value[:-1]) * 1000)
    elif value.endswith("m"):
        return int(float(value[:-1]) * 1000000)
    try:
        return int(float(value))
    except ValueError:
        return 0


def normalize_username(username: str) -> str:
    """
    Normalize the username to ensure consistency.
    - Lowercase
    - Strip leading/trailing whitespace
    """
    return username.strip().lower()


@retry_with_backoff
def scrape_twitter_profile(
    driver: webdriver.Chrome, username: str
) -> Union[Dict[str, Any], str, None]:
    """Scrape Twitter profile data."""
    username = normalize_username(username)  # Ensures consistency
    logger.info(f"Attempting to scrape profile for {username}")
    try:
        driver.get(f"https://x.com/{username}")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, '[data-testid="UserName"]')
            )
        )

        profile_data: Dict[str, Optional[Union[str, int]]] = {"Username": username}

        def safe_get_element(
            selector: str, get_attribute: Optional[str] = None
        ) -> Optional[str]:
            try:
                element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if get_attribute:
                    attr_value = element.get_attribute(get_attribute)
                    return clean_text(attr_value) if attr_value is not None else None
                return clean_text(element.text) if element.text is not None else None
            except (NoSuchElementException, TimeoutException):
                logger.warning(f"Element not found: {selector}")
                return None

        # Extract Full Name
        profile_data["Full Name"] = safe_get_element(
            '[data-testid="UserName"] div span span'
        )

        # Extract Description
        profile_data["Description"] = safe_get_element(
            '[data-testid="UserDescription"]'
        )

        # Extract Location
        profile_data["Location"] = safe_get_element(
            '[data-testid="UserProfileHeader_Items"] [data-testid="UserLocation"]'
        )

        # Extract Website
        profile_data["Website"] = safe_get_element(
            '[data-testid="UserProfileHeader_Items"] [data-testid="UserUrl"]', "href"
        )

        # Extract Join Date and map to Created At
        join_date = safe_get_element(
            '[data-testid="UserProfileHeader_Items"] [data-testid="UserJoinDate"]'
        )
        parsed_date = parse_date(join_date) if join_date else ""
        if parsed_date:
            profile_data["Created At"] = parsed_date

        # Extract Followers Count
        profile_data["Followers Count"] = parse_numeric_value(
            safe_get_element('a[href$="/verified_followers"] span span') or "0"
        )

        # Extract Following Count
        profile_data["Following Count"] = parse_numeric_value(
            safe_get_element('a[href$="/following"] span span') or "0"
        )

        # Extract Profile Image URL
        profile_image = safe_get_element(
            '[data-testid="UserAvatar-Container-HadickM"] img', "src"
        )
        profile_data["Profile Image URL"] = profile_image

        # Check Verified Status
        verified_button = driver.find_elements(
            By.CSS_SELECTOR, '[aria-label="Provides details about verified accounts."]'
        )
        profile_data["Verified"] = bool(verified_button)

        # Remove None values
        profile_data = {k: v for k, v in profile_data.items() if v is not None}

        logger.info(f"Successfully scraped data for {username}")
        return profile_data

    except TimeoutException:
        logger.warning(
            f"Timeout waiting for UserName element for {username} after all retries. Marking for deletion."
        )
        return DELETE_RECORD_INDICATOR
    except Exception as e:
        logger.error(f"Error scraping profile for {username}: {str(e)}", exc_info=True)
        return None


def update_twitter_data(
    driver: webdriver.Chrome,
    unenriched_accounts: List[Tuple[str, str]],
    airtable_token: str,
    base_id: str,
    table_id: str,
) -> Dict[str, Dict[str, Any]]:
    updated_count = 0
    records_to_update = []
    enriched_data = {}

    headers = {
        "Authorization": f"Bearer {airtable_token}",
        "Content-Type": "application/json",
    }

    for record_id, username in unenriched_accounts:
        username_lower = normalize_username(username)  # Ensures consistency
        if get_user_details(username_lower):
            continue

        try:
            twitter_data = scrape_twitter_profile(driver, username_lower)

            if (
                isinstance(twitter_data, dict)
                and twitter_data != DELETE_RECORD_INDICATOR
            ):
                # Clean data
                if "Created At" in twitter_data and not twitter_data["Created At"]:
                    del twitter_data["Created At"]

                update_user_details(username_lower, twitter_data)
                enriched_data[username_lower] = twitter_data
                updated_count += 1
                logging.info(f"Added new data for {username_lower}")

                # Prepare Airtable update
                update_record = prepare_update_record(
                    record_id, username_lower, {"data": twitter_data}, {}
                )
                if update_record:
                    records_to_update.append(update_record)

                random_delay(2, 5)
            elif twitter_data == DELETE_RECORD_INDICATOR:
                delete_airtable_record(record_id)
            else:
                logging.warning(f"Failed to scrape data for {username_lower}")
        except Exception as e:
            logging.error(f"Error processing {username_lower}: {str(e)}", exc_info=True)

    # Bulk update Airtable after scraping
    if records_to_update:
        success = update_airtable(records_to_update, headers)
        if success:
            logging.info(
                f"Updated {len(records_to_update)} records in Airtable successfully."
            )
        else:
            logging.error("Some batches failed to update in Airtable.")

    logging.info(f"Processed {updated_count} new handles for Twitter data enrichment.")
    return enriched_data


def init_driver() -> webdriver.Chrome:
    """Initialize and configure Chrome WebDriver."""
    options = Options()
    options.add_argument("--headless=new")  # New headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("window-size=1920x1080")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--incognito")
    options.add_argument(f"user-agent={UserAgent().random}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1920, 1080)
    logger.info("WebDriver initialized.")
    return driver


def load_cookies(driver: webdriver.Chrome, cookie_path: str) -> None:
    """Load cookies into Selenium WebDriver."""
    try:
        with open(cookie_path, "rb") as file:
            cookies = pickle.load(file)

        driver.get("https://x.com")
        driver.delete_all_cookies()

        loaded_cookies = 0
        for cookie in cookies:
            cookie.pop("domain", None)
            try:
                driver.add_cookie(cookie)
                loaded_cookies += 1
            except Exception as e:
                logger.warning(f"Failed to add cookie: {str(e)}")

        logger.info(f"Loaded {loaded_cookies} cookies into WebDriver.")
        driver.refresh()
    except FileNotFoundError:
        logger.error(f"Cookie file not found at {cookie_path}")
    except Exception as e:
        logger.error(f"Error loading cookies: {str(e)}", exc_info=True)


@retry_with_backoff
def get_following(
    driver: webdriver.Chrome,
    handle: str,
    existing_follows: set,
    max_accounts: Optional[int] = None,
) -> List[str]:
    """Fetch following accounts for a specific user using Selenium."""
    handle = handle.lower()  # Ensure username consistency
    url = f"https://x.com/{handle}/following"
    driver.get(url)
    logger.info(f"Fetching new following for {handle}")

    # Random initial wait between 5-15 seconds
    time.sleep(random.uniform(5, 15))

    initial_elements = driver.find_elements(
        By.XPATH, "//div[@aria-label='Timeline: Following']//a[contains(@href, '/')]"
    )
    if not initial_elements:
        logger.error("No following links loaded on the page. Exiting function.")
        screenshot_path = f"screenshots/{handle}_following.png"
        driver.save_screenshot(screenshot_path)
        logger.info(f"Screenshot saved at {screenshot_path}")
        return []

    normalized_existing = {normalize_username(ef) for ef in existing_follows}
    logger.info(f"Existing handles: {len(existing_follows)}")

    new_follows = set()
    previous_total = 0
    no_new_data_count = 0
    scroll_height = 0

    try:
        while True:
            # Random scroll amount between 100-300 pixels
            scroll_amount = random.randint(100, 300)
            scroll_height += scroll_amount

            # Occasionally scroll up a bit to simulate human behavior
            if random.random() < 0.1:  # 10% chance
                scroll_height -= random.randint(50, 150)
                driver.execute_script(f"window.scrollTo(0, {max(0, scroll_height)});")
                time.sleep(random.uniform(0.5, 1.5))

            # Scroll down with smooth behavior
            driver.execute_script(
                f"window.scrollTo({{top: {scroll_height}, behavior: 'smooth'}});"
            )

            # Random pause between scrolls (longer than before)
            time.sleep(random.uniform(2, 4))

            # Occasionally take a longer pause
            if random.random() < 0.15:  # 15% chance
                time.sleep(random.uniform(4, 8))

            elements = driver.find_elements(
                By.XPATH,
                "//div[@aria-label='Timeline: Following']//a[contains(@href, '/')]",
            )
            current_handles = {
                normalize_username(href.split("/")[-1])
                for el in elements
                if (href := el.get_attribute("href"))
                and href.startswith("https://x.com/")
                and href is not None
                and "/following" not in href
                and "search?q=" not in href
            }

            # Only keep handles we haven't seen before
            new_handles = current_handles - normalized_existing - new_follows
            if new_handles:
                logger.info(f"Found {len(new_handles)} new handles.")
                new_follows.update(new_handles)
                no_new_data_count = 0  # Reset counter when we find new handles
            else:
                no_new_data_count += 1

            logger.info(f"Current total new handles: {len(new_follows)}")

            # Check if we've reached the end (multiple checks with no new data)
            if no_new_data_count >= 3:
                logger.info(
                    "No new data found after multiple attempts. Likely reached the end."
                )
                break

            if len(new_follows) == previous_total:
                # Take a longer pause and try one more time before giving up
                time.sleep(random.uniform(5, 10))
                continue

            previous_total = len(new_follows)

            if max_accounts and len(new_follows) >= max_accounts:
                logger.info(f"Reached max accounts limit of {max_accounts}")
                break

            # Check if we've hit Twitter's rate limit or other issues
            if "rate-limit" in driver.current_url or "error" in driver.current_url:
                logger.warning("Detected potential rate limiting or error page")
                time.sleep(60)  # Wait a minute before continuing
                driver.get(url)  # Reload the page
                time.sleep(random.uniform(5, 10))

    except Exception as e:
        logger.error(
            f"An error occurred while fetching following for {handle}: {e}",
            exc_info=True,
        )

    # Final random pause before returning
    time.sleep(random.uniform(2, 5))
    return list(new_follows)


def random_delay(min_seconds: int, max_seconds: int) -> None:
    """Introduce a random delay between min_seconds and max_seconds."""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def process_user(
    username: str,
    follower_record_id: str,
    driver: webdriver.Chrome,
    headers: Dict[str, str],
    accounts: Dict[str, str],
    record_id_to_username: Dict[str, str],
) -> tuple[Dict[str, str], int]:
    """
    Process a user's following list and update Airtable accordingly.
    """
    existing_follows = fetch_existing_follows(
        follower_record_id, headers, record_id_to_username
    )
    logging.info(f"Existing follows for {username}: {len(existing_follows)}")

    new_follows = get_following(driver, username, existing_follows)
    all_follows = {
        normalize_username(uname) for uname in existing_follows.union(new_follows)
    }
    logging.info(f"Total follows for {username}: {len(all_follows)}")

    # Update accounts dictionary with any new accounts
    accounts = fetch_and_update_accounts(all_follows, headers, accounts)

    # Get account IDs for all follows
    followed_account_ids = []
    missing_accounts = []
    for uname in all_follows:
        if uname in accounts:
            followed_account_ids.append(accounts[uname])
        else:
            missing_accounts.append(uname)
            logging.warning(f"Account not found: {uname}")

    if missing_accounts:
        logging.error(f"Missing accounts: {missing_accounts}")

    # Update follower record with ALL account IDs
    if followed_account_ids:
        success = update_followers_field(
            follower_record_id, followed_account_ids, headers
        )
        if success:
            logging.info(
                f"Successfully updated follower {username} with {len(followed_account_ids)} accounts."
            )
        else:
            logging.error(f"Failed to update follower {username} with accounts.")

    return accounts, len(new_follows)
