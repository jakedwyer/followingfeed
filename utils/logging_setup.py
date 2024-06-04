import logging

def setup_logging(log_file_path="app.log"):
    logging.basicConfig(
        filename=log_file_path,
        filemode='a',
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
