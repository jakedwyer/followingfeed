import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from typing import Dict, List, Tuple, Optional, Any, Callable
from datetime import datetime
import time
import random
import pickle
import unicodedata
from twitter.twitter import fetch_twitter_data_api  # Add this line

# Set up logging
logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """Clean and normalize text."""
    decoded_text = text.encode('utf-8').decode('unicode-escape')
    normalized_text = unicodedata.normalize('NFKC', decoded_text)
    return ''.join(char for char in normalized_text if char.isprintable()).strip()


def scrape_twitter_profile(driver: webdriver.Chrome, username: str) -> Optional[Dict[str, Any]]:
    """Scrape Twitter profile data."""
    retry_count = 0
    while retry_count < 3:
        try:
            driver.get(f"https://x.com/{username}")
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="UserName"]')))
            
            profile_data = {"Username": username}

            def safe_get_text(selector):
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    return clean_text(element.text)
                except NoSuchElementException:
                    return None

            def safe_get_attribute(selector, attribute):
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    return element.get_attribute(attribute)
                except NoSuchElementException:
                    return None

            profile_data.update({
                "Full Name": safe_get_text('[data-testid="UserName"] div span span'),
                "Description": safe_get_text('[data-testid="UserDescription"]'),
                "Location": safe_get_text('[data-testid="UserProfileHeader_Items"] [data-testid="UserLocation"]'),
                "Website": safe_get_attribute('[data-testid="UserProfileHeader_Items"] [data-testid="UserUrl"]', "href"),
                "Join Date": safe_get_text('[data-testid="UserProfileHeader_Items"] [data-testid="UserJoinDate"]'),
                "Followers Count": safe_get_text('a[href$="/verified_followers"] span span'),
                "Listed Count": safe_get_text('a[href$="/lists"] span span'),
            })

            # Try to get Account ID
            try:
                account_id = driver.find_element(By.CSS_SELECTOR, '[data-testid="UserProfileHeader_Items"]').get_attribute('href').split('/')[-1]
                profile_data["Account ID"] = account_id
            except:
                pass

            # Remove None values
            profile_data = {k: v for k, v in profile_data.items() if v is not None}

            logger.info(f"Successfully scraped data for {username}")
            return profile_data

        except TimeoutException:
            if retry_count == 0:
                logger.warning(f"Timeout while loading profile for {username}. Retrying...")
                driver.refresh()
                time.sleep(5)
                retry_count += 1
            else:
                logger.error(f"Timeout while loading profile for {username} after retry.")
                return None
        except Exception as e:
            logger.error(f"Error scraping data for {username}: {e}")
            return None

    return None


def update_twitter_data(
    driver: webdriver.Chrome,
    existing_data: Dict[str, Any],
    unenriched_accounts: List[Tuple[str, str]],
    bearer_token: str,
    save_function: Callable
) -> Tuple[Dict[str, Any], int]:
    """Update Twitter data for unenriched accounts."""
    updated_count = 0

    for record_id, username in unenriched_accounts:
        username_lower = username.lower()
        
        if username_lower in existing_data:
            continue

        twitter_data = scrape_twitter_profile(driver, username)
        
        if twitter_data is not None:
            existing_data[username_lower] = {
                "data": twitter_data,
                "last_updated": datetime.now().isoformat()
            }
            save_function(username, twitter_data)
            updated_count += 1
            logging.info(f"Added new data for {username}")
            time.sleep(2)

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
    logging.info(f"Using ChromeDriver version: {service.path}")
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1920, 1080)
    logging.info("WebDriver initialized.")
    return driver


def load_cookies(driver: webdriver.Chrome, cookie_path: str) -> None:
    """Load cookies into Selenium WebDriver."""
    with open(cookie_path, "rb") as file:
        cookies = pickle.load(file)
    
    driver.get("https://x.com")
    driver.delete_all_cookies()
    
    for cookie in cookies:
        cookie.pop('domain', None)
        driver.add_cookie(cookie)
    
    logging.info("Cookies loaded into WebDriver.")
    driver.refresh()


def get_following(driver: webdriver.Chrome, handle: str, existing_follows: set, max_accounts: Optional[int] = None) -> List[str]:
    """Fetch following accounts for a specific user using Selenium."""
    url = f"https://x.com/{handle}/following"
    driver.get(url)
    logging.info(f"Fetching new following for {handle}")
    time.sleep(10)  # Initial wait for page load

    initial_elements = driver.find_elements(
        By.XPATH, "//div[@aria-label='Timeline: Following']//a[contains(@href, '/')]"
    )
    if not initial_elements:
        logging.error("No following links loaded on the page. Exiting function.")
        screenshot_path = f"screenshots/{handle}_following.png"
        driver.save_screenshot(screenshot_path)
        logging.info(f"Screenshot saved at {screenshot_path}")
        return list(existing_follows)

    extracted_handles = set(existing_follows)
    logging.info(f"Existing handles: {len(existing_follows)}")
    previous_handles_count = len(extracted_handles)

    try:
        while True:
            driver.execute_script("window.scrollBy(0, 100);")  # Scroll gradually
            time.sleep(random.uniform(1, 3))  # Random delay between 1 and 3 seconds
            time.sleep(random.randint(1, 5))  # Random pause to simulate human behavior

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
            logging.info(f"Found {len(new_handles)} new handles.")
            extracted_handles.update(new_handles)

            logging.info(f"Current total extracted handles: {len(extracted_handles)}")

            if len(extracted_handles) == previous_handles_count:
                logging.info("No new data to load or reached the end of the page.")
                break
            previous_handles_count = len(extracted_handles)

            if max_accounts and len(extracted_handles) >= max_accounts:
                logging.info(f"Reached max accounts limit of {max_accounts}")
                break

    except Exception as e:
        logging.error(f"An error occurred while fetching following for {handle}: {e}")

    return list(extracted_handles)