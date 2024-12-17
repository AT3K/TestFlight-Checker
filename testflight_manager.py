################################################################################
# TestFlight Manager
# Description: Utility script to monitor Apple TestFlight beta slots and send Discord notifications
# Features: Multi-app monitoring, Discord webhooks, PM2 process management, Auto-updates
################################################################################

################################################################################
#                           ⚙️ USER CONFIGURATION ⚙️                             #
#            Safe to modify settings in this section as needed                   #
################################################################################
MULTIPLE_INSTANCES = False  # Set to True for multiple simultaneous instances, False for single instance (recommended)

################################################################################
#                               ⚠️ WARNING ⚠️                                    #
#        DO NOT MODIFY ANY CODE BELOW THIS LINE - SYSTEM CRITICAL               #
################################################################################

################################################################################
# Imports 
################################################################################
import json,os,subprocess,shutil,requests,re,logging,unicodedata
from packaging import version
from typing import Dict

################################################################################
# Logging Setup
################################################################################
logging.basicConfig(level=logging.INFO,format='%(asctime)s [%(levelname)s] %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

################################################################################
# Constants
################################################################################
CURRENT_VERSION = "v0.1.3-beta"
CONFIG_FILE_PATH = "apps_config.json"
PM2_PROCESS_NAME = "testflight_checker"
WEBHOOK_URL_PATTERN = r"^https://discord\.com/api/webhooks/\d+/[A-Za-z0-9_-]+$"

################################################################################
# Utility Functions
################################################################################
def safe_subprocess_run(command:list,check:bool=True,capture_output:bool=False)->subprocess.CompletedProcess:
    try:
        sanitized_command = [str(arg) for arg in command]
        return subprocess.run(sanitized_command,check=check,capture_output=capture_output,text=True,shell=False,encoding='utf-8',errors='strict')
    except subprocess.CalledProcessError as e:
        logger.error(f"Command execution failed: {e}")
        logger.error(f"Command: {' '.join(sanitized_command)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error running command: {e}")
        raise

def is_tool_installed(tool_name:str)->bool:
    return shutil.which(tool_name) is not None

################################################################################
# Webhook Management
################################################################################
def create_env_file()->None:
    if not os.path.exists(".env"):
        with open(".env","w") as f:f.write("DISCORD_WEBHOOK_URL=''\n")
        logger.info(".env file created with empty DISCORD_WEBHOOK_URL.")

def check_webhook()->bool:
    create_env_file()
    with open(".env","r") as f:
        for line in f:
            if line.startswith("DISCORD_WEBHOOK_URL="):
                return bool(line.strip().split("=")[1].strip("'"))
    return False

def validate_discord_webhook_format(webhook_url:str)->bool:
    if re.match(WEBHOOK_URL_PATTERN,webhook_url):return True
    logger.warning("Invalid Discord webhook URL format.")
    logger.warning("Format: https://discord.com/api/webhooks/<webhook_id>/<webhook_token>")
    return False

def validate_discord_webhook(webhook_url:str,timeout:int=10)->bool:
    if not validate_discord_webhook_format(webhook_url):return False
    try:
        response=requests.post(webhook_url,json={"content":"Test message from TestFlight Manager"},timeout=timeout)
        response.raise_for_status()
        logger.info("Discord webhook URL is valid.")
        return True
    except (requests.exceptions.RequestException,ValueError) as e:
        logger.error(f"Error validating Discord webhook: {e}")
        return False

################################################################################
# App Management
################################################################################
def load_apps()->Dict[str,str]:
    if not os.path.exists(CONFIG_FILE_PATH):
        logger.info("Config file not found. Creating new blank file.")
        save_apps({})
        return {}
    try:
        with open(CONFIG_FILE_PATH,"r") as f:return json.load(f)
    except json.JSONDecodeError:
        logger.warning("Config file corrupted. Creating new blank file.")
        save_apps({})
        return {}

def save_apps(apps:Dict[str,str])->None:
    with open(CONFIG_FILE_PATH,"w") as f:
        json.dump(apps,f,indent=4)
        logger.info("Configuration saved.")

def list_apps()->None:
    apps=load_apps()
    if apps:
        print("\nConfigured Apps:")
        for name in apps:print(f"- {name}")
    else:print("\nNo apps configured.")

def sanitize_app_name(app_name: str) -> str:
    """
    Sanitizes app names to prevent injection and ensure safe storage.
    Supports international characters (Unicode) while maintaining security.
    
    Args:
        app_name (str): Raw app name input
    Returns:
        str: Sanitized app name
    """
    # Remove control characters but keep unicode letters/numbers from any language
    sanitized = ''.join(char for char in app_name if not unicodedata.category(char).startswith('C'))
    
    # Remove dangerous filesystem characters but keep unicode
    sanitized = re.sub(r'[<>:"/\\|?*]', '', sanitized)
    
    # Replace spaces with underscores
    sanitized = sanitized.replace(' ', '_')
    
    # Limit length to 50 characters (unicode-aware)
    sanitized = sanitized[:50]
    
    # Remove leading/trailing periods or spaces
    sanitized = sanitized.strip('. ')
    
    # Ensure name isn't empty after sanitization
    if not sanitized:
        sanitized = "unnamed_app"
        
    return sanitized

def add_app() -> None:
    """Add a new app with sanitized name validation."""
    raw_app_name = input("Enter app name: ").strip()
    if not raw_app_name:
        logger.warning("App name cannot be empty.")
        return
        
    # Sanitize the app name
    app_name = sanitize_app_name(raw_app_name)
    if app_name != raw_app_name:
        logger.info(f"App name sanitized to: {app_name}")
        if not input("Continue with sanitized name? (y/n): ").lower().startswith('y'):
            logger.info("Operation cancelled.")
            return
            
    testflight_url = input("Enter TestFlight URL: ").strip()
    if not testflight_url.startswith("https://testflight.apple.com/join/"):
        logger.warning("Invalid URL format. Must start with 'https://testflight.apple.com/join/'")
        return
        
    apps = load_apps()
    apps[app_name] = testflight_url
    save_apps(apps)
    restart_checker()

def remove_app()->None:
    apps=load_apps()
    if not apps:
        logger.warning("No apps to remove.")
        return
    print("Select app to remove:")
    for idx,(name,_) in enumerate(apps.items(),1):print(f"{chr(64+idx)}. {name}")
    choice=input("Enter option (A,B,C...): ").strip().upper()
    if not choice.isalpha() or ord(choice)<65 or ord(choice)>64+len(apps):
        logger.warning("Invalid option.")
        return
    app_name=list(apps.keys())[ord(choice)-65]
    del apps[app_name]
    save_apps(apps)
    logger.info(f"App '{app_name}' removed.")
    restart_checker()

################################################################################
# Process Management (PM2)
################################################################################
def start_checker()->None:
    create_env_file()
    if not is_tool_installed("pm2"):
        logger.error("PM2 not installed. Install with:\n1. sudo apt update\n2. sudo apt install nodejs npm -y\n3. sudo npm install -g pm2")
        return
    if not MULTIPLE_INSTANCES:
        try:safe_subprocess_run(["pm2","delete",PM2_PROCESS_NAME],check=False)
        except subprocess.CalledProcessError:pass
    try:
        safe_subprocess_run(["pm2","start","testflight_checker.py","--name",PM2_PROCESS_NAME,"--update-env","-f"])
        safe_subprocess_run(["pm2","save"])
        logger.info("Slot checker started with updated environment variables.")
        if not check_webhook():logger.warning("Webhook URL empty. Notifications not set.")
        if not os.path.exists(CONFIG_FILE_PATH):
            save_apps({})
            logger.info("Created new configuration file.")
    except subprocess.CalledProcessError as e:logger.error(f"Failed to start checker: {e}")

def stop_checker()->None:
    if not is_tool_installed("pm2"):
        logger.error("PM2 not installed.")
        return
    try:
        safe_subprocess_run(["pm2","stop",PM2_PROCESS_NAME])
        logger.info("Slot checker stopped.")
    except subprocess.CalledProcessError as e:logger.error(f"Failed to stop checker: {e}")

def restart_checker()->None:
    create_env_file()
    if not is_tool_installed("pm2"):
        logger.error("PM2 not installed.")
        return
    try:
        safe_subprocess_run(["pm2","restart",PM2_PROCESS_NAME])
        safe_subprocess_run(["pm2","save"])
        logger.info("Slot checker restarted with updated environment variables.")
        if not check_webhook():logger.warning("Webhook URL empty. Notifications not set.")
        if not os.path.exists(CONFIG_FILE_PATH):
            save_apps({})
            logger.info("Created new configuration file.")
    except subprocess.CalledProcessError as e:logger.error(f"Failed to restart checker: {e}")

################################################################################
# Advanced Options
################################################################################
def advanced_options()->None:
    while True:
        print("\nAdvanced Options:\n===================\n1. Update Webhook URL\n2. Check for updates\n3. Back to main menu")
        choice=input("Choose option (1-3): ").strip()
        if choice=="1":update_webhook()
        elif choice=="2":check_for_updates()
        elif choice=="3":break
        else:print("Invalid option.")

def update_webhook()->None:
    webhook_url=input("Enter new webhook URL: ").strip()
    if not webhook_url:
        logger.warning("Webhook URL not updated.")
        return
    if not validate_discord_webhook(webhook_url):return
    with open(".env","r") as f:lines=f.readlines()
    with open(".env","w") as f:
        for line in lines:
            f.write(f"DISCORD_WEBHOOK_URL='{webhook_url}'\n" if line.startswith("DISCORD_WEBHOOK_URL=") else line)
    logger.info("Webhook URL updated.")
    restart_checker()

def check_for_updates()->None:
    release_type=input("Check version type (beta/stable): ").strip().lower()
    if release_type not in ["beta","stable"]:
        logger.warning("Invalid option. Choose 'beta' or 'stable'.")
        return
    try:
        response=requests.get("https://api.github.com/repos/AT3K/TestFlight-Checker/releases",timeout=10)
        response.raise_for_status()
        current_version=version.parse(CURRENT_VERSION.lstrip("v"))
        releases=response.json()
        beta_versions=[tag for release in releases if (tag:=release['tag_name']) and ('-alpha' in tag or '-beta' in tag)]
        stable_versions=[tag for release in releases if (tag:=release['tag_name']) and '-alpha' not in tag and '-beta' not in tag]
        latest_version=max([version.parse(v.lstrip("v")) for v in (beta_versions if release_type=="beta" else stable_versions)],default=None)
        if latest_version:
            logger.info(f"Latest {release_type} release: {latest_version}")
            if latest_version>current_version:
                if input(f"Pull latest {release_type} version? (y/n): ").strip().lower()=="y":pull_latest_update()
            elif latest_version<current_version:logger.info("You have a development build! 🧑‍💻")
            else:logger.info(f"Already on latest {release_type} version!")
        else:logger.warning(f"No {release_type} versions available.")
    except (requests.exceptions.RequestException,ValueError) as e:logger.error(f"Update check failed: {e}")

def pull_latest_update()->None:
    if not is_tool_installed("git"):
        logger.error("Git not installed.")
        return
    if not os.path.isdir(".git"):
        logger.error("Not a Git repository.")
        return
    logger.info("Pulling updates...")
    try:
        result=safe_subprocess_run(["git","pull"],capture_output=True)
        logger.info(f"Update result: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:logger.error(f"Update failed: {e}")

################################################################################
# Main Menu
################################################################################
def main_menu()->None:
    while True:
        print("\nMain Menu:\n=================")
        print("1. List apps\n2. Add app\n3. Remove app\n4. Start checker")
        print("5. Stop checker\n6. Restart checker\n7. Advanced options\n8. Exit")
        choice=input("Choose option (1-8): ").strip()
        if choice=="1":list_apps()
        elif choice=="2":add_app()
        elif choice=="3":remove_app()
        elif choice=="4":start_checker()
        elif choice=="5":stop_checker()
        elif choice=="6":restart_checker()
        elif choice=="7":advanced_options()
        elif choice=="8":
            print("Exiting...")
            break
        else:print("Invalid option.")

################################################################################
# Entry Point
################################################################################
if __name__=="__main__":main_menu()
