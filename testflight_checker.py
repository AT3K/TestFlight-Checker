# =======================
# Import Required Libraries
# =======================
import json
import time
import sys
import logging
from logging.handlers import RotatingFileHandler
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

# =======================
# Logging Configuration
# =======================
def setup_logging(log_file='testflight_checker.log'):
    """Configure logging with file rotation"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(),  # Console output
            RotatingFileHandler(
                log_file, 
                maxBytes=1_048_576,  # 1 MB
                backupCount=5
            )
        ]
    )

# Setup logging
setup_logging()

# =======================
# Configuration & Constants
# =======================
CONFIG_FILE_PATH = "apps_config.json"  # Path to the JSON config file
CHECK_INTERVAL = 60  # Interval to check in seconds

# =======================
# Load Environment Variables
# =======================
load_dotenv()  # Ensure .env file is loaded

# Retrieve the Webhook URL from the environment variable
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# =======================
# Helper Functions
# =======================
def make_safe_request(url, method='get', timeout=10, **kwargs):
    """
    Safely make HTTP requests with error handling and timeout
    
    :param url: URL to request
    :param method: HTTP method (get, post)
    :param timeout: Request timeout in seconds
    :param kwargs: Additional requests arguments
    :return: Response or None
    """
    try:
        # Add headers to prevent potential blocking
        headers = kwargs.pop('headers', {})
        headers.setdefault('User-Agent', 'Mozilla/5.0')
        
        # Choose the appropriate request method
        request_method = getattr(requests, method.lower())
        
        response = request_method(url, timeout=timeout, headers=headers, **kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error for {url}: {e}")
        return None

def load_config(file_path, default_content=None):
    """
    Safely load configuration files with error handling
    
    :param file_path: Path to the configuration file
    :param default_content: Default content if file doesn't exist or is invalid
    :return: Configuration dictionary
    """
    try:
        if not os.path.exists(file_path):
            if default_content is not None:
                with open(file_path, 'w') as f:
                    json.dump(default_content, f, indent=4)
            return default_content or {}

        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading configuration: {e}")
        return default_content or {}

def save_apps(apps):
    """Save the apps configuration to the JSON file."""
    try:
        with open(CONFIG_FILE_PATH, "w") as file:
            json.dump(apps, file, indent=4)
        logging.info("Configuration saved.")
    except Exception as e:
        logging.error(f"Error saving config file: {e}")

def send_discord_notification(app_name, testflight_url, message):
    """Send a notification to Discord via a webhook."""
    if DISCORD_WEBHOOK_URL:  # Only send notification if the webhook URL is set
        try:
            response = make_safe_request(
                DISCORD_WEBHOOK_URL, 
                method='post', 
                json={"content": message}
            )
            
            if response:
                logging.info(f"Notification sent: {message}")
            else:
                logging.warning(f"Failed to send notification for {app_name}")
        except Exception as e:
            logging.error(f"Error sending notification for {app_name}: {e}")
    else:
        logging.warning(f"Skipping notification for {app_name} as DISCORD_WEBHOOK_URL is not set.")

def check_testflight_slot(app_name, app_data):
    """Check if a TestFlight slot is available or full for a specific app and notify accordingly."""
    try:
        testflight_url = app_data["url"]
        last_state = app_data.get("last_state", None)  # Default to None if not present

        response = make_safe_request(testflight_url)
        
        if not response:
            logging.error(f"Failed to fetch TestFlight status for {app_name}")
            return

        # Determine the current state for the app
        if "View in TestFlight" in response.text and "Testing Apps with TestFlight" in response.text:
            view_index = response.text.find("View in TestFlight")
            testing_index = response.text.find("Testing Apps with TestFlight")
            if view_index < testing_index:
                current_state = "available"
            else:
                current_state = "full"
        elif "This beta is full" in response.text or "This beta isn't accepting any new testers" in response.text:
            current_state = "full"
        else:
            current_state = "unknown"

        # Handle state changes for the app
        if current_state != last_state:
            if current_state == "available":
                logging.info(f"Slots available for {app_name}! {testflight_url}")
                send_discord_notification(app_name, testflight_url, f"🚀 TestFlight slots for {app_name} are AVAILABLE!\n- Web Link: {testflight_url}")
            elif current_state == "full" and last_state == "available":
                logging.info(f"Beta is full for {app_name}.")
                send_discord_notification(app_name, testflight_url, f"❌ TestFlight slot for {app_name} is FILLED.\n- Web Link: {testflight_url}")
            else:
                logging.info(f"State changed for {app_name}, current state: {current_state}.")
            
            app_data["last_state"] = current_state
        else:
            logging.info(f"No state change for {app_name} (current state: {current_state}).")

    except Exception as e:
        logging.error(f"Error checking slots for {app_name}: {e}")

# =======================
# Main Execution
# =======================
def main():
    apps = load_config(CONFIG_FILE_PATH, default_content={})
    
    if not apps:
        logging.warning("No apps to monitor.")
        sys.exit(0)

    logging.info("Starting TestFlight slot checker.")
    
    while True:
        for app_name, app_data in apps.items():
            # Initialize state for new apps if only URL is present
            if isinstance(app_data, str):
                apps[app_name] = {"url": app_data, "last_state": None}
                app_data = apps[app_name]

            logging.info(f"Checking: {app_name}")
            check_testflight_slot(app_name, app_data)

        save_apps(apps)  # Save updates after each cycle
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
