# main.py

import logging
import asyncio
import signal
import os
import secrets # For secure webhook path
from urllib.parse import urlparse
# from datetime import timedelta # Not used
import logging.handlers
import time

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    Application, # Keep this for type hinting if using v20 structure elsewhere
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    PicklePersistence,
    # If using updater explicitly, Updater might be needed from here for older versions
    # For v20, Application is the main object.
)

# --- Attempt to import configurations and handlers ---
try:
    from config.settings import (
        BOT_TOKEN, WEBHOOK_URL, PORT, # PORT is used directly in the new webhook logic
        WEBHOOK_PATH as CFG_WEBHOOK_PATH,
        ADMIN_CHAT_ID, DEVELOPMENT_MODE, USE_WEBHOOK,
        LOG_FILE_PATH
    )
except ImportError:
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.CRITICAL)
    logging.critical("CRITICAL: Failed to import required variables from config.settings.py.")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "CRITICAL_FAILURE_TOKEN_MISSING")
    WEBHOOK_URL = None; PORT = 8080; CFG_WEBHOOK_PATH = None; ADMIN_CHAT_ID = None; LOG_FILE_PATH = None
    DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "False").lower() in ("true", "1", "yes")
    USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"


# --- Configure Logging ---
log_level = logging.DEBUG if DEVELOPMENT_MODE else logging.INFO
log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"

logging.basicConfig(
    format=log_format,
    level=log_level,
    handlers=[logging.StreamHandler()]
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.INFO if not DEVELOPMENT_MODE else logging.DEBUG)
logger = logging.getLogger(__name__)

if LOG_FILE_PATH:
    try:
        file_formatter = logging.Formatter(log_format)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE_PATH, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setFormatter(file_formatter)
        logging.getLogger().addHandler(file_handler)
        logger.info(f"File logging enabled. Outputting to: {LOG_FILE_PATH}")
    except Exception as e:
        logger.error(f"Failed to configure file logging to {LOG_FILE_PATH}: {e}", exc_info=True)
else:
    logger.info("File logging disabled (LOG_FILE_PATH not set in config/settings.py).")

# --- Import State Definitions ---
try:
    from utils.state_definitions import *
    if 'STATE_NAME_MAP' not in globals() or not isinstance(STATE_NAME_MAP, dict) or \
       'STEP_2_AWAITING_REVIEW_CHOICE_STATE' not in globals():
        raise ImportError("Essential state definitions missing after import from utils.state_definitions.")
    logger.info("Successfully imported state definitions from utils.state_definitions.")
except ImportError as e:
    logger.critical(f"CRITICAL: Failed to import or validate state definitions from utils.state_definitions.py: {e}. THIS IS FATAL.")
    STEP_2_AWAITING_REVIEW_CHOICE_STATE, STEP_4_AWAITING_USER_DECISION_STATE = 0, 1
    STEP_5_CTA_TEXT_INPUT_STATE, STEP_5_FINAL_CHANCE_STATE = 2, 3
    AWAITING_STEP_TWO_ACK = STEP_2_AWAITING_REVIEW_CHOICE_STATE # Alias from your state_definitions
    AWAITING_STEP_FIVE_CHOICE = STEP_5_CTA_TEXT_INPUT_STATE     # Alias
    STEP_5_AWAITING_FINAL_ACTION = STEP_5_FINAL_CHANCE_STATE  # Alias
    STATE_NAME_MAP = {
        STEP_2_AWAITING_REVIEW_CHOICE_STATE: "FALLBACK_S2_REVIEW_CHOICE",
        STEP_4_AWAITING_USER_DECISION_STATE: "FALLBACK_S4_USER_DECISION",
        STEP_5_CTA_TEXT_INPUT_STATE: "FALLBACK_S5_CTA_INPUT",
        STEP_5_FINAL_CHANCE_STATE: "FALLBACK_S5_FINAL_CHANCE",
    }
    logger.warning("Fallback state definitions are active. ConversationHandler may be broken.")

# --- Import Handlers (Robust Placeholders) ---
try:
    from handlers.step_1 import step_one_entry
except ImportError:
    logger.warning("Using placeholder for step_1_entry.")
    async def step_one_entry(u: Update, c: ContextTypes.DEFAULT_TYPE):
        await u.message.reply_text("[SYS_ERR] H1 Missing.")
        return ConversationHandler.END

async def awaiting_step_two_ack_handler(u: Update,c: ContextTypes.DEFAULT_TYPE): logger.info("Placeholder: Awaiting Step 2 Ack handler"); return
async def awaiting_step_three_ack_handler(u: Update,c: ContextTypes.DEFAULT_TYPE): logger.info("Placeholder: Awaiting Step 3 Ack handler"); return
async def awaiting_step_five_choice_callback_handler(u: Update,c: ContextTypes.DEFAULT_TYPE): logger.info("Placeholder: Awaiting Step 5 Choice CB handler"); await u.callback_query.answer(); return
async def awaiting_step_five_choice_text_handler(u: Update,c: ContextTypes.DEFAULT_TYPE): logger.info("Placeholder: Awaiting Step 5 Choice text handler"); return
async def step_five_cta_text_handler(u: Update,c: ContextTypes.DEFAULT_TYPE): logger.info("Placeholder: Step 5 CTA text handler"); return
async def step_five_final_chance_handler(u: Update,c: ContextTypes.DEFAULT_TYPE): logger.info("Placeholder: Step 5 Final Chance handler"); return

try:
    from handlers.unknown import handle_unknown_message, handle_unknown_command, handle_unknown_callback
except ImportError:
    logger.warning("Using placeholders for unknown handlers.")
    async def handle_unknown_message(u: Update, c: ContextTypes.DEFAULT_TYPE): await u.message.reply_text("[SYS] Unknown input (text)."); return
    async def handle_unknown_command(u: Update, c: ContextTypes.DEFAULT_TYPE): await u.message.reply_text("[SYS] Unknown input (command)."); return
    async def handle_unknown_callback(u: Update, c: ContextTypes.DEFAULT_TYPE):
        if u.callback_query: await u.callback_query.answer("Unknown callback action.", show_alert=False)
        if u.effective_message: await u.effective_message.reply_text("[SYS] Unknown input (callback).")
        return

# --- Global Variables ---
shutdown_event = asyncio.Event()
application: Application | None = None # For PTB v20, this is correct. For v13, you'd use Updater.
FINAL_WEBHOOK_PATH = None

# --- Secure Webhook Path Generation ---
def setup_secure_webhook_path() -> None:
    global FINAL_WEBHOOK_PATH
    if not USE_WEBHOOK or not WEBHOOK_URL:
        FINAL_WEBHOOK_PATH = "webhook_path_not_set_or_needed" # Default placeholder
        logger.info("Webhook path generation skipped (not in webhook mode or WEBHOOK_URL not set).")
        return

    # Use user-configured path if valid, otherwise generate one
    if CFG_WEBHOOK_PATH and CFG_WEBHOOK_PATH.startswith("/") and len(CFG_WEBHOOK_PATH) > 1:
        FINAL_WEBHOOK_PATH = CFG_WEBHOOK_PATH
        logger.info(f"Using user-configured WEBHOOK_PATH from settings: {FINAL_WEBHOOK_PATH}")
    else:
        secure_suffix = secrets.token_urlsafe(16)
        FINAL_WEBHOOK_PATH = f"/tgwh_{secure_suffix}"
        logger.info(f"User-configured WEBHOOK_PATH invalid or not set. Using secure, auto-generated WEBHOOK_PATH: {FINAL_WEBHOOK_PATH}")

# --- Signal Handler ---
async def graceful_signal_handler_async(sig): # Renamed for clarity, now async
    logger.info(f"Signal {sig} received by async handler. Initiating graceful shutdown...")
    if application and hasattr(application, '_is_running') and application._is_running: # PTB v20 internal
        logger.info("Attempting to stop PTB application...")
        await application.stop()
        logger.info("PTB application stop initiated.")
    elif application and hasattr(application, 'updater') and application.updater and \
         hasattr(application.updater, 'running') and application.updater.running: # For v13-like structure
        logger.info("Attempting to stop PTB updater...")
        application.updater.stop() # This is synchronous in v13
        logger.info("PTB updater stop initiated.")
    shutdown_event.set()

# --- Post Initialization Hook ---
# This hook is part of PTB v20's ApplicationBuilder.
# If using v13 structure, this logic would be called manually after creating Updater.
async def post_initialization_hook(app: Application) -> None:
    global FINAL_WEBHOOK_PATH
    webhook_setup_successful = False
    allowed_updates = [Update.MESSAGE, Update.CALLBACK_QUERY]
    full_webhook_url_display = "N/A (Polling or Setup Failed)"

    if USE_WEBHOOK and WEBHOOK_URL and FINAL_WEBHOOK_PATH and BOT_TOKEN and not BOT_TOKEN.startswith("CRITICAL_FAILURE_TOKEN_MISSING"):
        if FINAL_WEBHOOK_PATH == "webhook_path_not_set_or_needed":
            logger.critical("CRITICAL: FINAL_WEBHOOK_PATH was not properly set. Webhook setup cannot proceed with Telegram.")
            return

        parsed_url = urlparse(WEBHOOK_URL)
        if not parsed_url.scheme == "https" or not parsed_url.netloc:
            logger.critical(f"Webhook URL '{WEBHOOK_URL}' invalid. Webhook NOT set with Telegram.")
        else:
            full_webhook_url_to_set = f"{WEBHOOK_URL.rstrip('/')}{FINAL_WEBHOOK_PATH}"
            full_webhook_url_display = full_webhook_url_to_set

            logger.info(f"Attempting to set webhook with Telegram: {full_webhook_url_to_set}")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # This uses app.bot which is correct for PTB v20 Application object
                    await app.bot.set_webhook(
                        url=full_webhook_url_to_set,
                        allowed_updates=allowed_updates,
                        drop_pending_updates=True
                    )
                    webhook_info = await app.bot.get_webhook_info()
                    if webhook_info.url == full_webhook_url_to_set:
                        logger.info(f"Webhook set successfully with Telegram on attempt {attempt + 1}: {webhook_info.url}")
                        webhook_setup_successful = True
                        break
                    else:
                        logger.warning(f"Telegram's reported Webhook URL differs. Expected: {full_webhook_url_to_set}, Got: {webhook_info.url}")
                        if urlparse(webhook_info.url).path == FINAL_WEBHOOK_PATH:
                             logger.info(f"Webhook path {FINAL_WEBHOOK_PATH} matches Telegram's reported URL. Considering successful.")
                             webhook_setup_successful = True
                             break
                except Exception as e:
                    logger.error(f"Error setting webhook with Telegram on attempt {attempt + 1}: {e}", exc_info=(attempt == max_retries - 1))
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying Telegram webhook setup in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
            if not webhook_setup_successful:
                 logger.critical("CRITICAL: Failed to set webhook with Telegram after multiple retries.")
                 full_webhook_url_display = "N/A (Telegram Webhook Setup FAILED!)"
    else:
        logger.info("Skipping Telegram webhook setup (Not in USE_WEBHOOK mode or missing critical configs).")

    # JobQueue and Admin notification logic remains the same
    if app.job_queue: logger.info(f"JobQueue initialized. Jobs: {len(app.job_queue.jobs())}")
    else: logger.warning("JobQueue not available.")

    if ADMIN_CHAT_ID:
        mode_display = "Webhook (TG Ok)" if webhook_setup_successful else \
                       ("Webhook (TG Fail)" if USE_WEBHOOK else "Polling")
        try:
            bot_info = await app.bot.get_me()
            from telegram.helpers import escape_markdown
            safe_bot_username = escape_markdown(bot_info.username if bot_info.username else "N/A_BOT_USERNAME", version=2)
            safe_webhook_url_display = escape_markdown(full_webhook_url_display, version=2)
            startup_message = (f"✅ *Z1\\-Gray Bot Online*\n"
                               f"*Mode:* `{mode_display}`\n"
                               f"*Node:* `@{safe_bot_username}`\n"
                               f"*TS:* `{time.strftime('%Y-%m-%d %H:%M:%S %Z')}`")
            if USE_WEBHOOK:
                startup_message += f"\n*App Listening Path:* `{escape_markdown(FINAL_WEBHOOK_PATH, version=2)}`"
                startup_message += f"\n*Telegram Endpoint:* `{safe_webhook_url_display}`"
            await app.bot.send_message(chat_id=ADMIN_CHAT_ID, text=startup_message, parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f"Startup notification sent to ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
        except Exception as e: logger.error(f"Failed to send startup notification: {e}", exc_info=True)


# --- Conversation Fallback Handler ---
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id_log = user.id if user else "N/A"
    current_state_val = context.user_data.get(ConversationHandler.STATE) if context.user_data else None
    state_name = STATE_NAME_MAP.get(current_state_val, f"UNKNOWN_S({current_state_val})") if current_state_val is not None else "N/A"
    logger.info(f"[CONV_CANCEL] User {user_id_log} (State: {state_name}) initiated /cancel.")
    if context.user_data: context.user_data.clear()
    await update.message.reply_text(
        "`[PROTOCOL_SESSION_TERMINATED]`\n`User directive acknowledged. System reset.`\n`/start` `to re-initiate protocol.`",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return ConversationHandler.END

# --- Main Bot Execution ---
async def run_bot():
    global application
    logger.info("Booting Z1-Gray System Core...")

    if not BOT_TOKEN or BOT_TOKEN == "CRITICAL_FAILURE_TOKEN_MISSING":
        logger.critical("FATAL: Invalid or missing BOT_TOKEN configuration.")
        raise RuntimeError("Invalid BOT_TOKEN. Cannot start bot.")

    setup_secure_webhook_path() # Sets FINAL_WEBHOOK_PATH

    persistence = None
    # ... persistence setup if needed ...

    # PTB v20 ApplicationBuilder pattern
    application_builder = (
        ApplicationBuilder().token(BOT_TOKEN)
        .post_init(post_initialization_hook) # post_init IS a v20 feature
        # .persistence(persistence)
    )
    application = application_builder.build() # This creates the Application object for v20

    # ConversationHandler definition
    z1_gray_conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", step_one_entry)],
        states={
            STEP_2_AWAITING_REVIEW_CHOICE_STATE: [
                MessageHandler(filters.Regex(r'^(OK|Ok|ok|YES|Yes|yes)$'), awaiting_step_two_ack_handler),
                CallbackQueryHandler(awaiting_step_two_ack_handler, pattern="^review_diagnostics_pressed$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message)
            ],
            # ... other states
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.COMMAND, handle_unknown_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message),
            CallbackQueryHandler(handle_unknown_callback)
        ],
        per_user=True,
        name="z1_gray_funnel_production_v5",
        allow_reentry=True,
    )
    application.add_handler(z1_gray_conversation_handler)

    # --- Start Bot ---
    if USE_WEBHOOK and WEBHOOK_URL and FINAL_WEBHOOK_PATH and BOT_TOKEN and not BOT_TOKEN == "CRITICAL_FAILURE_TOKEN_MISSING":
        if FINAL_WEBHOOK_PATH == "webhook_path_not_set_or_needed":
             logger.critical("CRITICAL: Webhook path not set, cannot start in webhook mode.")
             return

        # Fixed webhook startup section - using PTB v20 style
        try:
            logger.info(f"Starting webhook server, listening at 0.0.0.0:{PORT}, path: {FINAL_WEBHOOK_PATH}")
            
            # Key fix here - using the correct async approach with v20 Application
            await application.initialize()  # Initialize app (will call post_init hook)
            await application.start()  # Start the application (necessary preparation)
            
            # Proper webhook setup
            await application.bot.set_webhook(
                url=f"{WEBHOOK_URL.rstrip('/')}{FINAL_WEBHOOK_PATH}",
                allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY],
                drop_pending_updates=True
            )
            
            # Use WebhookServer for v20
            from telegram.ext._utils.webhookhandler import WebhookServer
            webhook_server = WebhookServer(
                listen="0.0.0.0",
                port=PORT, 
                url_path=FINAL_WEBHOOK_PATH,
                webhook_app=application.webhook_app
            )
            
            # Start the web server
            await webhook_server.serve_forever()
            
            logger.info(f"Webhook server successfully started, listening at 0.0.0.0:{PORT} on path {FINAL_WEBHOOK_PATH}")
            await shutdown_event.wait()  # Wait for shutdown signal
            
        except Exception as e:
            logger.critical(f"Failed to start webhook server: {e}", exc_info=True)
            return

    else: # Polling mode
        logger.info("Starting bot in POLLING mode...")
        allowed_updates = [Update.MESSAGE, Update.CALLBACK_QUERY]
        await application.run_polling(
            allowed_updates=allowed_updates,
            drop_pending_updates=True,
            stop_signals=[signal.SIGINT, signal.SIGTERM]
        )

    logger.info("Bot's main run function has exited.")


# --- Script Entry Point ---
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(graceful_signal_handler_async(s)))

    logger.info("Z1-Gray Main Application Bootstrapping Sequence Initiated...")
    try:
        asyncio.run(run_bot())
    except RuntimeError as e:
        if "Cannot close a running event loop" in str(e) or "Event loop is closed" in str(e):
            logger.warning(f"Known RuntimeError during shutdown: {e}")
        elif "Invalid BOT_TOKEN" in str(e): pass
        else: logger.critical(f"Runtime Error: {e}. Execution halted.", exc_info=True)
    except NameError as e:
        logger.critical(f"FATAL NameError: {e}. Check imports and definitions.", exc_info=True)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Process terminated by KeyboardInterrupt/SystemExit.")
    except Exception as e:
        logger.critical(f"FATAL UNHANDLED EXCEPTION at top level: {e}", exc_info=True)
    finally:
        logger.info("Z1-Gray Main Application execution cycle concluded.")