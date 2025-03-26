import logging
from logging.handlers import RotatingFileHandler
import os
import atexit


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove all existing handlers
    for handler in logger.handlers[:]:
        handler.close()  # Properly close the handler
        logger.removeHandler(handler)

    # Ensure logs directory exists
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
    )
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "main.log")

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
    )
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Register cleanup function
    def cleanup():
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    atexit.register(cleanup)
