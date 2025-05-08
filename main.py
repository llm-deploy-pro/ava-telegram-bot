# main.py

import logging
import asyncio
import signal
import os
import secrets # For secure webhook path
from urllib.parse import urlparse
from datetime import timedelta
import logging.handlers # ✅ Item 5 (from review): For RotatingFileHandler
import time # Added for startup message timestamp

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    PicklePersistence # ✅ Item 4 (from review): Enable persistence
)

# --- Attempt to import configurations and handlers ---
# Assume settings.py loads BOT_TOKEN, WEBHOOK_URL, PORT, CFG_WEBHOOK_PATH, ADMIN_CHAT_ID, DEVELOPMENT_MODE, USE_WEBHOOK
try:
    from config.settings import (
        BOT_TOKEN, WEBHOOK_URL, PORT,
        WEBHOOK_PATH as CFG_WEBHOOK_PATH, # User configured path (might be ignored if not secure)
        ADMIN_CHAT_ID, DEVELOPMENT_MODE, USE_WEBHOOK,
        LOG_FILE_PATH # ✅ Item 5: Expect log file path from settings
    )
except ImportError:
    # Critical fallback logging setup
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.CRITICAL)
    logging.critical("CRITICAL: Failed to import required variables from config.settings.py.")
    # Set minimal defaults to allow basic error checks
    BOT_TOKEN = os.getenv("BOT_TOKEN", "CRITICAL_FAILURE_TOKEN_MISSING")
    WEBHOOK_URL = None; PORT = 8080; CFG_WEBHOOK_PATH = None; ADMIN_CHAT_ID = None; LOG_FILE_PATH = None
    DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "False").lower() in ("true", "1", "yes")
    USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"


# --- Configure Logging ---
log_level = logging.DEBUG if DEVELOPMENT_MODE else logging.INFO
log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"

# Setup basic console logging first
logging.basicConfig(
    format=log_format,
    level=log_level,
    handlers=[logging.StreamHandler()] # Console output
)

# Silence overly verbose libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.INFO if not DEVELOPMENT_MODE else logging.DEBUG)
logger = logging.getLogger(__name__) # Logger for this main module

# ✅ Item 5 (from review): Setup File Logging if path is configured
if LOG_FILE_PATH:
    try:
        # Use RotatingFileHandler for log rotation (10MB per file, keep 5 backups)
        file_formatter = logging.Formatter(log_format)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE_PATH, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setFormatter(file_formatter)
        # Add the handler to the root logger to capture logs from all modules
        logging.getLogger().addHandler(file_handler)
        logger.info(f"File logging enabled. Outputting to: {LOG_FILE_PATH}")
    except Exception as e:
        logger.error(f"Failed to configure file logging to {LOG_FILE_PATH}: {e}", exc_info=True)
else:
    logger.info("File logging disabled (LOG_FILE_PATH not set in config/settings.py).")


# --- Import Handlers (Robust Placeholders) ---
# These imports MUST be replaced with actual handler functions as they are developed.
try:
    from handlers.step_1 import step_one_entry
except ImportError:
    logger.warning("Using placeholder for step_1_entry.")
    async def step_one_entry(u: Update, c: ContextTypes.DEFAULT_TYPE): # Added type hints for clarity
        await u.message.reply_text("[SYS_ERR] H1 Missing.")
        return ConversationHandler.END # type: ignore

# Import placeholders for handlers that specific CH states will point to
async def awaiting_step_two_ack_handler(u: Update,c: ContextTypes.DEFAULT_TYPE): logger.info("Placeholder: Awaiting Step 2 Ack handler"); return # type: ignore
async def awaiting_step_three_ack_handler(u: Update,c: ContextTypes.DEFAULT_TYPE): logger.info("Placeholder: Awaiting Step 3 Ack handler"); return # type: ignore
async def awaiting_step_five_choice_callback_handler(u: Update,c: ContextTypes.DEFAULT_TYPE): logger.info("Placeholder: Awaiting Step 5 Choice CB handler"); await u.callback_query.answer(); return # type: ignore
async def awaiting_step_five_choice_text_handler(u: Update,c: ContextTypes.DEFAULT_TYPE): logger.info("Placeholder: Awaiting Step 5 Choice text handler"); return # type: ignore
async def step_five_cta_text_handler(u: Update,c: ContextTypes.DEFAULT_TYPE): logger.info("Placeholder: Step 5 CTA text handler"); return # type: ignore
async def step_five_final_chance_handler(u: Update,c: ContextTypes.DEFAULT_TYPE): logger.info("Placeholder: Step 5 Final Chance handler"); return # type: ignore

try:
    from handlers.unknown import handle_unknown_message, handle_unknown_command, handle_unknown_callback
except ImportError:
    logger.warning("Using placeholders for unknown handlers.")
    async def handle_unknown_message(u: Update, c: ContextTypes.DEFAULT_TYPE): # Added type hints
        await u.message.reply_text("[SYS] Unknown input (text).") # type: ignore
        return

    async def handle_unknown_command(u: Update, c: ContextTypes.DEFAULT_TYPE): # Added type hints
        await u.message.reply_text("[SYS] Unknown input (command).") # type: ignore
        return

    async def handle_unknown_callback(u: Update, c: ContextTypes.DEFAULT_TYPE): # Added type hints
        if u.callback_query:
            await u.callback_query.answer("Unknown callback action.", show_alert=False)
        await u.effective_message.reply_text("[SYS] Unknown input (callback).") # type: ignore
        return

try:
    from utils.state_definitions import * # Import all states
    if 'STATE_NAME_MAP' not in globals() or not isinstance(STATE_NAME_MAP, dict): raise ImportError("STATE_NAME_MAP missing")
except ImportError:
    logger.critical("CRITICAL: utils/state_definitions.py / STATE_NAME_MAP missing. Using fallbacks.")
    AWAITING_STEP_TWO_ACK, AWAITING_STEP_THREE_ACK, AWAITING_STEP_FIVE_CHOICE = 0,1,2 # type: ignore
    STEP_5_AWAITING_FINAL_ACTION, STEP_5_FINAL_CHANCE_STATE = 3, 4 # type: ignore
    STATE_NAME_MAP = {0:"S2_ACK_FB", 1:"S3_ACK_FB", 2:"S5_CHOICE_FB", 3:"S5_ACTION_FB", 4:"S5_FINAL_FB"} # type: ignore


# --- Global Variables ---
shutdown_event = asyncio.Event()
application: ApplicationBuilder.application_type | None = None
FINAL_WEBHOOK_PATH = None

# --- Secure Webhook Path Generation ---
# ✅ Item 3 (from review): Enhanced security for Webhook Path
def setup_secure_webhook_path() -> None:
    """Determines the final, secure webhook path."""
    global FINAL_WEBHOOK_PATH
    if not WEBHOOK_URL: return # Not needed for polling

    # Use a highly unpredictable, URL-safe random string as the path base
    # Prepending with a short, non-obvious prefix is optional but can help routing/identification
    secure_suffix = secrets.token_urlsafe(16) # Generate 16 URL-safe random bytes
    FINAL_WEBHOOK_PATH = f"/tgwh_{secure_suffix}" # Example prefix + random string
    logger.info(f"Using secure, auto-generated WEBHOOK_PATH: {FINAL_WEBHOOK_PATH}")
    # Disregard CFG_WEBHOOK_PATH from settings unless a specific need arises to override this secure generation

# --- Signal Handler ---
def graceful_signal_handler(sig, frame):
    logger.info(f"Signal {sig} received. Initiating graceful shutdown...")
    if loop := asyncio.get_running_loop(): loop.call_soon_threadsafe(shutdown_event.set)
    else: shutdown_event.set()

# --- Post Initialization Hook ---
async def post_initialization_hook(app: ApplicationBuilder.application_type) -> None:
    global FINAL_WEBHOOK_PATH
    webhook_setup_successful = False
    allowed_updates = [Update.MESSAGE, Update.CALLBACK_QUERY] # Be specific
    full_webhook_url = "N/A (Polling or Setup Failed)" # Initialize for startup message

    if USE_WEBHOOK and WEBHOOK_URL and FINAL_WEBHOOK_PATH and BOT_TOKEN and not BOT_TOKEN.startswith("CRITICAL_FAILURE_TOKEN_MISSING"): # Check against fallback token
        parsed_url = urlparse(WEBHOOK_URL)
        if not parsed_url.scheme == "https" or not parsed_url.netloc:
            logger.critical(f"Webhook URL '{WEBHOOK_URL}' invalid. Webhook NOT set.")
        else:
            full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}{FINAL_WEBHOOK_PATH}"
            logger.info(f"Attempting to set webhook: {full_webhook_url}")
            # ✅ Item 4 (from review): Webhook Setup Retry Logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await app.bot.set_webhook(url=full_webhook_url, allowed_updates=allowed_updates, drop_pending_updates=True)
                    webhook_info = await app.bot.get_webhook_info()
                    if webhook_info.url == full_webhook_url:
                        logger.info(f"Webhook set successfully on attempt {attempt + 1}: {webhook_info.url}")
                        webhook_setup_successful = True
                        break # Exit retry loop on success
                    else:
                        logger.warning(f"Webhook set attempt {attempt + 1} failed. API returned different URL. Got: {webhook_info.url}")
                except Exception as e:
                    logger.error(f"Error setting webhook on attempt {attempt + 1}: {e}", exc_info=(attempt == max_retries - 1)) # Log full traceback on last attempt
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt # Exponential backoff (1, 2, 4 seconds)
                    logger.info(f"Retrying webhook setup in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
            if not webhook_setup_successful:
                 logger.critical("CRITICAL: Failed to set webhook after multiple retries. Bot may not receive updates in webhook mode.")
                 full_webhook_url = "N/A (Setup FAILED!)"

    else:
        logger.info("Skipping webhook setup (Polling mode or invalid config/token).")
        full_webhook_url = "N/A (Polling)"


    if app.job_queue: logger.info(f"JobQueue initialized. Jobs: {len(app.job_queue.jobs())}")
    else: logger.warning("JobQueue not available.")

    if ADMIN_CHAT_ID:
        mode = "Webhook (Active)" if webhook_setup_successful else ("Webhook (Setup FAILED!)" if USE_WEBHOOK else "Polling")
        try:
            bot_info = await app.bot.get_me()
            # Use escape_markdown for user-generated or potentially unsafe content
            from telegram.helpers import escape_markdown
            safe_bot_username = escape_markdown(bot_info.username if bot_info.username else "N/A_BOT_USERNAME", version=2)
            safe_webhook_url = escape_markdown(full_webhook_url, version=2)
            startup_message = f"✅ *Z1\\-Gray Bot Online*\n*Mode:* `{mode}`\n*Node:* `@{safe_bot_username}`\n*TS:* `{time.strftime('%Y-%m-%d %H:%M:%S %Z')}`"
            if USE_WEBHOOK: startup_message += f"\n*Webhook:* `{safe_webhook_url}`" # Always show webhook URL if USE_WEBHOOK is true
            await app.bot.send_message(chat_id=ADMIN_CHAT_ID, text=startup_message, parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f"Startup notification sent to ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
        except Exception as e: logger.error(f"Failed to send startup notification: {e}")

# --- Conversation Fallback Handler ---
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id_log = user.id if user else "N/A"
    # ✅ Item 5 (from review): Use STATE_NAME_MAP for logging state
    current_state_val = context.user_data.get(ConversationHandler.STATE) if context.user_data else None
    state_name = STATE_NAME_MAP.get(current_state_val, f"UNKNOWN({current_state_val})") if current_state_val is not None else "N/A"
    logger.info(f"[CONV_CANCEL] User {user_id_log} (State: {state_name}) initiated /cancel.")
    # ✅ Item 2 (from review): Clear user_data on cancel
    if context.user_data: context.user_data.clear()
    await update.message.reply_text(
        "`[PROTOCOL_SESSION_TERMINATED]`\n`User directive acknowledged. System reset.`\n`/start` `to re-initiate protocol.`", # Use backticks for code font
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return ConversationHandler.END

# --- Main Bot Execution ---
async def run_bot():
    global application
    logger.info("Booting Z1-Gray System Core...")

    # ✅ Item 6 (from review): Strict BOT_TOKEN Check
    if not BOT_TOKEN or BOT_TOKEN == "CRITICAL_FAILURE_TOKEN_MISSING": # More specific check
        logger.critical("FATAL: Invalid or missing BOT_TOKEN configuration. Halting execution.")
        raise RuntimeError("Invalid BOT_TOKEN configuration. Cannot start bot.")

    setup_secure_webhook_path() # Determine secure path if using webhook

    # --- Application Builder ---
    # ✅ Item 4 (from review): Persistence setup (uncomment to enable)
    persistence = None
    # persistence_path = os.getenv("PERSISTENCE_PATH", "z1_gray_persistence.pkl")
    # try:
    #     persistence = PicklePersistence(filepath=persistence_path)
    #     logger.info(f"PicklePersistence enabled: {persistence_path}")
    # except Exception as e:
    #     logger.error(f"Failed to initialize PicklePersistence: {e}. Persistence disabled.")

    application_builder = (
        ApplicationBuilder().token(BOT_TOKEN)
        .post_init(post_initialization_hook)
        .drop_pending_updates(True) # Good for production to avoid processing old updates on restart
        # .persistence(persistence) # Enable if configured
        # .concurrent_updates(True) # Optional performance tuning
    )
    application = application_builder.build()

    # --- Conversation Handler ---
    # ✅ Item 2 (from review): States MUST map to actual, imported handlers
    # Replace placeholders like 'awaiting_step_two_ack_handler' with real imports
    # from handlers.step_2 import handle_step_2_ack_text, handle_step_2_ack_button etc.
    # ✅ Item 5 (from review): routes.py suggestion noted in comment.
    # ConversationHandler definition - replace placeholders with actual handlers
    z1_gray_conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", step_one_entry)], # step_one_entry MUST clear user_data
        states={
            # Example: Assuming step_one_entry returns AWAITING_STEP_TWO_ACK
            # The job it schedules runs Step 2 messages and prompts the user.
            AWAITING_STEP_TWO_ACK: [
                # ✅ Item 3 (from review): Specific filters first
                MessageHandler(filters.Regex(r'^(OK|Ok|ok|YES|Yes|yes)$'), awaiting_step_two_ack_handler), # REPLACE placeholder
                CallbackQueryHandler(awaiting_step_two_ack_handler, pattern="^review_diagnostics_pressed$"), # REPLACE placeholder
                # Fallback *within this state* for other text
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message) # Use the placeholder defined above
            ],
            # Define ALL other states from state_definitions.py here
            # Map them to their specific handlers imported from handlers/*.py
            # AWAITING_STEP_THREE_ACK: [ ... handlers ... ],
            # AWAITING_STEP_FIVE_CHOICE: [ ... handlers ... ],
            # STEP_5_AWAITING_FINAL_ACTION: [ ... handlers ... ],
            # STEP_5_FINAL_CHANCE_STATE: [ ... handlers ... ],
            # STEP_5_REJECTION_WARNING_STATE: [ ... handlers ... ], # If using this state
        },
        fallbacks=[ # Global fallbacks if no state handler matches
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.COMMAND, handle_unknown_command), # Use the placeholder defined above
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message), # Use the placeholder defined above
            CallbackQueryHandler(handle_unknown_callback) # Use the placeholder defined above
        ],
        per_user=True,
        name="z1_gray_funnel_production_v4", # Increment version name
        allow_reentry=True, # ✅ step_one_entry MUST handle data clearing
        # persistent=True, # Enable if using persistence object
        # map_to_state= # Optional advanced state mapping
    )
    application.add_handler(z1_gray_conversation_handler)

    # --- Start Bot ---
    if USE_WEBHOOK and WEBHOOK_URL and FINAL_WEBHOOK_PATH and BOT_TOKEN and not BOT_TOKEN == "CRITICAL_FAILURE_TOKEN_MISSING":
        await application.initialize()
        await application.start()
        logger.info(f"PTB core started for WEBHOOK. Ensure external server handles {FINAL_WEBHOOK_PATH} on port {PORT}.")
        await shutdown_event.wait()
    else:
        logger.info("Starting bot in POLLING mode...")
        allowed_updates = [Update.MESSAGE, Update.CALLBACK_QUERY] # Example: be specific
        await application.run_polling(allowed_updates=allowed_updates, stop_signals=[]) # Pass empty list to handle signals manually

    # --- Graceful Shutdown ---
    logger.info("Initiating final application shutdown...")
    if hasattr(application, 'running') and application.running: await application.stop()
    await application.shutdown()
    logger.info("Application shut down successfully.")

# --- Script Entry Point ---
if __name__ == "__main__":
    signal.signal(signal.SIGINT, graceful_signal_handler)
    signal.signal(signal.SIGTERM, graceful_signal_handler)
    logger.info("Z1-Gray Main Application Bootstrapping Sequence Initiated...")
    try:
        asyncio.run(run_bot())
    except RuntimeError as e:
        if "Invalid BOT_TOKEN" in str(e): # Check if it's our specific token error
            pass # Already logged critically in run_bot()
        else:
            logger.critical(f"Runtime Error: {e}. Execution halted.", exc_info=True)
    except (KeyboardInterrupt, SystemExit) as e: logger.info(f"Process terminated by signal ({type(e).__name__}).")
    except Exception as e: logger.critical(f"FATAL UNHANDLED EXCEPTION at top level: {e}", exc_info=True)
    finally: logger.info("Z1-Gray Main Application execution cycle concluded.")