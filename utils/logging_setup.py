import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    log_dir = "/root/followfeed/"
    log_file = os.path.join(log_dir, "app.log")
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create a rotating file handler
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    
    # Create a formatter and add it to the handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # Get the root logger and add the file handler
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    # Optionally, add a stream handler for console output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)