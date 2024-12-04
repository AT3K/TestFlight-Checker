# testflight_checker.py
import json
import time
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

# =======================
# Configuration
# =======================
CONFIG_FILE_PATH = "apps_config.json"  # Path to the JSON config file
CHECK_INTERVAL = 60  # Interval to check in seconds

# Load environment variables from the .env file
load_dotenv()  # This will automatically look for a .env file in the current directory

# Retrieve the Webhook URL from the environment variable
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Function to prompt the user for the Discord Webhook URL if it's not set
def prompt_for_webhook():
    """Prompt the user to input the Discord Webhook URL if it's not set and save it to the .env file."""
    global DISCORD_WEBHOOK_URL
    while not DISCORD_WEBHOOK_URL:
        webhook_url = input("Please enter your Discord webhook URL: ").strip()
        if webhook_url:
            # Save the webhook URL to the .env file
            set_key(".env", "DISCORD_WEBHOOK_URL", webhook_url)
            print(f"[{datetime.now()}] Webhook URL saved to .env file.")
            DISCORD_WEBHOOK_URL = webhook_url  # Update the global variable
        else:
            print(f"[{datetime.now()}] Invalid URL provided. Webhook not set.")

# If the Webhook URL is not found in the environment variables, prompt the user for it
if not DISCORD_WEBHOOK_URL:
    prompt_for_webhook()

# =======================
# Load Apps Function
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
        print(f"[{datetime.now()}] Configuration file not found. Please provide a valid JSON file.")
        return {}

# =======================
# Discord Notification Function
# =======================
def send_discord_notification(app_name, testflight_url):
    """Send a notification to Discord via a webhook."""
    try:
        message = f"🚀 TestFlight slots for {app_name} are AVAILABLE!\n" \
                  f"- Web Link: {testflight_url}\n" \
                  f"- Open in App: itms-beta://{testflight_url.split('://')[1]}"
        data = {"content": message}
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        if response.status_code == 204:
            print(f"[{datetime.now()}] Notification sent to Discord for {app_name}.")
        else:
            print(f"[{datetime.now()}] Failed to send Discord notification for {app_name}: {response.status_code} {response.text}")
    except Exception as e:
        print(f"[{datetime.now()}] Error sending Discord notification for {app_name}: {e}")

# =======================
# Check TestFlight Slot Function
# =======================
def check_testflight_slot(app_name, testflight_url):
    """Check if a TestFlight slot is available for a given app."""
    try:
        # Send a GET request to the TestFlight URL
        response = requests.get(testflight_url)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)

        # Check if the "View in TestFlight" and "Testing Apps with TestFlight" are present
        if "View in TestFlight" in response.text and "Testing Apps with TestFlight" in response.text:
            view_index = response.text.find("View in TestFlight")
            testing_index = response.text.find("Testing Apps with TestFlight")
            if view_index < testing_index:  # "View in TestFlight" should be before "Testing Apps with TestFlight"
                print(f"[{datetime.now()}] TestFlight slots are AVAILABLE for {app_name}! Visit {testflight_url}")
                send_discord_notification(app_name, testflight_url)
            else:
                print(f"[{datetime.now()}] No available slots yet for {app_name}.")
        # Check if the beta is full or not accepting new testers
        elif "This beta is full" in response.text or "This beta isn't accepting any new testers right now" in response.text:
            print(f"[{datetime.now()}] Beta is full or not accepting new testers for {app_name}.")
        else:
            print(f"[{datetime.now()}] No available slots yet for {app_name}.")

    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] Error checking TestFlight slot for {app_name}: {e}")

# =======================
# Start Checking Function
# =======================
def start_checking():
    """Start checking the TestFlight slots for all apps."""
    apps = load_apps()
    if not apps:
        print(f"[{datetime.now()}] No apps available to check.")
        return

    print(f"[{datetime.now()}] Starting TestFlight beta checker.")
    while True:
        for app_name, testflight_url in apps.items():
            print(f"[{datetime.now()}] Checking: {app_name}")
            check_testflight_slot(app_name, testflight_url)
        time.sleep(CHECK_INTERVAL)

# =======================
# Main Execution
# =======================
if __name__ == "__main__":
    # If Webhook URL is not set, prompt for it
    if not DISCORD_WEBHOOK_URL:
        prompt_for_webhook()

    start_checking()
