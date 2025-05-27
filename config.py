import os
import logging
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv # For local development

# Load environment variables from .env file if it exists (for local development)
# In AWS Lambda, environment variables are set in the function's configuration
load_dotenv()

# ---- Logger setup ----
logger = logging.getLogger(__name__)

# ---- Google Sheets Configuration ----
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Path to the service account key file from environment variable
# For AWS Lambda, ensure this file is included in your deployment package
# or consider loading credentials from an environment variable containing the JSON content.
SERVICE_ACCOUNT_FILE_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH")
if not SERVICE_ACCOUNT_FILE_PATH:
    logger.critical("GOOGLE_SERVICE_ACCOUNT_PATH environment variable not set!")

# ID of the Google Sheet from environment variable
SHEET_ID = os.getenv("SHEET_ID")
if not SHEET_ID:
    logger.critical("SHEET_ID environment variable not set!")

# ---- Telegram Bot Configuration ----
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.critical("TELEGRAM_TOKEN environment variable not set!")

# Allowed Telegram User IDs from environment variable
ALLOWED_USER_IDS_STR = os.getenv("ALLOWED_USER_IDS")
ALLOWED_USER_IDS = []
if ALLOWED_USER_IDS_STR:
    try:
        ALLOWED_USER_IDS = [int(uid.strip()) for uid in ALLOWED_USER_IDS_STR.split(',')]
    except ValueError:
        logger.error(f"Invalid format for ALLOWED_USER_IDS: '{ALLOWED_USER_IDS_STR}'. Expected comma-separated integers.")
else:
    logger.warning("ALLOWED_USER_IDS environment variable not set or empty. No users will be authorized.")

# ---- Font Configuration ----
# Path to the directory containing font files (e.g., arial.ttf, arialbd.ttf)
# Set via FONT_PATH environment variable. Defaults to current directory if not set.
FONT_PATH = os.getenv("FONT_PATH", ".")

# ---- Logging Configuration ----
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# ---- Initialize Google Credentials ----
# This is kept separate to allow other modules to import config values
# without immediately trying to load credentials if they are not needed.
def get_google_credentials():
    """
    Loads Google service account credentials from the path specified
    in the GOOGLE_SERVICE_ACCOUNT_PATH environment variable.
    """
    if not SERVICE_ACCOUNT_FILE_PATH:
        logger.error("Cannot load Google credentials: GOOGLE_SERVICE_ACCOUNT_PATH is not set.")
        return None
    try:
        return Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE_PATH,
            scopes=SCOPES
        )
    except FileNotFoundError:
        logger.error(f"Service account file not found at: {SERVICE_ACCOUNT_FILE_PATH}")
        return None
    except Exception as e:
        logger.error(f"Error loading Google credentials from {SERVICE_ACCOUNT_FILE_PATH}: {e}", exc_info=True)
        return None
