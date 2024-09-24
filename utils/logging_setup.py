import logging
from logging.handlers import RotatingFileHandler
import os


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # File handler
        file_handler = logging.FileHandler("main.log")
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
