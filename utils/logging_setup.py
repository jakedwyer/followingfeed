import logging

def setup_logging():
    logging.basicConfig(
        filename='main.log',  # Log file name
        filemode='a',        # Append mode
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
        level=logging.INFO   # Log level
    )