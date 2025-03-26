import fcntl
import logging
import sys
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def file_lock(lock_file_path: str):
    lock_fd = open(lock_file_path, "w")
    try:
        fcntl.lockf(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logger.debug(f"Acquired lock on {lock_file_path}")
        yield
    except IOError:
        logger.error("Another instance is already running. Exiting.")
        sys.exit(1)
    finally:
        fcntl.lockf(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        logger.debug(f"Released lock on {lock_file_path}")
