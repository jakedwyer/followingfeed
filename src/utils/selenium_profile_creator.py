from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from src.utils.session_manager import TwitterSessionManager
import os
import json
from datetime import datetime


class TwitterProfileCreator:
    def __init__(self, api_key: str):
        self.session_manager = TwitterSessionManager(api_key)
        self.driver = None
        self.profile_id = None

    def create_selenium_session(self, chromedriver_url: str):
        """Set up Selenium with the Airtop session"""
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")

        self.driver = webdriver.Remote(
            command_executor=chromedriver_url, options=chrome_options
        )

    async def login_to_twitter(self, username: str, password: str):
        """Handle Twitter login process"""
        try:
            if not self.driver:
                raise Exception("Selenium driver not initialized")

            self.driver.get("https://twitter.com/login")

            # Wait for and fill username
            username_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "text"))
            )
            username_input.send_keys(username)
            # Click next
            next_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']"))
            )
            next_button.click()

            # Wait for and fill password
            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            password_input.send_keys(password)
            # Click login
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Log in']"))
            )
            login_button.click()

            # Wait for successful login
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//a[@aria-label='Profile']"))
            )

            return True
        except Exception as e:
            print(f"Login failed: {str(e)}")
            return False

    async def create_and_save_profile(self, username: str, password: str):
        """Create a new session with profile persistence and perform login"""
        try:
            # Create session with profile persistence enabled
            print("Creating session...")
            session = self.session_manager.create_session(
                timeout_minutes=15, persist_profile=True
            )
            print(f"Session created: {session}")

            # Set up Selenium with the chromedriver URL
            if "chromedriver_url" not in session:
                raise ValueError("No chromedriver URL in session response")

            print("Setting up Selenium...")
            self.create_selenium_session(session["chromedriver_url"])

            # Perform login
            print("Attempting Twitter login...")
            login_success = await self.login_to_twitter(username, password)

            if login_success:
                self.profile_id = session.get("profile_id")
                if not self.profile_id:
                    raise ValueError("No profile ID received from session")

                # Save profile information to a JSON file
                profile_info = {
                    "profile_id": self.profile_id,
                    "username": username,
                    "created_at": datetime.now().isoformat(),
                }

                with open("twitter_profile.json", "w") as f:
                    json.dump(profile_info, f)

                print(
                    f"Profile created and saved successfully. Profile ID: {self.profile_id}"
                )
                return self.profile_id

            return None
        except Exception as e:
            print(f"Error in create_and_save_profile: {str(e)}")
            raise
        finally:
            try:
                if self.driver:
                    self.driver.quit()
                if (
                    hasattr(self.session_manager, "session_id")
                    and self.session_manager.session_id
                ):
                    self.session_manager.terminate_session()
            except Exception as e:
                print(f"Error during cleanup: {str(e)}")

    def get_saved_profile(self):
        """Get the saved profile information"""
        try:
            with open("twitter_profile.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
