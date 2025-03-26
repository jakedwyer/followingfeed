import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from fake_useragent import UserAgent
import os
import tempfile
import shutil
import atexit

logger = logging.getLogger(__name__)


def init_driver() -> webdriver.Chrome:
    """Initialize Chrome WebDriver with appropriate options."""
    # Create a unique temporary directory
    temp_dir = tempfile.mkdtemp(prefix="chrome_")

    # Register cleanup on exit
    def cleanup():
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    atexit.register(cleanup)

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280,720")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-javascript")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument(f"--user-data-dir={temp_dir}")
    chrome_options.page_load_strategy = "eager"
    chrome_options.add_argument(f"user-agent={UserAgent().random}")

    # Set binary location explicitly
    chrome_binary = os.environ.get("CHROME_BIN", "/usr/bin/google-chrome")
    if os.path.exists(chrome_binary):
        chrome_options.binary_location = chrome_binary

    # Set ChromeDriver path explicitly
    chromedriver_path = os.environ.get(
        "CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver"
    )
    if not os.path.exists(chromedriver_path):
        logger.error(f"ChromeDriver not found at {chromedriver_path}")
        raise FileNotFoundError(f"ChromeDriver not found at {chromedriver_path}")

    service = Service(executable_path=chromedriver_path)

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("WebDriver initialized successfully.")
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize WebDriver: {str(e)}")
        # Log more detailed information for debugging
        logger.error(f"Chrome binary location: {chrome_binary}")
        logger.error(f"ChromeDriver path: {chromedriver_path}")
        logger.error(
            f"Chrome version: {os.popen('google-chrome --version').read().strip()}"
        )
        logger.error(
            f"ChromeDriver version: {os.popen('chromedriver --version').read().strip()}"
        )
        cleanup()  # Clean up on error
        raise
