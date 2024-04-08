import unittest
from unittest.mock import patch, MagicMock
import tweepy
from main import authenticate_twitter_api  # Import your function


class TestTwitterAuth(unittest.TestCase):

    @patch("tweepy.API")
    def test_authenticate_twitter_api_success(self, mock_api):
        # Setup mock
        mock_api.verify_credentials = MagicMock(return_value=True)

        # Call the function
        api = authenticate_twitter_api()

        # Assert API is returned
        self.assertIsNotNone(api)

    @patch("tweepy.API")
    def test_authenticate_twitter_api_failure(self, mock_api):
        # Setup mock to throw exception
        mock_api.verify_credentials = MagicMock(side_effect=Exception("Auth Failed"))

        # Call the function
        api = authenticate_twitter_api()

        # Assert None is returned
        self.assertIsNone(api)


if __name__ == "__main__":
    unittest.main()
