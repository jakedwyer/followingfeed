# selenium_helpers/browser.py
import asyncio
import logging
import os
import pickle
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException

from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

async def get_webdriver_async() -> webdriver.Chrome:
    """
    Initialize and return a Selenium WebDriver instance asynchronously.

    Returns:
        webdriver.Chrome: The Selenium WebDriver instance.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, initialize_webdriver)

def initialize_webdriver():
    """
    Synchronously initialize the Selenium WebDriver.

    Returns:
        webdriver.Chrome: The Selenium WebDriver instance.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=9222")

    # Specify the major version of Chrome
    chrome_major_version = "125"
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    logger.info("Selenium WebDriver initialized successfully.")
    return driver

async def close_webdriver_async(driver: webdriver.Chrome) -> None:
    """
    Close the Selenium WebDriver asynchronously.

    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, driver.quit)
    logger.info("Selenium WebDriver closed.")

async def load_cookies_async(driver: webdriver.Chrome, cookie_path: str) -> None:
    """
    Load cookies into the Selenium WebDriver asynchronously from a pickle file.

    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance.
        cookie_path (str): Path to the cookies pickle file.
    """
    if not os.path.exists(cookie_path):
        logger.warning(f"Cookie file {cookie_path} does not exist.")
        return

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, sync_load_cookies, driver, cookie_path)
    logger.info("Cookies loaded successfully.")

def sync_load_cookies(driver: webdriver.Chrome, cookie_path: str) -> None:
    """
    Synchronously load cookies into the Selenium WebDriver.

    Args:
        driver (webdriver.Chrome): The Selenium WebDriver instance.
        cookie_path (str): Path to the cookies pickle file.
    """
    try:
        with open(cookie_path, 'rb') as f:
            cookies = pickle.load(f)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                logger.error(f"Error adding cookie: {e}")
    except Exception as e:
        logger.exception(f"Failed to load cookies from {cookie_path}: {e}")