import os
from src.utils.session_manager import TwitterSessionManager
from typing import Optional


def create_and_save_profile(session_manager: TwitterSessionManager) -> Optional[str]:
    """
    Create a new session and save its profile
    """
    try:
        # Create session with profile persistence enabled
        session = session_manager.create_session(
            timeout_minutes=15,
            screen_resolution="1920x1080",
            persist_profile=True,  # This will save the profile
        )
        print("Session created with profile:", session)

        # Do your Twitter authentication here...

        # Terminate session to ensure profile is saved
        session_manager.terminate_session()

        return session.get("profile_id")

    except Exception as e:
        print(f"Error creating profile: {str(e)}")
        return None


def use_existing_profile(session_manager: TwitterSessionManager, profile_id: str):
    """
    Create a new session using an existing profile
    """
    try:
        # Create session with existing profile
        session = session_manager.create_session(
            timeout_minutes=15,
            screen_resolution="1920x1080",
            base_profile_id=profile_id,  # This will restore the profile
        )
        print("Session created with existing profile:", session)

        # Your authenticated Twitter operations here...

        # Terminate session when done
        session_manager.terminate_session()

    except Exception as e:
        print(f"Error using profile: {str(e)}")


def example():
    api_key = os.getenv("AIRTOP_API_KEY")
    if not api_key:
        raise ValueError("AIRTOP_API_KEY environment variable not set")

    session_manager = TwitterSessionManager(api_key)

    # First, create and save a profile
    profile_id = create_and_save_profile(session_manager)

    if profile_id:
        print(f"Created profile with ID: {profile_id}")

        # List all profiles
        profiles = session_manager.get_profiles()
        print("Available profiles:", profiles)

        # Use the saved profile in a new session
        use_existing_profile(session_manager, profile_id)


if __name__ == "__main__":
    example()
