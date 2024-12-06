# =======================
# Import Required Libraries
# =======================
import json
import time
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# =======================
# Configuration & Constants
# =======================
CONFIG_FILE_PATH = "apps_config.json"  # Path to the JSON config file
CHECK_INTERVAL = 60  # Interval to check in seconds
NOTIFICATION_COOLDOWN = timedelta(minutes=5)  # Cooldown period for notifications (5 minutes)

# =======================
# Load Environment Variables
# =======================
load_dotenv()  # Ensure .env file is loaded

# Retrieve the Webhook URL from the environment variable
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# If webhook URL is missing, display a warning, but don't exit the script
if not DISCORD_WEBHOOK_URL:
    print(f"[{datetime.now()}] Warning: DISCORD_WEBHOOK_URL is not set in the environment. Notifications will not be sent.")

# =======================
# Helper Functions
# =======================
# Dictionary to store the last notification time for each app
last_notification_time = {}

def load_apps():
    """Load the apps configuration from the JSON file."""
    try:
        with open(CONFIG_FILE_PATH, "r") as file:
            apps = json.load(file)
            if not apps:
                print(f"[{datetime.now()}] No apps found in config file.")
            return apps
    except FileNotFoundError:
        print(f"[{datetime.now()}] Configuration file not found.")
        return {}

def send_discord_notification(app_name, testflight_url, message):
    """Send a notification to Discord via a webhook."""
    if DISCORD_WEBHOOK_URL:  # Only send notification if the webhook URL is set
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
            if response.status_code == 204:
                print(f"[{datetime.now()}] {message} for {app_name}.")
            else:
                print(f"[{datetime.now()}] Failed to send notification for {app_name}: {response.status_code} {response.text}")
        except Exception as e:
            print(f"[{datetime.now()}] Error sending notification for {app_name}: {e}")
    else:
        print(f"[{datetime.now()}] Skipping notification for {app_name} as DISCORD_WEBHOOK_URL is not set.")

def check_testflight_slot(app_name, testflight_url):
    """Check if a TestFlight slot is available."""
    try:
        response = requests.get(testflight_url)
        response.raise_for_status()

        # Check if the page indicates available slots
        if "View in TestFlight" in response.text and "Testing Apps with TestFlight" in response.text:
            view_index = response.text.find("View in TestFlight")
            testing_index = response.text.find("Testing Apps with TestFlight")
            if view_index < testing_index:
                print(f"[{datetime.now()}] Slots available for {app_name}! {testflight_url}")
                
                # Check if enough time has passed since the last notification
                last_notification = last_notification_time.get(app_name)
                if not last_notification or (datetime.now() - last_notification) >= NOTIFICATION_COOLDOWN:
                    send_discord_notification(app_name, testflight_url, f"🚀 TestFlight slots for {app_name} are AVAILABLE!\n- Web Link: {testflight_url}")
                    last_notification_time[app_name] = datetime.now()  # Update last notification time
            else:
                print(f"[{datetime.now()}] No slots available for {app_name}.")
        elif "This beta is full" in response.text or "This beta isn't accepting any new testers" in response.text:
            print(f"[{datetime.now()}] Beta is full for {app_name}.")
            
            # Check if enough time has passed since the last filled notification
            last_notification = last_notification_time.get(app_name)
            if not last_notification or (datetime.now() - last_notification) >= NOTIFICATION_COOLDOWN:
                send_discord_notification(app_name, testflight_url, f"❌ TestFlight slot for {app_name} is FILLED.\n- Web Link: {testflight_url}")
                last_notification_time[app_name] = datetime.now()  # Update last notification time
        else:
            print(f"[{datetime.now()}] No slots available for {app_name}.")
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] Error checking slots for {app_name}: {e}")

# =======================
# Main Execution
# =======================
if __name__ == "__main__":
    apps = load_apps()
    if not apps:
        print(f"[{datetime.now()}] No apps to monitor.")
        exit(0)

    print(f"[{datetime.now()}] Starting TestFlight slot checker.")
    while True:
        for app_name, testflight_url in apps.items():
            print(f"[{datetime.now()}] Checking: {app_name}")
            check_testflight_slot(app_name, testflight_url)
        time.sleep(CHECK_INTERVAL)
