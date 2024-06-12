import logging
import os

def setup_logging():
    log_file_path = os.path.join(os.path.dirname(__file__), '../app.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path),
            logging.StreamHandler()
        ]
    )