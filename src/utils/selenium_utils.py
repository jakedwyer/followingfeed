from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from typing import Optional
import json


def get_selenium_driver(
    chromedriver_url: str, profile_id: Optional[str] = None
) -> webdriver.Remote:
    """
    Create a Selenium driver with the saved profile
    """
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")

    if profile_id:
        chrome_options.add_argument(f"--profile-id={profile_id}")

    driver = webdriver.Remote(command_executor=chromedriver_url, options=chrome_options)

    return driver


def get_saved_profile_id() -> Optional[str]:
    """
    Get the saved profile ID from the JSON file
    """
    try:
        with open("twitter_profile.json", "r") as f:
            profile_data = json.load(f)
            return profile_data.get("profile_id")
    except FileNotFoundError:
        return None
