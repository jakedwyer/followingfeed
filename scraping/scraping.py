import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from typing import Dict, List, Tuple, Optional, Any, Callable, Union
from datetime import datetime
import time
import random
import pickle
import unicodedata
from twitter.twitter import fetch_twitter_data_api  # Add this line

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def retry_with_backoff(func, max_retries=5, initial_wait=1, max_wait=60):
    def wrapper(*args, **kwargs):
        wait = initial_wait
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except TimeoutException:
                if attempt == max_retries - 1:
                    logger.error(f"Max retries ({max_retries}) reached for {func.__name__}. Raising exception.")
                    raise
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed. Retrying in {wait} seconds.")
                time.sleep(wait)
                wait = min(wait * 2, max_wait)
        logger.error(f"All {max_retries} attempts failed for {func.__name__}.")
    return wrapper

@retry_with_backoff
def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not isinstance(text, str):
        logger.warning(f"Expected string, got {type(text)}. Converting to string.")
        text = str(text)
    decoded_text = text.encode('utf-8').decode('unicode_escape')
    normalized_text = unicodedata.normalize('NFKC', decoded_text)
    return ''.join(char for char in normalized_text if char.isprintable()).strip()

DELETE_RECORD_INDICATOR = "DELETE_RECORD"

@retry_with_backoff
def scrape_twitter_profile(driver: webdriver.Chrome, username: str) -> Union[Dict[str, Any], str, None]:
    """Scrape Twitter profile data."""
    logger.info(f"Attempting to scrape profile for {username}")
    try:
        driver.get(f"https://x.com/{username}")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="UserName"]')))
        
        profile_data: Dict[str, Optional[str]] = {"Username": username}

        def safe_get_text(selector: str) -> Optional[str]:
            try:
                element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                return clean_text(element.text)
            except (NoSuchElementException, TimeoutException):
                logger.warning(f"Element not found: {selector}")
                return None

        def safe_get_attribute(selector: str, attribute: str) -> Optional[str]:
            try:
                element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                return element.get_attribute(attribute)
            except (NoSuchElementException, TimeoutException):
                logger.warning(f"Element not found: {selector}")
                return None

        profile_data.update({
            "Full Name": safe_get_text('[data-testid="UserName"] div span span'),
            "Description": safe_get_text('[data-testid="UserDescription"]'),
            "Location": safe_get_text('[data-testid="UserProfileHeader_Items"] [data-testid="UserLocation"]'),
            "Website": safe_get_attribute('[data-testid="UserProfileHeader_Items"] [data-testid="UserUrl"]', "href"),
            "Created At": safe_get_text('[data-testid="UserProfileHeader_Items"] [data-testid="UserJoinDate"]'),
            "Followers Count": safe_get_text('a[href$="/verified_followers"] span span'),
            "Listed Count": safe_get_text('a[href$="/lists"] span span'),
        })

        # Try to get Account ID
        try:
            account_id_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="UserProfileHeader_Items"]')))
            account_id = account_id_element.get_attribute('href')
            if account_id:
                profile_data["Account ID"] = account_id.split('/')[-1]
        except (NoSuchElementException, TimeoutException, AttributeError) as e:
            logger.warning(f"Failed to get Account ID: {str(e)}")

        # Remove None values
        profile_data = {k: v for k, v in profile_data.items() if v is not None}

        logger.info(f"Successfully scraped data for {username}")
        return profile_data

    except TimeoutException:
        logger.warning(f"Timeout waiting for UserName element for {username} after all retries. Marking for deletion.")
        return DELETE_RECORD_INDICATOR
    except Exception as e:
        logger.error(f"Error scraping profile for {username}: {str(e)}", exc_info=True)
        return None

def update_twitter_data(
    driver: webdriver.Chrome,
    existing_data: Dict[str, Any],
    unenriched_accounts: List[Tuple[str, str]],
    bearer_token: str,
    save_function: Callable[[str, Dict[str, Any]], None]
) -> Tuple[Dict[str, Any], int]:
    """Update Twitter data for unenriched accounts."""
    updated_count = 0

    for record_id, username in unenriched_accounts:
        username_lower = username.lower()
        
        if username_lower in existing_data:
            continue

        try:
            twitter_data = scrape_twitter_profile(driver, username)
            
            if twitter_data is not None and twitter_data != DELETE_RECORD_INDICATOR:
                existing_data[username_lower] = {
                    "data": twitter_data,
                    "last_updated": datetime.now().isoformat()
                }
                save_function(username, existing_data[username_lower])
                updated_count += 1
                logger.info(f"Added new data for {username}")
                time.sleep(random.uniform(2, 5))  # Random delay between 2 and 5 seconds
            elif twitter_data == DELETE_RECORD_INDICATOR:
                logger.warning(f"Marking {username} for deletion")
            else:
                logger.warning(f"Failed to scrape data for {username}")
        except Exception as e:
            logger.error(f"Error processing {username}: {str(e)}", exc_info=True)

    return existing_data, updated_count

def init_driver() -> webdriver.Chrome:
    """Initialize and configure Chrome WebDriver."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    logger.info(f"Using ChromeDriver version: {service.path}")
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
        
        for cookie in cookies:
            cookie.pop('domain', None)
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                logger.warning(f"Failed to add cookie: {str(e)}")
        
        logger.info("Cookies loaded into WebDriver.")
        driver.refresh()
    except Exception as e:
        logger.error(f"Error loading cookies: {str(e)}", exc_info=True)

@retry_with_backoff
def get_following(driver: webdriver.Chrome, handle: str, existing_follows: set, max_accounts: Optional[int] = None) -> List[str]:
    """Fetch following accounts for a specific user using Selenium."""
    url = f"https://x.com/{handle}/following"
    driver.get(url)
    logger.info(f"Fetching new following for {handle}")
    time.sleep(10)  # Initial wait for page load

    initial_elements = driver.find_elements(
        By.XPATH, "//div[@aria-label='Timeline: Following']//a[contains(@href, '/')]"
    )
    if not initial_elements:
        logger.error("No following links loaded on the page. Exiting function.")
        screenshot_path = f"screenshots/{handle}_following.png"
        driver.save_screenshot(screenshot_path)
        logger.info(f"Screenshot saved at {screenshot_path}")
        return list(existing_follows)

    extracted_handles = set(existing_follows)
    logger.info(f"Existing handles: {len(existing_follows)}")
    previous_handles_count = len(extracted_handles)

    try:
        while True:
            driver.execute_script("window.scrollBy(0, 100);")  # Scroll gradually
            time.sleep(random.uniform(1, 5))  # Random delay between 1 and 5 seconds

            elements = driver.find_elements(
                By.XPATH, "//div[@aria-label='Timeline: Following']//a[contains(@href, '/')]"
            )
            current_handles = {
                href.split("/")[-1]
                for el in elements
                if (href := el.get_attribute("href")) and href.startswith("https://x.com/")
                and href is not None
                and "/following" not in href
                and "search?q=" not in href
            }

            new_handles = current_handles - extracted_handles
            logger.info(f"Found {len(new_handles)} new handles.")
            extracted_handles.update(new_handles)

            logger.info(f"Current total extracted handles: {len(extracted_handles)}")

            if len(extracted_handles) == previous_handles_count:
                logger.info("No new data to load or reached the end of the page.")
                break
            previous_handles_count = len(extracted_handles)

            if max_accounts and len(extracted_handles) >= max_accounts:
                logger.info(f"Reached max accounts limit of {max_accounts}")
                break

    except Exception as e:
        logger.error(f"An error occurred while fetching following for {handle}: {e}", exc_info=True)

    return list(extracted_handles)