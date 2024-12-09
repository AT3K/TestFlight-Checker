#!/usr/bin/env python3

# ======================
# Script Starts Here
#========================

import json
import os
import subprocess
import shutil
import requests
from packaging import version
import re
import logging
from typing import Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# =======================
# Configuration & Constants
# =======================
MULTIPLE_INSTANCES = False  # Set to True to allow multiple instances, False to allow only a single instance
CURRENT_VERSION = "v0.1.2-beta"  # Current version of the application
CONFIG_FILE_PATH = "apps_config.json"  # Path to the apps configuration file
PM2_PROCESS_NAME = "testflight_checker"  # Name of the PM2 process
WEBHOOK_URL_PATTERN = r"^https://discord\.com/api/webhooks/\d+/[A-Za-z0-9_-]+$"  # Regex pattern to validate Discord webhook URL

# =======================
# Utility Functions
# =======================
def safe_subprocess_run(command: list, check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    """
    Safely run subprocess commands with enhanced error handling and security.

    Args:
        command (list): Command to run as a list of strings - MUST be a static, predefined list
        check (bool): Raise an exception if the command returns a non-zero exit code
        capture_output (bool): Capture stdout and stderr

    Returns:
        subprocess.CompletedProcess: Result of the subprocess command
    """
    try:
        # Ensure command is a list of strings and contains no dynamic content
        sanitized_command = [str(arg) for arg in command]

        return subprocess.run(
            sanitized_command,
            check=check,
            capture_output=capture_output,
            text=True,
            # Explicitly set shell to False for security
            shell=False,
            # Add additional security measures
            encoding='utf-8',
            errors='strict'
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Command execution failed: {e}")
        logger.error(f"Command: {' '.join(sanitized_command)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error running command: {e}")
        raise

def is_tool_installed(tool_name: str) -> bool:
    """Check if a tool is installed and accessible."""
    return shutil.which(tool_name) is not None

# =======================
# Webhook Management
# =======================
def create_env_file() -> None:
    """Create the .env file with an empty DISCORD_WEBHOOK_URL if it doesn't exist."""
    if not os.path.exists(".env"):
        with open(".env", "w") as file:
            file.write("DISCORD_WEBHOOK_URL=''\n")
        logger.info(".env file created with an empty DISCORD_WEBHOOK_URL.")

def check_webhook() -> bool:
    """Check if the webhook URL is set in the .env file."""
    create_env_file()  # Ensure .env file exists
    with open(".env", "r") as file:
        for line in file:
            if line.startswith("DISCORD_WEBHOOK_URL="):
                webhook_url = line.strip().split("=")[1].strip("'")
                return bool(webhook_url)
    return False

def validate_discord_webhook_format(webhook_url: str) -> bool:
    """Validate the format of the Discord webhook URL."""
    if re.match(WEBHOOK_URL_PATTERN, webhook_url):
        return True
    logger.warning("Invalid Discord webhook URL format.")
    logger.warning("The correct format is: https://discord.com/api/webhooks/<webhook_id>/<webhook_token>")
    return False

def validate_discord_webhook(webhook_url: str, timeout: int = 10) -> bool:
    """Validate the Discord webhook URL by sending a test message."""
    if not validate_discord_webhook_format(webhook_url):
        return False

    test_data = {
        "content": "Test message from TestFlight Manager to validate webhook."
    }

    try:
        response = requests.post(webhook_url, json=test_data, timeout=timeout)
        response.raise_for_status()

        logger.info("Discord webhook URL is valid.")
        return True
    except (requests.exceptions.RequestException, ValueError) as e:
        logger.error(f"Error validating Discord webhook: {e}")
        return False

# =======================
# App Management Functions
# =======================
def load_apps() -> Dict[str, str]:
    """Load the apps configuration from the JSON file."""
    if not os.path.exists(CONFIG_FILE_PATH):
        logger.info("Configuration file not found. Creating a new blank file.")
        save_apps({})
        return {}

    try:
        with open(CONFIG_FILE_PATH, "r") as file:
            apps = json.load(file)
        return apps
    except json.JSONDecodeError:
        logger.warning("Configuration file is corrupted. Creating a new blank file.")
        save_apps({})
        return {}

def save_apps(apps: Dict[str, str]) -> None:
    """Save the apps configuration to the JSON file."""
    with open(CONFIG_FILE_PATH, "w") as file:
        json.dump(apps, file, indent=4)
        logger.info("Configuration saved.")

def list_apps() -> None:
    """List all configured apps."""
    apps = load_apps()
    if apps:
        print("\nConfigured Apps:")
        for name in apps.keys():
            print(f"- {name}")
    else:
        print("\nNo apps are configured.")

def add_app() -> None:
    """Add a new app to the configuration."""
    app_name = input("Enter the app name: ").strip()
    if not app_name:
        logger.warning("App name cannot be empty.")
        return

    testflight_url = input("Enter the TestFlight URL: ").strip()

    if not testflight_url.startswith("https://testflight.apple.com/join/"):
        logger.warning("Invalid URL format. The URL must start with 'https://testflight.apple.com/join/'.")
        return

    apps = load_apps()
    apps[app_name] = testflight_url
    save_apps(apps)

    restart_checker()

def remove_app() -> None:
    """Remove an app from the configuration."""
    apps = load_apps()

    if not apps:
        logger.warning("No apps to remove.")
        return

    print("Select an app to remove:")
    for idx, (name, _) in enumerate(apps.items(), start=1):
        print(f"{chr(64 + idx)}. {name}")

    app_choice = input("Enter the option (A, B, C, etc.): ").strip().upper()

    if not app_choice.isalpha() or ord(app_choice) < 65 or ord(app_choice) > 65 + len(apps) - 1:
        logger.warning("Invalid option.")
        return

    app_index = ord(app_choice) - 65
    app_name = list(apps.keys())[app_index]

    del apps[app_name]
    save_apps(apps)
    logger.info(f"App '{app_name}' removed.")

    restart_checker()

# =======================
# Process Management (PM2)
# =======================
def start_checker() -> None:
    """Start the slot checker using PM2."""
    create_env_file()

    if not is_tool_installed("pm2"):
        logger.error("PM2 is not installed or not accessible.")
        print("Install PM2 using:")
        print("1. sudo apt update")
        print("2. sudo apt install nodejs npm -y")
        print("3. sudo npm install -g pm2")
        return

    if not MULTIPLE_INSTANCES:
        try:
            safe_subprocess_run(["pm2", "delete", PM2_PROCESS_NAME], check=False)
        except subprocess.CalledProcessError:
            pass  # Ignore if process doesn't exist

    try:
        safe_subprocess_run(["pm2", "start", "testflight_checker.py", "--name", PM2_PROCESS_NAME, "--update-env", "-f"])
        safe_subprocess_run(["pm2", "save"])

        logger.info("Slot checker started with updated environment variables.")

        if not check_webhook():
            logger.warning("Webhook URL is empty. Notifications are not set.")

        if not os.path.exists(CONFIG_FILE_PATH):
            save_apps({})
            logger.info("Created new configuration file.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start checker: {e}")

def stop_checker() -> None:
    """Stop the slot checker using PM2."""
    if not is_tool_installed("pm2"):
        logger.error("PM2 is not installed or not accessible.")
        return

    try:
        safe_subprocess_run(["pm2", "stop", PM2_PROCESS_NAME])
        logger.info("Slot checker stopped.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to stop checker: {e}")

def restart_checker() -> None:
    """Restart the slot checker using PM2."""
    create_env_file()

    if not is_tool_installed("pm2"):
        logger.error("PM2 is not installed or not accessible.")
        return

    try:
        safe_subprocess_run(["pm2", "restart", PM2_PROCESS_NAME])
        safe_subprocess_run(["pm2", "save"])

        logger.info("Slot checker restarted with updated environment variables.")

        if not check_webhook():
            logger.warning("Webhook URL is empty. Notifications are not set.")

        if not os.path.exists(CONFIG_FILE_PATH):
            save_apps({})
            logger.info("Created new configuration file.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to restart checker: {e}")

# =======================
# Advanced Options (Updates and Webhook)
# =======================
def advanced_options() -> None:
    """Advanced options menu."""
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

def update_webhook() -> None:
    """Update the webhook URL in the .env file."""
    webhook_url = input("Enter the new webhook URL: ").strip()

    if not webhook_url:
        logger.warning("Webhook URL not updated.")
        return

    if not validate_discord_webhook(webhook_url):
        return

    with open(".env", "r") as file:
        lines = file.readlines()

    with open(".env", "w") as file:
        for line in lines:
            if line.startswith("DISCORD_WEBHOOK_URL="):
                file.write(f"DISCORD_WEBHOOK_URL='{webhook_url}'\n")
            else:
                file.write(line)

    logger.info("Webhook URL updated in the .env file.")
    restart_checker()

def check_for_updates() -> None:
    """Check for updates from GitHub."""
    release_type = input("Which version would you like to check for? (beta or stable): ").strip().lower()

    if release_type not in ["beta", "stable"]:
        logger.warning("Invalid option. Please choose either 'beta' or 'stable'.")
        return

    github_api_url = "https://api.github.com/repos/AT3K/TestFlight-Checker/releases"

    try:
        response = requests.get(github_api_url, timeout=10)
        response.raise_for_status()

        current_version_str = CURRENT_VERSION.lstrip("v")
        current_version = version.parse(current_version_str)

        releases = response.json()

        beta_versions = [
            tag_name for release in releases
            if (tag_name := release['tag_name']) and ('-alpha' in tag_name or '-beta' in tag_name)
        ]
        stable_versions = [
            tag_name for release in releases
            if (tag_name := release['tag_name']) and ('-alpha' not in tag_name and '-beta' not in tag_name)
        ]

        latest_beta_version = max([version.parse(v.lstrip("v")) for v in beta_versions], default=None)
        latest_stable_version = max([version.parse(v.lstrip("v")) for v in stable_versions], default=None)

        latest_version = latest_beta_version if release_type == "beta" else latest_stable_version
        version_type = "beta" if release_type == "beta" else "stable"

        if latest_version:
            logger.info(f"Latest {version_type} release: {latest_version}")

            if latest_version > current_version:
                pull_update = input(f"Would you like to pull the latest {version_type} version? (y/n): ").strip().lower()
                if pull_update == "y":
                    pull_latest_update()
            elif latest_version < current_version:
                logger.info("You have a build higher than the latest release. You must be a developer or a secret tester! 🧑‍💻")
            else:
                logger.info(f"You are already on the latest {version_type} version!")
        else:
            logger.warning(f"No {version_type} versions available.")

    except (requests.exceptions.RequestException, ValueError) as e:
        logger.error(f"Error checking for updates: {e}")

def pull_latest_update() -> None:
    """Pull the latest changes from the GitHub repository."""
    if not is_tool_installed("git"):
        logger.error("Git is not installed. Please install Git and try again.")
        return

    if not os.path.isdir(".git"):
        logger.error("This is not a Git repository. Please initialize a Git repository first.")
        return

    logger.info("Pulling the latest updates from the repository...")
    try:
        result = safe_subprocess_run(["git", "pull"], capture_output=True)
        logger.info(f"Update result: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to pull updates: {e}")

# =======================
# Main Menu & Program Flow
# =======================
def main_menu() -> None:
    """Main program menu."""
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
