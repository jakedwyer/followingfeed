import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.remote_connection import ChromeRemoteConnection
from airtop import Airtop
from typing import Tuple, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class AirtopRemoteConnection(ChromeRemoteConnection):
    """Custom Remote Connection for Airtop with authentication."""

    def __init__(self, airtop_api_key, remote_server_addr, *args, **kwargs):
        super().__init__(remote_server_addr, *args, **kwargs)
        self.airtop_api_key = airtop_api_key

    def get_remote_connection_headers(self, *args, **kwargs):
        """Get headers with authentication for Airtop."""
        headers = super().get_remote_connection_headers(*args, **kwargs)
        headers["Authorization"] = f"Bearer {self.airtop_api_key}"
        return headers


def wait_for_session_ready(client: Any, session_id: str, max_retries: int = 15) -> bool:
    """Wait for Airtop session to be fully ready."""
    for attempt in range(max_retries):
        try:
            session_info = client.sessions.get_info(session_id)
            status = session_info.data.status
            logger.info(
                f"Session status: {status}. Attempt {attempt + 1}/{max_retries}"
            )

            if status == "running":
                logger.info("Session is ready")
                return True
            elif status in ["initializing", "awaiting_capacity"]:
                time.sleep(2)  # Increased wait time between checks
            else:
                logger.error(f"Unexpected session status: {status}")
                return False
        except Exception as e:
            logger.error(
                f"Error checking session status (attempt {attempt + 1}): {str(e)}"
            )
            time.sleep(2)
    return False


def init_airtop_driver(
    api_key: str, client: Airtop, session, max_retries: int = 3
) -> Tuple[webdriver.Remote, Any]:
    """Initialize Selenium WebDriver with Airtop integration"""
    for attempt in range(max_retries):
        try:
            # Create custom command executor
            command_executor = AirtopRemoteConnection(
                airtop_api_key=api_key, remote_server_addr=session.data.chromedriver_url
            )

            # Initialize Chrome options
            chrome_options = webdriver.ChromeOptions()

            # Create Remote WebDriver
            driver = webdriver.Remote(
                command_executor=command_executor, options=chrome_options
            )

            # Get window info
            window_info = client.windows.get_window_info_for_selenium_driver(
                session.data, driver
            )

            return driver, window_info

        except Exception as e:
            if attempt == max_retries - 1:
                raise Exception(
                    f"Failed to initialize Airtop driver after {max_retries} attempts: {str(e)}"
                )
            continue

    raise Exception("Failed to initialize Airtop driver")


def cleanup_airtop_session(
    client: Any, session_id: Optional[str], driver: Optional[webdriver.Remote] = None
) -> None:
    """Clean up Airtop session and resources."""
    try:
        if driver:
            logger.info("Closing WebDriver...")
            driver.quit()

        if session_id:
            logger.info(f"Terminating Airtop session: {session_id}")
            client.sessions.terminate(session_id)
            logger.info("Session terminated successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
