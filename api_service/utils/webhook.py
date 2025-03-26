import requests
import logging

def send_to_webhook(url, data):
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        logging.info(f"Data successfully sent to webhook: {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending data to webhook: {e}")
