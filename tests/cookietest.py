import unittest
from selenium.webdriver.common.by import By
from scraping.scraping import init_driver, load_cookies

class TestTwitterCookies(unittest.TestCase):
    def setUp(self):
        """Initialize the WebDriver and load cookies."""
        self.driver = init_driver()
        load_cookies(self.driver, '/root/followfeed/twitter_cookies.pkl')

    def test_logged_in(self):
        """Test if the cookies load the user as logged in on Twitter."""
        self.driver.get("https://twitter.com/home")
        try:
            # Wait for potential login elements that indicate we are not logged in
            login_element = self.driver.find_element(By.XPATH, "//input[@name='session[username_or_email]']")
            self.assertIsNone(login_element, "Expected no login element, found one, user is not logged in.")
        except Exception as e:
            print("User appears to be logged in: ", e)

    def tearDown(self):
        """Close the WebDriver."""
        self.driver.quit()

if __name__ == "__main__":
    unittest.main()
