import logging
import sys
from pathlib import Path


def setup_logging():
    """Configure logging for the application."""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "main.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Set specific log levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("webdriver_manager").setLevel(logging.WARNING)
