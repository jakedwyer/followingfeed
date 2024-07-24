import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    log_file = '/root/followfeed/main.log'
    max_log_size = 10 * 1024 * 1024  # 10 MB
    backup_count = 5

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_log_size, backupCount=backup_count
    )
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logging.info("Logging setup completed")
    logging.info(f"Log file location: {log_file}")