from airtop import Airtop
from selenium import webdriver
from selenium.webdriver.chrome.remote_connection import ChromeRemoteConnection
from typing import Any


def create_airtop_selenium_connection(
    airtop_api_key: str, airtop_session_data: Any, *args: Any, **kwargs: Any
):
    """Create a custom ChromeRemoteConnection for Airtop"""

    class AirtopRemoteConnection(ChromeRemoteConnection):
        @classmethod
        def get_remote_connection_headers(cls, *args: Any, **kwargs: Any):
            headers = super().get_remote_connection_headers(*args, **kwargs)
            headers["Authorization"] = f"Bearer {airtop_api_key}"
            return headers

    return AirtopRemoteConnection(
        remote_server_addr=airtop_session_data.chromedriver_url, *args, **kwargs
    )


def init_airtop_driver(
    api_key: str, client: Airtop, session: Any
) -> tuple[webdriver.Remote, Any]:
    """Initialize Selenium WebDriver with Airtop connection"""
    browser = webdriver.Remote(
        command_executor=create_airtop_selenium_connection(api_key, session.data),
        options=webdriver.ChromeOptions(),
    )

    # Get window info for the browser
    window_info = client.windows.get_window_info_for_selenium_driver(
        session.data,
        browser,
    )

    return browser, window_info
