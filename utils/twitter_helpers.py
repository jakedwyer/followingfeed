import logging
from typing import Dict, Any, Optional, Set
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
from utils.helpers import normalize_username

logger = logging.getLogger(__name__)


def get_following(
    driver: WebDriver,
    handle: str,
    existing_follows: Set[str],
    max_accounts: Optional[int] = None,
) -> Set[str]:
    """
    Fetch following accounts for a specific user using Selenium.
    """
    handle = normalize_username(handle)
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
        return set(existing_follows)

    extracted_handles = set(existing_follows)
    logger.info(f"Existing handles: {len(existing_follows)}")
    previous_handles_count = len(extracted_handles)

    try:
        while True:
            driver.execute_script("window.scrollBy(0, 100);")
            time.sleep(random.uniform(1, 5))

            elements = driver.find_elements(
                By.XPATH,
                "//div[@aria-label='Timeline: Following']//a[contains(@href, '/')]",
            )
            current_handles = {
                href.split("/")[-1]
                for el in elements
                if (href := el.get_attribute("href"))
                and href.startswith("https://x.com/")
                and href is not None
                and "/following" not in href
                and "search?q=" not in href
            }

            new_handles = current_handles - extracted_handles
            logger.info(f"Found {len(new_handles)} new handles.")
            extracted_handles.update(new_handles)

            if len(extracted_handles) == previous_handles_count:
                logger.info("No new data to load or reached the end of the page.")
                break
            previous_handles_count = len(extracted_handles)

            if max_accounts and len(extracted_handles) >= max_accounts:
                logger.info(f"Reached max accounts limit of {max_accounts}")
                break

    except Exception as e:
        logger.error(
            f"An error occurred while fetching following for {handle}: {e}",
            exc_info=True,
        )

    return extracted_handles
