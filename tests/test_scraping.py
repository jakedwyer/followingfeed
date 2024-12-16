import unittest
import os
from scraping.scraping import init_driver, verify_driver_health


class TestScraping(unittest.TestCase):
    driver = None

    @classmethod
    def setUpClass(cls):
        """Initialize a single ChromeDriver instance for all tests."""
        if not cls.driver:
            cls.driver = init_driver(show_browser=False)

    @classmethod
    def tearDownClass(cls):
        """Clean up the ChromeDriver instance after all tests."""
        if cls.driver:
            try:
                cls.driver.quit()
            except Exception:
                pass  # Ignore errors during cleanup
            finally:
                cls.driver = None

    def setUp(self):
        """Verify driver health before each test."""
        self.assertTrue(verify_driver_health(self.driver), "Driver is not healthy")

    def test_driver_initialization(self):
        """Test that the WebDriver is initialized and healthy."""
        self.assertIsNotNone(self.driver)
        self.assertTrue(verify_driver_health(self.driver))

    def test_basic_page_load(self):
        """Test that the WebDriver can load a basic page."""
        try:
            self.driver.get("https://example.com")
            self.assertIn("Example Domain", self.driver.title)
        except Exception as e:
            self.fail(f"Failed to load page: {str(e)}")


if __name__ == "__main__":
    unittest.main()
