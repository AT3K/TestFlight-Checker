import os
import json
import requests
from dotenv import load_dotenv, set_key
from datetime import datetime

# ###################################################################################################
# CONFIGURATION
# ###################################################################################################

CONFIG_FILE_PATH = "apps_config.json"  # Path to the configuration file
CHECKER_SCRIPT_PATH = "testflight_checker.py"  # Path to the TestFlight checker script

ALLOW_MULTIPLE_INSTANCES = False  # Set this to True for multiple instances, False for a single instance

# ###################################################################################################
# *** DO NOT EDIT ANYTHING BELOW THIS LINE ***
# ###################################################################################################

# The rest of the script starts here

# ###################################################################################################
# SECTION: PM2 Management
# ###################################################################################################

def check_pm2():
    """Check if PM2 is installed."""
    try:
        # Attempt to check the version of PM2
        pm2_version = os.popen("pm2 -v").read().strip()
        if not pm2_version:
            print(f"[{datetime.now()}] PM2 is missing or not initialized. Please install PM2 manually to continue.")
            print(f"[{datetime.now()}] You can find the installation guide here: https://pm2.io/docs/runtime/guide/installation/")
            exit()  # Exit the script if PM2 is not installed
        return True
    except Exception as e:
        # In case the command fails (e.g., PM2 is missing)
        print(f"[{datetime.now()}] Error checking PM2: {e}")
        print(f"[{datetime.now()}] PM2 is missing or not initialized. Please install PM2 manually to continue.")
        print(f"[{datetime.now()}] You can find the installation guide here: https://pm2.io/docs/runtime/guide/installation/")
        exit()  # Exit the script if there is any issue with PM2

# ###################################################################################################
# SECTION: Configuration Management
# ###################################################################################################

def load_apps():
    """Load the apps from the configuration file."""
    if not os.path.exists(CONFIG_FILE_PATH):
        with open(CONFIG_FILE_PATH, "w") as file:
            json.dump({}, file, indent=4)
        print(f"[{datetime.now()}] Configuration file created.")
    with open(CONFIG_FILE_PATH, "r") as file:
        return json.load(file) or {}

def save_apps(apps):
    """Save the apps to the configuration file."""
    with open(CONFIG_FILE_PATH, "w") as file:
        json.dump(apps, file, indent=4)
    print(f"[{datetime.now()}] Configuration saved.")

def check_and_prompt_webhook():
    """Check if the Discord webhook URL is set and prompt for it if not."""
    load_dotenv()
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        webhook_url = input("Enter your Discord webhook URL: ").strip()
        if webhook_url:
            set_key(".env", "DISCORD_WEBHOOK_URL", webhook_url)
            print(f"[{datetime.now()}] Webhook URL saved.")
    return webhook_url

# ###################################################################################################
# SECTION: App Management
# ###################################################################################################

def list_apps():
    """List all apps in the configuration."""
    apps = load_apps()
    if not apps:
        print(f"[{datetime.now()}] No apps available.")
        return
    print(f"\nCurrent TestFlight apps:\n{'='*30}")
    for index, app in enumerate(apps.items()):
        print(f"{chr(65 + index)}) {app[0]}")
    print(f"{'='*30}")

def add_app():
    """Add a new app to the configuration."""
    app_name = input("Enter the app name: ")
    testflight_url = input("Enter the TestFlight URL: ")
    if app_name and testflight_url:
        apps = load_apps()
        apps[app_name] = testflight_url
        save_apps(apps)
        print(f"[{datetime.now()}] {app_name} added successfully!")
    else:
        print(f"[{datetime.now()}] Invalid input. Please make sure both app name and TestFlight URL are provided.")

def remove_app():
    """Remove an app from the configuration."""
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
        print(f"[{datetime.now()}] {app_to_remove} removed successfully!")
    else:
        print(f"[{datetime.now()}] Invalid selection. Please enter a valid letter.")

# ###################################################################################################
# SECTION: TestFlight Management
# ###################################################################################################

def start_checking():
    """Start checking the TestFlight slots for all apps."""
    apps = load_apps()
    if not apps:
        print(f"[{datetime.now()}] No apps to check.")
        return

    # Check if the DISCORD_WEBHOOK_URL is set in the testflight_checker.py script
    webhook_url = check_and_prompt_webhook()  # Ensure the webhook URL is set before proceeding

    # Check if PM2 is installed and initialized
    if not check_pm2():
        print(f"[{datetime.now()}] PM2 is missing or not initialized. Please install PM2 manually to continue.")
        return

    print(f"[{datetime.now()}] Starting TestFlight beta checker.")

    # If single instance mode is allowed, check for an existing process and delete it
    if not ALLOW_MULTIPLE_INSTANCES:
        os.system("pm2 delete testflight_checker")  # Delete any existing instance of testflight_checker

    # Start the TestFlight checker with PM2, force if already running
    os.system("pm2 start testflight_checker.py --name testflight_checker -f")  # Added -f option

    # Save PM2 state
    os.system("pm2 save")

    # Send a test message to the Discord webhook after starting the checker
    send_test_message(webhook_url)

    # Exit after starting the checker
    print(f"[{datetime.now()}] TestFlight checker started in PM2.")
    exit()

def stop_checking():
    """Stop the TestFlight checker."""
    os.system("pm2 stop testflight_checker")
    print(f"[{datetime.now()}] TestFlight checker stopped.")

def restart_checking():
    """Restart the TestFlight checker."""
    os.system("pm2 restart testflight_checker --update-env")
    print(f"[{datetime.now()}] TestFlight checker restarted.")

def check_testflight_slot(app_name, testflight_url):
    """Check if there are available TestFlight slots for a given app."""
    try:
        response = requests.get(testflight_url)
        response.raise_for_status()
        if "View in TestFlight" in response.text:
            print(f"[{datetime.now()}] Slots available for {app_name}!")
        else:
            print(f"[{datetime.now()}] No available slots for {app_name}.")
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] Error checking slot for {app_name}: {e}")

# ###################################################################################################
# SECTION: Webhook Management
# ###################################################################################################

def send_test_message(webhook_url):
    """Send a test message to the Discord webhook."""
    test_message = {"content": "Webhook is successfully set up and the TestFlight Manager is running!"}
    try:
        response = requests.post(webhook_url, json=test_message)
        if response.status_code == 204:
            print(f"[{datetime.now()}] Test message sent successfully to Discord webhook.")
        else:
            print(f"[{datetime.now()}] Failed to send test message. Response: {response.text} (Status code: {response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] Error sending test message: {e}")

def validate_discord_webhook(webhook_url):
    """Validate the Discord webhook URL."""
    try:
        response = requests.post(webhook_url, json={"content": "Webhook test."})
        return response.status_code == 204
    except requests.exceptions.RequestException:
        print(f"[{datetime.now()}] Error validating webhook URL.")
        return False

def inject_webhook_url_into_checker(webhook_url):
    """Inject the webhook URL into the testflight_checker.py script."""
    try:
        with open(CHECKER_SCRIPT_PATH, 'r') as file:
            script_content = file.readlines()
        for i, line in enumerate(script_content):
            if line.strip().startswith("DISCORD_WEBHOOK_URL ="):
                script_content[i] = f'DISCORD_WEBHOOK_URL = "{webhook_url}"\n'
                break
        with open(CHECKER_SCRIPT_PATH, 'w') as file:
            file.writelines(script_content)
        print(f"[{datetime.now()}] Webhook URL injected into checker script.")
    except Exception as e:
        print(f"[{datetime.now()}] Error injecting webhook: {e}")

# ###################################################################################################
# SECTION: Main Menu
# ###################################################################################################

def main_menu():
    """Main interactive menu."""
    # Check PM2 before starting the menu loop
    check_pm2()

    while True:
        print(f"\nTestFlight Manager - Main Menu\n{'='*30}")
        print("1. List apps\n2. Add app\n3. Remove app\n4. Start checker\n5. Stop checker\n6. Restart checker\n7. Set Webhook\n8. Exit")
        choice = input("Choose an option (1-8): ")

        if choice == "1": 
            list_apps()
        elif choice == "2": 
            add_app()
        elif choice == "3": 
            remove_app()
        elif choice == "4": 
            start_checking()
        elif choice == "5": 
            stop_checking()
        elif choice == "6": 
            restart_checking()
        elif choice == "7": 
            inject_webhook_url_into_checker(check_and_prompt_webhook())
        elif choice == "8": 
            break
        else: 
            print(f"[{datetime.now()}] Invalid choice.")

# ###################################################################################################
# SECTION: Entry Point
# ###################################################################################################

if __name__ == "__main__":
    main_menu()
