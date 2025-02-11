import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os
import sys

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_chrome_setup():
    try:
        logger.info("Starting Chrome setup test...")

        # Print environment info
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Current working directory: {os.getcwd()}")

        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # Use new headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")

        # Log Chrome binary location
        chrome_binary = "/usr/bin/google-chrome"
        logger.info(f"Chrome binary location: {chrome_binary}")
        chrome_options.binary_location = chrome_binary

        # Set up ChromeDriver service
        chromedriver_path = "/usr/local/bin/chromedriver"
        logger.info(f"ChromeDriver path: {chromedriver_path}")
        service = Service(executable_path=chromedriver_path)

        # Initialize WebDriver with detailed logging
        logger.info("Initializing WebDriver...")
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Test basic functionality
        logger.info("Testing basic functionality...")
        driver.get("https://example.com")
        logger.info(f"Page title: {driver.title}")

        # Clean up
        driver.quit()
        logger.info("Test completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Error during Chrome setup test: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = test_chrome_setup()
    sys.exit(0 if success else 1)
