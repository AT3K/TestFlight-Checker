# =======================
# Import Required Libraries
# =======================
import json
import time
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

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

# If webhook URL is missing, display a warning, but don't exit the script
if not DISCORD_WEBHOOK_URL:
    print(f"[{datetime.now()}] Warning: DISCORD_WEBHOOK_URL is not set in the environment. Notifications will not be sent.")

# =======================
# Helper Functions
# =======================
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

def save_apps(apps):
    """Save the updated apps configuration back to the JSON file."""
    try:
        with open(CONFIG_FILE_PATH, "w") as file:
            json.dump(apps, file, indent=4)
    except Exception as e:
        print(f"[{datetime.now()}] Error saving config file: {e}")

def send_discord_notification(app_name, testflight_url, message):
    """Send a notification to Discord via a webhook."""
    if DISCORD_WEBHOOK_URL:  # Only send notification if the webhook URL is set
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
            if response.status_code == 204:
                print(f"[{datetime.now()}] Notification sent: {message}")
            else:
                print(f"[{datetime.now()}] Failed to send notification for {app_name}: {response.status_code} {response.text}")
        except Exception as e:
            print(f"[{datetime.now()}] Error sending notification for {app_name}: {e}")
    else:
        print(f"[{datetime.now()}] Skipping notification for {app_name} as DISCORD_WEBHOOK_URL is not set.")

def check_testflight_slot(app_name, app_data):
    """Check if a TestFlight slot is available or full for a specific app and notify accordingly."""
    try:
        testflight_url = app_data["url"]
        last_state = app_data.get("last_state", None)  # Default to None if not present

        response = requests.get(testflight_url)
        response.raise_for_status()

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
                print(f"[{datetime.now()}] Slots available for {app_name}! {testflight_url}")
                send_discord_notification(app_name, testflight_url, f"🚀 TestFlight slots for {app_name} are AVAILABLE!\n- Web Link: {testflight_url}")
            elif current_state == "full" and last_state == "available":
                print(f"[{datetime.now()}] Beta is full for {app_name}.")
                send_discord_notification(app_name, testflight_url, f"❌ TestFlight slot for {app_name} is FILLED.\n- Web Link: {testflight_url}")
            else:
                print(f"[{datetime.now()}] State changed for {app_name}, current state: {current_state}.")
            app_data["last_state"] = current_state
        else:
            print(f"[{datetime.now()}] No state change for {app_name} (current state: {current_state}).")

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
        for app_name, app_data in apps.items():
            if isinstance(app_data, str):
                # Initialize state for new apps if only URL is present
                apps[app_name] = {"url": app_data, "last_state": None}
                app_data = apps[app_name]

            print(f"[{datetime.now()}] Checking: {app_name}")
            check_testflight_slot(app_name, app_data)

        save_apps(apps)  # Save updates after each cycle
        time.sleep(CHECK_INTERVAL)
