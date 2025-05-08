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
_placeholder_bot_token = "YOUR_FALLBACK_BOT_TOKEN_PLEASE_SET"
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN or BOT_TOKEN.strip() == "" or BOT_TOKEN == _placeholder_bot_token:
    logger.critical(
        f"CRITICAL FAILURE: BOT_TOKEN is missing, empty, or still set to the placeholder value ('{_placeholder_bot_token}') in your .env file. "
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
        "If USE_WEBHOOK is True, this will be an issue. "
        "Otherwise, the bot will default to POLLING mode."
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

# 4. Webhook Path (User-configured, for Webhook deployment)
# The specific URL path Telegram will send updates to, e.g., /yourwebhookpath
# It's crucial this path starts with a '/'.
# Note: main.py might generate its own secure path and ignore this if not secure enough.
_default_webhook_path = "/webhook" # A generic default
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH") # Allow it to be None if not set
if WEBHOOK_PATH and not WEBHOOK_PATH.startswith("/"):
    logger.warning(
        f"WARNING: WEBHOOK_PATH ('{WEBHOOK_PATH}') in .env does not start with '/'. "
        f"This may cause issues if used directly. Recommended format: '/yourpath'."
    )
    # main.py handles secure path generation, so this is more of an advisory
    # if the user intends to use a specific fixed path.
elif not WEBHOOK_PATH:
    logger.info(
        f"INFO: WEBHOOK_PATH not set in .env. main.py will generate a secure path if in webhook mode."
    )


# --- Operational Mode & Admin ---
# 5. Admin Chat ID (Optional, for notifications)
ADMIN_CHAT_ID_STR = os.getenv("ADMIN_CHAT_ID")
ADMIN_CHAT_ID = None
if ADMIN_CHAT_ID_STR:
    try:
        ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_STR)
    except ValueError:
        logger.warning(
            f"WARNING: Invalid ADMIN_CHAT_ID value ('{ADMIN_CHAT_ID_STR}') in .env. It should be an integer. Admin notifications might fail."
        )
else:
    logger.info(
        "INFO: ADMIN_CHAT_ID is not set in .env. Startup/error notifications to admin will be disabled if main.py relies on this."
    )

# 6. Development Mode (Boolean)
# Affects logging level and potentially other debug features.
DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "False").lower() in ("true", "1", "yes")

# 7. Use Webhook (Boolean)
# Determines if the bot should run in webhook or polling mode.
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "False").lower() in ("true", "1", "yes")
if WEBHOOK_URL and not USE_WEBHOOK:
    logger.info("INFO: WEBHOOK_URL is set, but USE_WEBHOOK is False. Bot will run in POLLING mode.")
if not WEBHOOK_URL and USE_WEBHOOK:
    logger.warning("WARNING: USE_WEBHOOK is True, but WEBHOOK_URL is not set. Webhook mode will likely fail.")


# --- Logging Configuration ---
# 8. Log File Path (Optional)
# Path for file-based logging, if enabled in main.py.
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH") # Can be None if not set


# --- Configuration Load Summary (for startup logs, helps in deployment) ---
def log_config_summary():
    """Logs a summary of the loaded configurations."""
    logger.info("--- Configuration Settings Loaded (config/settings.py) ---")
    if BOT_TOKEN:
        try:
            # Try to show last 4 chars, but handle short tokens gracefully
            token_display = f"...{BOT_TOKEN[-4:]}" if len(BOT_TOKEN) > 4 else "(Token is very short)"
            logger.info(f"  BOT_TOKEN: Loaded (Verified by presence, ending with '{token_display}')")
        except TypeError: # Should not happen if BOT_TOKEN is string, but defensive
             logger.info(f"  BOT_TOKEN: Loaded (Presence verified, type issue with display)")
    else:
        logger.error("  BOT_TOKEN: ❌ CRITICALLY MISSING OR INVALID ❌")

    logger.info(f"  DEVELOPMENT_MODE: {DEVELOPMENT_MODE}")
    logger.info(f"  USE_WEBHOOK: {USE_WEBHOOK}")

    if USE_WEBHOOK:
        if WEBHOOK_URL:
            logger.info(f"  WEBHOOK_URL: {WEBHOOK_URL}")
            logger.info(f"  PORT (for Webhook): {PORT}")
            if WEBHOOK_PATH:
                logger.info(f"  WEBHOOK_PATH (user configured): {WEBHOOK_PATH}")
            else:
                logger.info(f"  WEBHOOK_PATH (user configured): Not set (main.py will auto-generate)")
        else:
            # This warning is already covered when USE_WEBHOOK is processed
            pass # logger.warning("  WEBHOOK_URL: Not set, critical for webhook mode.")
    else:
        logger.info("  (Polling mode indicated by USE_WEBHOOK=False)")

    if ADMIN_CHAT_ID:
        logger.info(f"  ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
    else:
        logger.info("  ADMIN_CHAT_ID: Not set or invalid.")

    if LOG_FILE_PATH:
        logger.info(f"  LOG_FILE_PATH: {LOG_FILE_PATH}")
    else:
        logger.info("  LOG_FILE_PATH: Not set (File logging in main.py will be disabled if it relies on this).")

    logger.info("---------------------------------------------------------")

# Call the summary log function when the module is loaded.
# This ensures that as soon as settings are imported, a summary is logged.
# Ensure basicConfig for logging is set in main.py before this module is imported if you want these logs to appear formatted.
# If this module is imported before logging is configured, these logs might go to a default handler or be lost.
# However, for critical issues like missing BOT_TOKEN, immediate logging here is valuable.
if __name__ != "main": # Avoid double logging if main.py also calls this, though unlikely
    # To ensure these logs are seen even if main.py hasn't set up full logging yet,
    # a minimal basicConfig could be placed at the very top of this file for this logger,
    # but generally, main entry point config is cleaner.
    # For now, we assume that if main.py imports this, logging is configured or will be soon.
    pass

log_config_summary()