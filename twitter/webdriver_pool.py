from queue import Queue
import logging
from selenium import webdriver
from typing import Optional, Generator
import threading
from contextlib import contextmanager
from .driver_init import init_driver

logger = logging.getLogger(__name__)


class WebDriverPool:
    def __init__(self, max_drivers: int = 3, init_drivers: int = 1):
        self.pool: Queue = Queue()
        self.max_drivers = max_drivers
        self.active_drivers = 0
        self._lock = threading.Lock()

        # Initialize pool with some drivers
        for _ in range(init_drivers):
            self._add_driver()

    def _create_driver(self) -> webdriver.Chrome:
        """Create a new WebDriver instance with all necessary options."""
        return init_driver()

    def _add_driver(self) -> None:
        """Add a new driver to the pool."""
        try:
            driver = self._create_driver()
            self.pool.put(driver)
            with self._lock:
                self.active_drivers += 1
        except Exception as e:
            logger.error(f"Failed to create WebDriver: {e}")
            raise

    @contextmanager
    def get_driver(self) -> Generator[webdriver.Chrome, None, None]:
        """Get a driver from the pool or create a new one if needed."""
        driver = None
        try:
            # Try to get an existing driver
            try:
                driver = self.pool.get_nowait()
            except Queue.Empty:
                # If no drivers available and below max, create new one
                with self._lock:
                    if self.active_drivers < self.max_drivers:
                        self._add_driver()
                        driver = self.pool.get()
                    else:
                        # Wait for an available driver
                        driver = self.pool.get()

            yield driver

            # Return driver to pool if it's still healthy
            try:
                driver.current_url  # Quick health check
                self.pool.put(driver)
            except:
                # If driver is unhealthy, close it and create new one
                self._close_driver(driver)
                self._add_driver()

        except Exception as e:
            logger.error(f"Error managing WebDriver: {e}")
            if driver:
                self._close_driver(driver)
            raise

    def _close_driver(self, driver: Optional[webdriver.Chrome]) -> None:
        """Safely close a driver and decrease active count."""
        if driver:
            try:
                driver.quit()
            except:
                pass  # Ignore errors during closing
            finally:
                with self._lock:
                    self.active_drivers -= 1

    def shutdown(self) -> None:
        """Close all drivers in the pool."""
        while not self.pool.empty():
            driver = self.pool.get_nowait()
            self._close_driver(driver)


# Global pool instance
driver_pool = WebDriverPool(max_drivers=3, init_drivers=1)
