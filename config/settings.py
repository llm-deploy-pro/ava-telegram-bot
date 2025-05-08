# config/settings.py

import os
import logging
from dotenv import load_dotenv

# It's good practice to load .env as early as possible.
# This will load variables from a .env file in the project root.
load_dotenv()

# Configure a logger for this module.
# It's recommended to configure basicConfig in your main entry point (e.g., main.py)
# for application-wide logging settings. However, getting a logger instance here is fine.
logger = logging.getLogger(__name__)

# --- Core Application Configurations ---

# 1. Telegram Bot Token (CRITICAL)
# This token is essential for the bot to connect to the Telegram API.
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN or BOT_TOKEN.strip() == "" or BOT_TOKEN == "YOUR_FALLBACK_BOT_TOKEN_PLEASE_SET": # Added placeholder check
    logger.critical(
        "CRITICAL FAILURE: BOT_TOKEN is missing, empty, or still set to the placeholder value in your .env file. "
        "The Telegram Bot CANNOT start without a valid token. "
        "Please ensure a .env file exists in the project root and contains a valid 'BOT_TOKEN=your_actual_token'."
    )
    BOT_TOKEN = None # Explicitly None, main.py MUST check this before proceeding.

# 2. Webhook Base URL (Optional, for Webhook deployment)
# Example: https://your-app-name.onrender.com
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    logger.info(
        "INFO: WEBHOOK_URL is not set in the .env file. "
        "The bot will default to using POLLING mode for updates. "
        "For production webhook deployment, ensure WEBHOOK_URL is correctly configured."
    )

# 3. Webhook Port (For Webhook deployment)
# Render.com and similar platforms often inject the PORT environment variable.
# Defaults to 8080 if not set or if the value is invalid.
_default_port = 8080
try:
    PORT = int(os.getenv("PORT", str(_default_port))) # Provide string default to int()
except ValueError:
    logger.warning(
        f"WARNING: Invalid PORT value ('{os.getenv('PORT')}') in .env. Defaulting to {_default_port}."
    )
    PORT = _default_port

# 4. Webhook Path (For Webhook deployment)
# The specific URL path Telegram will send updates to, e.g., /yourwebhookpath
# It's crucial this path starts with a '/'.
_default_webhook_path = "/webhook"
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", _default_webhook_path)
if not WEBHOOK_PATH.startswith("/"):
    logger.warning(
        f"WARNING: WEBHOOK_PATH ('{WEBHOOK_PATH}') in .env does not start with '/'. "
        f"This may cause issues with webhook registration. Recommended format: '/yourpath'. "
        f"Consider correcting it or relying on the default '{_default_webhook_path}' if applicable."
    )
    # For robustness, one might choose to enforce a default here if the format is critical,
    # but for now, a strong warning is issued.
    # Example enforcement: WEBHOOK_PATH = _default_webhook_path

# --- Optional Configurations (Reserved for future use) ---
# DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() in ("true", "1", "yes")
# API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
# logger.info(f"Debug mode: {'Enabled' if DEBUG_MODE else 'Disabled'}")
# logger.info(f"API Timeout: {API_TIMEOUT} seconds")

# --- Configuration Load Summary (for startup logs, helps in deployment) ---
# This section should ideally be called once after all configurations are attempted.
# Placing it here means it runs when this module is imported.

def log_config_summary():
    """Logs a summary of the loaded configurations."""
    logger.info("--- Configuration Settings Loaded (config/settings.py) ---")
    if BOT_TOKEN:
        logger.info(f"  BOT_TOKEN: Loaded (Verified by presence, ending with '...{BOT_TOKEN[-4:]}')")
    else:
        logger.error("  BOT_TOKEN: ❌ CRITICALLY MISSING OR INVALID ❌")

    if WEBHOOK_URL:
        logger.info(f"  WEBHOOK_URL: {WEBHOOK_URL}")
        logger.info(f"  PORT (for Webhook): {PORT}")
        logger.info(f"  WEBHOOK_PATH: {WEBHOOK_PATH}")
    else:
        logger.info("  WEBHOOK_URL: Not set (Implies Polling mode or manual webhook setup needed).")
    logger.info("---------------------------------------------------------")

# Call the summary log function when the module is loaded.
# This ensures that as soon as settings are imported, a summary is logged.
log_config_summary()
