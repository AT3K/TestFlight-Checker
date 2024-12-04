import os
import json
import requests
import time
from dotenv import load_dotenv, set_key
from datetime import datetime

# CONFIGURATION
CONFIG_FILE_PATH = "apps_config.json"  # Path to the config file
CHECKER_SCRIPT_PATH = "testflight_checker.py"  # Path to the TestFlight checker script

# SECTION: PM2 Management
def check_pm2():
    """Check if PM2 is installed and initialized dynamically for the current user."""
    try:
        # Silently check if PM2 is installed
        pm2_version = os.popen("pm2 -v").read().strip()
        if pm2_version:
            # PM2 is installed
            return True
        else:
            print(f"[{datetime.now()}] PM2 is not installed. Please install PM2.")
            return False
    except Exception as e:
        print(f"[{datetime.now()}] Error checking PM2 installation: {e}")
        print(f"[{datetime.now()}] PM2 is not installed. Please install PM2.")
        return False

def initialize_pm2():
    """Initialize PM2 if it hasn't been initialized yet for the current user."""
    current_user = os.getlogin()
    home_dir = os.path.expanduser("~")

    # Check if PM2 startup is already configured for the current user
    startup_check = os.popen(f"pm2 startup systemd | grep -i '{current_user}'").read().strip()
    if startup_check:
        return  # PM2 is already initialized, no need to reinitialize

    # Initialize PM2 for the current user
    print(f"[{datetime.now()}] PM2 is not initialized. Attempting to initialize...")
    startup_command = f"sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u {current_user} --hp {home_dir}"
    os.system(startup_command)
    os.system("pm2 save")  # Save the current PM2 processes
    print(f"[{datetime.now()}] PM2 startup configured and saved for user {current_user}.")

# SECTION: Configuration Management
def ensure_config_file():
    """Ensure the configuration file exists."""
    if not os.path.exists(CONFIG_FILE_PATH):
        with open(CONFIG_FILE_PATH, "w") as file:
            json.dump({}, file, indent=4)  # Create an empty JSON file if it doesn't exist
        print(f"[{datetime.now()}] Configuration file created.")

def check_and_prompt_webhook():
    """Check if the Discord webhook URL is set in the .env file, and prompt the user if not."""
    global DISCORD_WEBHOOK_URL
    load_dotenv()  # Reload the .env file to ensure it's up-to-date
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

    if not DISCORD_WEBHOOK_URL:
        print(f"[{datetime.now()}] Discord webhook URL is not set.")
        webhook_url = input("Please enter your Discord webhook URL: ").strip()

        if webhook_url:
            # Save the webhook URL to the .env file
            set_key(".env", "DISCORD_WEBHOOK_URL", webhook_url)
            print(f"[{datetime.now()}] Webhook URL saved to .env file.")
            DISCORD_WEBHOOK_URL = webhook_url  # Update the global variable
        else:
            print(f"[{datetime.now()}] Invalid URL provided. Webhook not set.")

def load_apps():
    """Load the apps configuration from the JSON file."""
    ensure_config_file()  # Ensure the config file exists
    with open(CONFIG_FILE_PATH, "r") as file:
        apps = json.load(file)
    return apps if apps else {}

def save_apps(apps):
    """Save the apps configuration to the JSON file."""
    with open(CONFIG_FILE_PATH, "w") as file:
        json.dump(apps, file, indent=4)
    print(f"[{datetime.now()}] Configuration saved.")

# SECTION: App Management
def list_apps():
    """List all apps with options to remove them."""
    apps = load_apps()
    if not apps:
        print(f"[{datetime.now()}] No apps available.")
    else:
        print(f"\nCurrent TestFlight apps:\n{'='*30}")
        for index, (app_name, testflight_url) in enumerate(apps.items()):
            print(f"{chr(65 + index)}) {app_name}")
        print(f"{'='*30}\n")

def add_app():
    """Add a new app and its TestFlight URL."""
    app_name = input("Enter the app name: ")
    testflight_url = input("Enter the TestFlight URL: ")
    apps = load_apps()

    if app_name and testflight_url:
        apps[app_name] = testflight_url
        save_apps(apps)
        print(f"[{datetime.now()}] {app_name} has been added.")
    else:
        print(f"[{datetime.now()}] Invalid input. Both app name and URL are required.")

def remove_app():
    """Remove an app by its letter (A, B, C, etc.)."""
    apps = load_apps()
    if not apps:
        print(f"[{datetime.now()}] No apps to remove.")
        return

    list_apps()
    letter = input("Enter the letter of the app to remove: ").upper()

    if letter.isalpha() and ord(letter) - 65 < len(apps):
        app_to_remove = list(apps.keys())[ord(letter) - 65]
        del apps[app_to_remove]
        save_apps(apps)
        print(f"[{datetime.now()}] {app_to_remove} has been removed.")
    else:
        print(f"[{datetime.now()}] Invalid selection. Please choose a valid app.")

# SECTION: TestFlight Checking
def start_checking():
    """Start checking the TestFlight slots for all apps."""
    apps = load_apps()
    if not apps:
        print(f"[{datetime.now()}] No apps to check.")
        return

    # Check if the DISCORD_WEBHOOK_URL is set in the testflight_checker.py script
    check_and_prompt_webhook()  # Ensure the webhook URL is set before proceeding

    # Check if PM2 is installed and initialized
    if not check_pm2():
        print(f"[{datetime.now()}] PM2 setup failed. Aborting operation.")
        return

    # Initialize PM2 if not already done
    initialize_pm2()

    print(f"[{datetime.now()}] Starting TestFlight beta checker.")
    # Start the TestFlight checker with PM2, force if already running
    os.system("pm2 start testflight_checker.py --name testflight_checker -f")  # Added -f option

    # Save PM2 state
    os.system("pm2 save")

    # Exit after starting the checker
    print(f"[{datetime.now()}] TestFlight checker started in PM2.")
    exit()

def stop_checking():
    """Stop TestFlight checking in PM2."""
    print(f"[{datetime.now()}] Stopping TestFlight checker in PM2.")
    os.system("pm2 stop testflight_checker")

def restart_checking():
    """Restart TestFlight checking in PM2."""
    print(f"[{datetime.now()}] Restarting TestFlight checker in PM2.")
    # Use --update-env flag to ensure environment variables are updated
    os.system("pm2 restart testflight_checker --update-env")

def check_testflight_slot(app_name, testflight_url):
    """Check if a TestFlight slot is available for a given app."""
    try:
        response = requests.get(testflight_url)
        response.raise_for_status()

        if "View in TestFlight" in response.text and "Testing Apps with TestFlight" in response.text:
            view_index = response.text.find("View in TestFlight")
            testing_index = response.text.find("Testing Apps with TestFlight")
            if view_index < testing_index:
                print(f"[{datetime.now()}] TestFlight slots are AVAILABLE for {app_name}! Visit {testflight_url}")
            else:
                print(f"[{datetime.now()}] No available slots yet for {app_name}.")
        elif "This beta is full" in response.text or "This beta isn't accepting any new testers right now" in response.text:
            print(f"[{datetime.now()}] Beta is full or not accepting new testers for {app_name}.")
        else:
            print(f"[{datetime.now()}] No available slots yet for {app_name}.")
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] Error checking TestFlight slot for {app_name}: {e}")

# SECTION: Webhook Management
def get_discord_webhook():
    """Prompt for and validate the Discord webhook URL."""
    while True:
        webhook_url = input("Enter your Discord Webhook URL: ").strip()
        if validate_discord_webhook(webhook_url):
            print(f"[{datetime.now()}] Valid Discord webhook URL.")
            inject_webhook_into_checker(webhook_url)
            return webhook_url
        else:
            print(f"[{datetime.now()}] Invalid Discord webhook URL. Please try again.")

def validate_discord_webhook(webhook_url):
    """Validate the Discord webhook by sending a test message."""
    test_message = {"content": "Webhook validation test message."}
    try:
        response = requests.post(webhook_url, json=test_message)
        if response.status_code == 204:
            return True  # Webhook is valid if status code is 204 (No Content)
        else:
            print(f"[{datetime.now()}] Webhook test failed with status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] Webhook validation error: {e}")
        return False

def inject_webhook_into_checker(webhook_url):
    """Inject the validated Discord webhook URL into the checker script."""
    try:
        # Open the checker script and read the contents
        with open(CHECKER_SCRIPT_PATH, 'r') as file:
            script_content = file.readlines()

        # Find the line where DISCORD_WEBHOOK_URL is set and modify it
        for i, line in enumerate(script_content):
            if line.strip().startswith("DISCORD_WEBHOOK_URL ="):
                # Replace the line with the new webhook URL
                script_content[i] = f'DISCORD_WEBHOOK_URL = "{webhook_url}"\n'
                break

        # Write the modified content back to the checker script
        with open(CHECKER_SCRIPT_PATH, 'w') as file:
            file.writelines(script_content)

        print(f"[{datetime.now()}] Discord webhook URL injected into {CHECKER_SCRIPT_PATH}.")
    except Exception as e:
        print(f"[{datetime.now()}] Error injecting webhook URL into checker script: {e}")

# SECTION: Main Menu
def main_menu():
    """Main interactive menu."""
    while True:
        print(f"\nTestFlight Manager - Main Menu\n{'='*30}")
        print("1. List all apps")
        print("2. Add a new app")
        print("3. Remove an app")
        print("4. Start TestFlight checker with PM2")
        print("5. Stop TestFlight checker in PM2")
        print("6. Restart TestFlight checker in PM2")
        print("7. Enter your Discord webhook URL")
        print("8. Exit")
        choice = input("Choose an option (1-8): ")

        if choice == "1":
            list_apps()
        elif choice == "2":
            add_app()
        elif choice == "3":
            remove_app()
        elif choice == "4":
            start_checking()  # Start checking and exit after
            break  # Exiting the menu after starting the checker
        elif choice == "5":
            stop_checking()
        elif choice == "6":
            restart_checking()
        elif choice == "7":
            get_discord_webhook()
        elif choice == "8":
            print("Exiting...")
            break
        else:
            print(f"[{datetime.now()}] Invalid choice. Please choose between 1 and 8.")

# SECTION: Entry Point
if __name__ == "__main__":
    main_menu()
