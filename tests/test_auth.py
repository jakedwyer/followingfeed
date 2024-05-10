import unittest
from unittest.mock import patch, MagicMock
from twitter.twitter import authenticate_twitter_api  # Import your function from the correct module

class TestTwitterAuth(unittest.TestCase):

    @patch("twitter.twitter.authenticate_twitter_api")
    def test_authenticate_twitter_api_success(self, mock_authenticate):
        # Setup mock
        mock_authenticate.return_value = MagicMock()

        # Call the function with test credentials
        api = authenticate_twitter_api("test_consumer_key", "test_consumer_secret", "test_access_token", "test_access_token_secret")

        # Assert API is returned
        self.assertIsNotNone(api)

    @patch("twitter.twitter.authenticate_twitter_api")
    def test_authenticate_twitter_api_failure(self, mock_authenticate):
        # Setup mock to throw exception
        mock_authenticate.side_effect = Exception("Auth Failed")

        # Call the function with test credentials
        api = authenticate_twitter_api("test_consumer_key", "test_consumer_secret", "test_access_token", "test_access_token_secret")

        # Assert None is returned
        self.assertIsNone(api)

if __name__ == "__main__":
    unittest.main()
