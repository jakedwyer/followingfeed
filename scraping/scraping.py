from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import logging
import time
import random
import pickle

def init_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    logging.info(f"Using ChromeDriver version: {service.path}")  # Log the path to check version
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1920, 1080)
    logging.info("WebDriver initialized.")
    return driver

import datetime

def load_cookies(driver, cookie_path):
    driver.get("https://twitter.com")
    """Load cookies into Selenium WebDriver."""
    # Load the cookies from the file
    with open(cookie_path, "rb") as file:
        cookies = pickle.load(file)
    
    # Navigate to the correct domain before adding cookies
    driver.get("https://twitter.com")
    
    # Delete all existing cookies
    driver.delete_all_cookies()
    
    for cookie in cookies:
        # Ensure the cookie domain matches the current domain
        if 'domain' in cookie:
            del cookie['domain']
        driver.add_cookie(cookie)
    
    logging.info("Cookies loaded into WebDriver.")
    driver.refresh()



def get_following(driver, handle, existing_follows, max_accounts=None):
    """Fetch following accounts for a specific user using Selenium."""
    from selenium.webdriver.common.by import By

    url = f"https://twitter.com/{handle}/following"
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

    scroll_pause_time = random.randint(1, 5)  # Pause time to ensure page loading
    incremental_scroll = 100  # Gradual scroll to load more data
    extracted_handles = set(existing_follows)
    logging.info(f"Existing handles: {len(existing_follows)}")
    previous_handles_count = len(extracted_handles)

    try:
        while True:
            driver.execute_script(f"window.scrollBy(0, {incremental_scroll});")  # Scroll gradually
            time.sleep(scroll_pause_time)  # Wait for the page to load

            elements = driver.find_elements(
                By.XPATH, "//div[@aria-label='Timeline: Following']//a[contains(@href, '/')]"
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
