# ======================
# Script Starts Here
#========================

MULTIPLE_INSTANCES = False  # Set to True to allow multiple instances, False to allow only a single instance

# =======================
# DO NOT EDIT BELOW THIS LINE UNLESS YOU KNOW WHAT YOU ARE DOING
# =======================

# =======================
# Import Required Libraries
# =======================
import json
import os
import subprocess
import shutil
import requests
from datetime import datetime
from packaging import version  # We will use this library to compare version strings
import re

# =======================
# Configuration & Constants
# =======================
CURRENT_VERSION = "v0.1.0-beta"  # Current version of the application
CONFIG_FILE_PATH = "apps_config.json"  # Path to the apps configuration file
PM2_PROCESS_NAME = "testflight_checker"  # Name of the PM2 process
WEBHOOK_URL_PATTERN = r"^https://discord\.com/api/webhooks/\d+/[A-Za-z0-9_-]+$"  # Regex pattern to validate Discord webhook URL

# =======================
# Webhook Management
# =======================
def create_env_file():
    """Create the .env file with an empty DISCORD_WEBHOOK_URL if it doesn't exist."""
    if not os.path.exists(".env"):
        with open(".env", "w") as file:
            file.write("DISCORD_WEBHOOK_URL=''\n")
        print(f"[{datetime.now()}] .env file created with an empty DISCORD_WEBHOOK_URL.")

def check_webhook():
    """Check if the webhook URL is set in the .env file."""
    if not os.path.exists(".env"):
        create_env_file()  # Create the .env file if it doesn't exist
    with open(".env", "r") as file:
        for line in file:
            if line.startswith("DISCORD_WEBHOOK_URL="):
                webhook_url = line.strip().split("=")[1].strip("'")  # Remove the single quotes around the URL
                return bool(webhook_url)  # Return True if the webhook URL is not empty
    return False

def validate_discord_webhook_format(webhook_url):
    """Validate the format of the Discord webhook URL."""
    if re.match(WEBHOOK_URL_PATTERN, webhook_url):
        return True
    else:
        print(f"[{datetime.now()}] Invalid Discord webhook URL format. Please ensure the URL follows the correct format.")
        print(f"[{datetime.now()}] The correct format for a Discord webhook URL is: https://discord.com/api/webhooks/<webhook_id>/<webhook_token>")
        return False

def validate_discord_webhook(webhook_url):
    """Validate the Discord webhook URL by sending a test message."""
    if not validate_discord_webhook_format(webhook_url):
        return False
    
    test_data = {
        "content": "Test message from TestFlight Manager to validate webhook."
    }

    try:
        response = requests.post(webhook_url, json=test_data)
        
        if response.status_code == 204:
            print(f"[{datetime.now()}] Discord webhook URL is valid.")
            return True
        else:
            print(f"[{datetime.now()}] Failed to send test message. Status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] Error validating Discord webhook: {e}")
        return False

# =======================
# App Management Functions
# =======================
def load_apps():
    """Load the apps configuration from the JSON file or create an empty file if it doesn't exist."""
    if not os.path.exists(CONFIG_FILE_PATH):
        print(f"[{datetime.now()}] Configuration file not found. Creating a new blank file.")
        save_apps({})  # Create an empty file if it doesn't exist
        return {}

    try:
        with open(CONFIG_FILE_PATH, "r") as file:
            apps = json.load(file)
        return apps
    except json.JSONDecodeError:
        print(f"[{datetime.now()}] Configuration file is corrupted. Creating a new blank file.")
        save_apps({})  # If JSON is corrupted, reset to an empty file
        return {}

def save_apps(apps):
    """Save the apps configuration to the JSON file."""
    with open(CONFIG_FILE_PATH, "w") as file:
        json.dump(apps, file, indent=4)
        print(f"[{datetime.now()}] Configuration saved.")

def list_apps():
    """List all configured apps."""
    apps = load_apps()
    if apps:
        print("\nConfigured Apps:")
        for name, url in apps.items():
            print(f"- {name}")
    else:
        print("\nNo apps are configured.")

def add_app():
    """Add a new app to the configuration."""
    app_name = input("Enter the app name: ").strip()
    if not app_name:
        print(f"[{datetime.now()}] App name cannot be empty. Returning to the menu.")
        return

    testflight_url = input("Enter the TestFlight URL: ").strip()

    if not testflight_url.startswith("https://testflight.apple.com/join/"):
        print(f"[{datetime.now()}] Invalid URL format. The URL must start with 'https://testflight.apple.com/join/'.")
        return

    apps = load_apps()
    apps[app_name] = testflight_url
    save_apps(apps)
    
    # Restart silently in the background to apply changes
    restart_checker()

def remove_app():
    """Remove an app from the configuration."""
    apps = load_apps()
    
    if not apps:
        print(f"[{datetime.now()}] No apps to remove.")
        return

    # List apps with options A, B, C...
    print("Select an app to remove:")
    for idx, (name, url) in enumerate(apps.items(), start=1):
        print(f"{chr(64 + idx)}. {name}")

    app_choice = input("Enter the option (A, B, C, etc.): ").strip().upper()

    # Validate input choice
    if not app_choice.isalpha() or ord(app_choice) < 65 or ord(app_choice) > 65 + len(apps) - 1:
        print(f"[{datetime.now()}] Invalid option. Returning to the menu.")
        return

    app_index = ord(app_choice) - 65
    app_name = list(apps.keys())[app_index]

    # Remove the selected app
    del apps[app_name]
    save_apps(apps)
    print(f"[{datetime.now()}] App '{app_name}' removed.")
    
    # Restart silently in the background to apply changes
    restart_checker()

# =======================
# PM2 Availability Check
# =======================
def is_pm2_installed():
    """Check if PM2 is installed and accessible."""
    return shutil.which("pm2") is not None

# =======================
# Process Management (PM2)
# =======================
def start_checker():
    """Start the slot checker using PM2 with -f and --update-env options."""
    create_env_file()  # Ensure .env file is created if it doesn't exist

    if not is_pm2_installed():
        print(f"[{datetime.now()}] Error: PM2 is not installed or not accessible. Please install PM2 and try again.")
        print("You can install PM2 by running the following commands:")
        print("1. sudo apt update")
        print("2. sudo apt install nodejs npm -y")
        print("3. sudo npm install -g pm2")
        return

    if not MULTIPLE_INSTANCES:
        # Stop any existing process for 'testflight_checker' to avoid duplicates if SINGLE INSTANCE is enabled
        subprocess.run(["pm2", "delete", PM2_PROCESS_NAME], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Start the new process
    subprocess.run(["pm2", "start", "testflight_checker.py", "--name", PM2_PROCESS_NAME, "--update-env", "-f"])

    # Save the current process list to avoid warnings
    subprocess.run(["pm2", "save"])

    print(f"[{datetime.now()}] Slot checker started with updated environment variables and PM2 configuration saved.")

    # Check if the webhook is empty and remind the user
    if not check_webhook():
        print(f"[{datetime.now()}] Warning: Webhook URL is empty. Notifications are not set. Please update the webhook URL.")

    # Check if the configuration file exists
    if not os.path.exists(CONFIG_FILE_PATH):  # Check if the configuration file exists
        print(f"[{datetime.now()}] Configuration file not found. Creating a new blank file.")
        save_apps({})  # Create an empty configuration file

def stop_checker():
    """Stop the slot checker using PM2."""
    if not is_pm2_installed():
        print(f"[{datetime.now()}] Error: PM2 is not installed or not accessible. Please install PM2 and try again.")
        return

    subprocess.run(["pm2", "stop", PM2_PROCESS_NAME])
    print(f"[{datetime.now()}] Slot checker stopped.")

def restart_checker():
    """Restart the slot checker using PM2."""
    create_env_file()  # Ensure .env file is created if it doesn't exist

    if not is_pm2_installed():
        print(f"[{datetime.now()}] Error: PM2 is not installed or not accessible. Please install PM2 and try again.")
        return

    # Restart the existing process
    subprocess.run(["pm2", "restart", PM2_PROCESS_NAME])

    # Save the current process list to avoid warnings
    subprocess.run(["pm2", "save"])

    print(f"[{datetime.now()}] Slot checker restarted with updated environment variables.")

    # Check if the webhook is empty and remind the user
    if not check_webhook():
        print(f"[{datetime.now()}] Warning: Webhook URL is empty. Notifications are not set. Please update the webhook URL.")

    # Check if the configuration file exists
    if not os.path.exists(CONFIG_FILE_PATH):  # Check if the configuration file exists
        print(f"[{datetime.now()}] Configuration file not found. Creating a new blank file.")
        save_apps({})  # Create an empty configuration file
    
# =======================
# Advanced Options (Updates and Webhook)
# =======================
def advanced_options():
    while True:
        print("\nAdvanced Options:")
        print("===================")
        print("1. Update the Webhook URL")
        print("2. Check for updates from GitHub")
        print("3. Back to main menu")
        choice = input("Choose an option (1-3): ").strip()

        if choice == "1":
            update_webhook()
        elif choice == "2":
            check_for_updates()
        elif choice == "3":
            break
        else:
            print("Invalid option. Please try again.")

def update_webhook():
    """Update the webhook URL in the .env file."""
    webhook_url = input("Enter the new webhook URL: ").strip()

    # Do not update if the webhook URL is empty
    if not webhook_url:
        print(f"[{datetime.now()}] Webhook URL not updated. Returning to the menu.")
        return
    
    # Validate the webhook URL format
    if not validate_discord_webhook(webhook_url):
        return

    # Open the .env file and update the webhook URL
    with open(".env", "r") as file:
        lines = file.readlines()

    with open(".env", "w") as file:
        for line in lines:
            if line.startswith("DISCORD_WEBHOOK_URL="):
                file.write(f"DISCORD_WEBHOOK_URL='{webhook_url}'\n")
            else:
                file.write(line)

    print(f"[{datetime.now()}] Webhook URL updated in the .env file.")

    # Restart PM2 process to apply changes
    restart_checker()
    print(f"[{datetime.now()}] PM2 process restarted to apply updated webhook.")

def check_for_updates():
    """Check for updates from GitHub based on user's choice (beta or stable)."""
    # Ask the user for the type of release they want to check (beta or stable)
    release_type = input(f"[{datetime.now()}] Which version would you like to check for? (beta or stable): ").strip().lower()

    if release_type not in ["beta", "stable"]:
        print(f"[{datetime.now()}] Invalid option. Please choose either 'beta' or 'stable'.")
        return

    # Define the GitHub API URL for the releases
    github_api_url = "https://api.github.com/repos/AT3K/TestFlight-Checker/releases"

    try:
        # Make the request to GitHub API to get the releases
        response = requests.get(github_api_url)
        response.raise_for_status()

        # Get the current version of the app
        current_version_str = CURRENT_VERSION.lstrip("v")  # Strip 'v' from the current version
        current_version = version.parse(current_version_str)

        # Get the list of releases from the response
        releases = response.json()

        # Separate beta and stable releases
        beta_versions = []
        stable_versions = []

        for release in releases:
            tag_name = release['tag_name']
            if '-alpha' in tag_name or '-beta' in tag_name:
                beta_versions.append(tag_name)
            else:
                stable_versions.append(tag_name)

        # Find the latest version for each release type
        latest_beta_version = max([version.parse(v.lstrip("v")) for v in beta_versions], default=None)
        latest_stable_version = max([version.parse(v.lstrip("v")) for v in stable_versions], default=None)

        if release_type == "beta":
            if latest_beta_version:
                print(f"[{datetime.now()}] Latest beta release: {latest_beta_version}")
                if latest_beta_version > current_version:
                    pull_update = input(f"Would you like to pull the latest beta version? (y/n): ").strip().lower()
                    if pull_update == "y":
                        pull_latest_update()
                elif latest_beta_version < current_version:
                    print(f"[{datetime.now()}] Seems like you have a build higher than the latest beta release. You must be a developer or a secret tester! 🧑‍💻")
                else:
                    print(f"[{datetime.now()}] You are already on the latest beta version!")
            else:
                print(f"[{datetime.now()}] No beta versions available.")
        
        elif release_type == "stable":
            if latest_stable_version:
                print(f"[{datetime.now()}] Latest stable release: {latest_stable_version}")
                if latest_stable_version > current_version:
                    pull_update = input(f"Would you like to pull the latest stable version? (y/n): ").strip().lower()
                    if pull_update == "y":
                        pull_latest_update()
                elif latest_stable_version < current_version:
                    print(f"[{datetime.now()}] Seems like you have a build higher than the latest stable release. You must be a developer or a secret tester! 🧑‍💻")
                else:
                    print(f"[{datetime.now()}] You are already on the latest stable version!")
            else:
                print(f"[{datetime.now()}] No stable versions available.")
    
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] Error checking for updates: {e}")

def pull_latest_update():
    """Pull the latest changes from the GitHub repository."""
    if not is_git_installed():
        print(f"[{datetime.now()}] Error: Git is not installed. Please install Git and try again.")
        return

    if not is_git_repository():
        print(f"[{datetime.now()}] Error: This is not a Git repository. Please initialize a Git repository first.")
        return

    print(f"[{datetime.now()}] Pulling the latest updates from the repository...")
    try:
        result = subprocess.run(["git", "pull"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            print(f"[{datetime.now()}] Successfully pulled the latest update.")
        else:
            print(f"[{datetime.now()}] Error pulling updates: {result.stderr.decode()}")
    except subprocess.CalledProcessError as e:
        print(f"[{datetime.now()}] Failed to pull updates: {e}")

# =======================
# Git Installation & Repository Checks
# =======================
def is_git_installed():
    """Check if Git is installed on the system."""
    return shutil.which("git") is not None

def is_git_repository():
    """Check if the current directory is a Git repository."""
    return os.path.isdir(".git")

# =======================
# Main Menu & Program Flow
# =======================
def main_menu():
    while True:
        print("\nMain Menu:")
        print("=================")
        print("1. List all configured apps")
        print("2. Add a new app")
        print("3. Remove an app")
        print("4. Start the checker")
        print("5. Stop the checker")
        print("6. Restart the checker")
        print("7. Advanced options")
        print("8. Exit")

        choice = input("Choose an option (1-8): ").strip()

        if choice == "1":
            list_apps()
        elif choice == "2":
            add_app()
        elif choice == "3":
            remove_app()
        elif choice == "4":
            start_checker()
        elif choice == "5":
            stop_checker()
        elif choice == "6":
            restart_checker()
        elif choice == "7":
            advanced_options()
        elif choice == "8":
            print("Exiting...")
            break
        else:
            print("Invalid option. Please try again.")

# =======================
# Program Execution
# =======================
if __name__ == "__main__":
    main_menu()
