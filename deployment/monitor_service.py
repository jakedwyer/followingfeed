#!/usr/bin/env python3

import requests
import subprocess
import logging
import psutil
import time
from datetime import datetime
import sys
import os
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/var/log/twitter-analyzer/monitor.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

# Constants
SERVICE_NAME = "twitter-analyzer"
API_PORT = 8001
MAX_CPU_PERCENT = 85
MAX_MEMORY_PERCENT = 80
HEALTH_CHECK_RETRIES = 3
HEALTH_CHECK_RETRY_DELAY = 5


def get_service_metrics() -> Dict[str, float]:
    """Get current service resource usage"""
    metrics = {
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "connections": 0.0,
        "uptime": 0.0,
    }

    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            if "uvicorn" in str(proc.info["cmdline"]):
                process = psutil.Process(proc.info["pid"])
                metrics["cpu_percent"] = float(process.cpu_percent(interval=1))
                metrics["memory_percent"] = float(process.memory_percent())
                metrics["connections"] = float(len(process.connections()))
                metrics["uptime"] = float(time.time() - process.create_time())
    except Exception as e:
        logging.error(f"Error getting service metrics: {e}")

    return metrics


def check_service_health(retry_count: int = HEALTH_CHECK_RETRIES) -> bool:
    """Check if the API service is healthy with retries"""
    for attempt in range(retry_count):
        try:
            response = requests.get(f"http://localhost:{API_PORT}/health", timeout=10)
            if (
                response.status_code == 200
                and response.json().get("status") == "healthy"
            ):
                return True
            logging.warning(
                f"Unhealthy response on attempt {attempt + 1}: {response.text}"
            )
        except requests.RequestException as e:
            logging.error(f"Error checking service health (attempt {attempt + 1}): {e}")

        if attempt < retry_count - 1:
            time.sleep(HEALTH_CHECK_RETRY_DELAY)

    return False


def check_system_resources() -> Dict[str, bool]:
    """Check if system resources are within acceptable limits"""
    return {
        "cpu_ok": psutil.cpu_percent() < MAX_CPU_PERCENT,
        "memory_ok": psutil.virtual_memory().percent < MAX_MEMORY_PERCENT,
        "disk_ok": psutil.disk_usage("/").percent < 90,
    }


def check_service_status():
    """Check if the systemd service is running."""
    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "is-active", "twitter-analyzer"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() == "active"
    except Exception as e:
        logging.error(f"Error checking service status: {e}")
        return False


def check_health_endpoint():
    """Check if the health endpoint is responding."""
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Health check failed: {e}")
        return False


def test_analyze_endpoint():
    """Test the analyze endpoint with a sample profile."""
    try:
        response = requests.post(
            "http://localhost:8001/analyze_profile",
            json={"username": "support"},
            timeout=30,
        )

        if response.status_code != 200:
            logging.error(
                f"Analyze endpoint returned status code: {response.status_code}"
            )
            return False

        result = response.json()
        if "error" in result and result["error"]:
            logging.error(f"Analyze endpoint returned error: {result['error']}")
            return False

        return True
    except Exception as e:
        logging.error(f"Error testing analyze endpoint: {e}")
        return False


def send_alert(message):
    """Send alert about service issues."""
    logging.error(message)
    # Add your alert mechanism here (email, Slack, etc.)
    # For now, we'll just log to file


def restart_service() -> bool:
    """Restart the systemd service"""
    try:
        # Stop the service
        subprocess.run(["/usr/bin/systemctl", "stop", SERVICE_NAME], check=True)

        # Kill any remaining uvicorn processes
        try:
            subprocess.run(["/usr/bin/pkill", "-f", "uvicorn"], check=False)
        except Exception:
            pass  # Ignore pkill errors as the process might not exist

        # Small delay to ensure processes are stopped
        time.sleep(5)

        # Start the service
        subprocess.run(["/usr/bin/systemctl", "start", SERVICE_NAME], check=True)

        # Wait for service to be fully up (increased wait time)
        max_wait = 30  # Maximum wait time in seconds
        wait_interval = 2  # Check every 2 seconds
        attempts = max_wait // wait_interval

        for _ in range(attempts):
            time.sleep(wait_interval)
            try:
                # Try to connect to the health endpoint
                response = requests.get("http://localhost:8001/health", timeout=2)
                if response.status_code == 200:
                    logging.info("Service is up and responding")
                    return True
            except requests.RequestException:
                continue

        logging.error("Service failed to respond after restart")
        return False

    except subprocess.CalledProcessError as e:
        logging.error(f"Error restarting service: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error restarting service: {e}")
        return False


def log_metrics(metrics: Dict[str, Any]) -> None:
    """Log current service metrics"""
    logging.info(
        f"Service Metrics - CPU: {metrics['cpu_percent']:.1f}%, "
        f"Memory: {metrics['memory_percent']:.1f}%, "
        f"Connections: {metrics['connections']}, "
        f"Uptime: {metrics['uptime']:.0f}s"
    )


def main():
    # Initial delay to let the main service start up
    logging.info("Waiting 30 seconds for initial service startup...")
    time.sleep(30)

    failure_count = 0
    max_failures = 3  # Number of consecutive failures before taking action
    check_interval = 300  # 5 minutes between checks
    retry_delay = 10  # Seconds to wait between retries

    while True:
        logging.info("Running monitoring check...")

        # Check system resources first
        resources = check_system_resources()
        if not all(resources.values()):
            logging.warning(f"System resource check failed: {resources}")
            time.sleep(retry_delay)
            continue

        # Check if service is running with retries
        service_up = False
        for attempt in range(3):
            if check_service_status():
                service_up = True
                break
            time.sleep(retry_delay)

        if not service_up:
            failure_count += 1
            logging.warning(f"Service check failed. Failure count: {failure_count}")

            if failure_count >= max_failures:
                message = f"Service is down after {failure_count} consecutive failures. Attempting restart..."
                send_alert(message)

                if restart_service():
                    logging.info("Service restart successful")
                    failure_count = 0
                else:
                    send_alert(
                        "Failed to restart service. Manual intervention required."
                    )
                    time.sleep(
                        check_interval
                    )  # Wait full interval after failed restart
                continue
            time.sleep(retry_delay)
            continue

        # Check health endpoint with retries
        health_ok = False
        for attempt in range(3):
            if check_health_endpoint():
                health_ok = True
                break
            time.sleep(retry_delay)

        if not health_ok:
            failure_count += 1
            logging.warning(f"Health check failed. Failure count: {failure_count}")

            if failure_count >= max_failures:
                message = f"Health endpoint is down after {failure_count} consecutive failures. Attempting restart..."
                send_alert(message)

                if restart_service():
                    logging.info("Service restart successful")
                    failure_count = 0
                else:
                    send_alert(
                        "Failed to restart service. Manual intervention required."
                    )
                    time.sleep(
                        check_interval
                    )  # Wait full interval after failed restart
                continue
            time.sleep(retry_delay)
            continue

        # Test analyze endpoint with retries
        analyze_ok = False
        for attempt in range(2):  # Fewer retries for analyze endpoint as it's slower
            if test_analyze_endpoint():
                analyze_ok = True
                break
            time.sleep(retry_delay * 2)  # Longer delay for analyze endpoint

        if not analyze_ok:
            failure_count += 1
            logging.warning(
                f"Analyze endpoint test failed. Failure count: {failure_count}"
            )

            if failure_count >= max_failures:
                message = f"Analyze endpoint is down after {failure_count} consecutive failures. Attempting restart..."
                send_alert(message)

                if restart_service():
                    logging.info("Service restart successful")
                    failure_count = 0
                else:
                    send_alert(
                        "Failed to restart service. Manual intervention required."
                    )
                    time.sleep(
                        check_interval
                    )  # Wait full interval after failed restart
                continue
            time.sleep(retry_delay)
            continue

        # If we get here, all checks passed
        if failure_count > 0:
            logging.info("Service recovered after previous failures")
        failure_count = 0
        logging.info("All monitoring checks passed")

        # Get and log service metrics
        metrics = get_service_metrics()
        log_metrics(metrics)

        time.sleep(check_interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Unexpected error in monitoring script: {e}", exc_info=True)
        sys.exit(1)
