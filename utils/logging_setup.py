import logging
import os

def setup_logging():
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(log_dir, '..', 'main.log')
    
    logging.basicConfig(
        filename=log_file,  # Use absolute path for log file
        filemode='a',        # Append mode
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
        level=logging.INFO   # Log level
    )
    
    # Test log message
    logging.info("Logging setup completed")
    logging.info(f"Log file location: {log_file}")