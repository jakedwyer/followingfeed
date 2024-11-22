from airtop import Airtop, SessionConfig
import os
from dotenv import load_dotenv
import json

login_url = "https://twitter.com/login"


def get_profile_id_input():
    """Prompt user for an existing profile ID"""
    profile_id = input("Enter a profileId (or press Enter to skip): ").strip()
    return profile_id if profile_id else None


def wait_for_login():
    """Wait for user to complete login"""
    input("Press Enter once you have logged in...")


def check_login_status(client, session_id, window_id):
    """Check if user is logged in to Twitter"""
    login_check_prompt = """
    Please check if the user is currently logged into Twitter/X.
    Return a JSON object with format: {"isLoggedIn": true/false}
    """

    response = client.windows.page_query(
        session_id, window_id, prompt=login_check_prompt
    )

    # Parse the string response into a JSON object
    try:
        result = json.loads(response.data.model_response)
        return result.get("isLoggedIn", False)
    except json.JSONDecodeError:
        print("Warning: Could not parse login status response")
        return False


def main():
    # Load environment variables
    load_dotenv()
    api_key = os.getenv("AIRTOP_API_KEY")
    if not api_key:
        raise ValueError("AIRTOP_API_KEY environment variable is not set")

    # Initialize Airtop client
    client = Airtop(api_key=api_key)

    # Get profile ID if user has one
    profile_id = get_profile_id_input()

    # Create session with profile persistence
    session = client.sessions.create(
        configuration=SessionConfig(
            timeout_minutes=10,
            persist_profile=True if not profile_id else False,
            base_profile_id=profile_id,
        )
    )

    try:
        # Create window and navigate to Twitter
        window = client.windows.create(session.data.id, url=login_url)
        # Get window info for live view URL
        window_info = client.windows.get_window_info(
            session.data.id, window.data.window_id
        )

        # Check login status
        is_logged_in = check_login_status(
            client, session.data.id, window.data.window_id
        )

        if not is_logged_in:
            print("\nPlease log into your Twitter account using this URL:")
            print(window_info.data.live_view_url)
            print("\nThis browser session will save your login state.")

            wait_for_login()

            # Provide profile ID for future use
            print(
                "\nTo avoid logging in again, use this profile ID for future sessions:"
            )
            print(f"Profile ID: {session.data.profile_id}\n")
        else:
            print("\nAlready logged in using existing profile!")
            print(f"Live View URL: {window_info.data.live_view_url}\n")

    finally:
        # Clean up
        client.sessions.terminate(session.data.id)


if __name__ == "__main__":
    main()
