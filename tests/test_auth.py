import unittest
from unittest.mock import patch, MagicMock
import tweepy
from twitter.twitter import authenticate_twitter_api  # Import your function from the correct module


class TestTwitterAuth(unittest.TestCase):

    @patch("tweepy.API")
    def test_authenticate_twitter_api_success(self, mock_api):
        # Setup mock
        mock_api.return_value.verify_credentials.return_value = True

        # Call the function with test credentials
        api = authenticate_twitter_api("test_consumer_key", "test_consumer_secret", "test_access_token", "test_access_token_secret")

        # Assert API is returned
        self.assertIsNotNone(api)

    @patch("tweepy.API")
    def test_authenticate_twitter_api_failure(self, mock_api):
        # Setup mock to throw exception
        mock_api.return_value.verify_credentials.side_effect = Exception("Auth Failed")

        # Call the function with test credentials
        api = authenticate_twitter_api("test_consumer_key", "test_consumer_secret", "test_access_token", "test_access_token_secret")

        # Assert None is returned
        self.assertIsNone(api)


if __name__ == "__main__":
    unittest.main()
