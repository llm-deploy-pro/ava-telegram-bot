#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main.py (Z1-Gray Version with aiohttp integration - Deduplicated & Corrected)

import logging
import asyncio
import os
import signal
import sys
import secrets
from urllib.parse import urlparse
from datetime import timedelta # Not used, but kept from original if intended for future
import logging.handlers
import time

from telegram import Update, ReplyKeyboardRemove # ReplyKeyboardRemove might be needed in cancel
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    PicklePersistence,
)
from telegram.error import InvalidToken, BadRequest
from telegram.constants import ParseMode
from dotenv import load_dotenv
from aiohttp import web # For manual webhook server

# --- Configure Logging ---
# Setup logging ONCE, early.
log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
logging.basicConfig(format=log_format, level=logging.INFO, force=True) # Force ensures reconfiguration if called before
logger = logging.getLogger(__name__) # Logger for this main module

# --- Load Environment Variables ---
load_dotenv()

# --- Import Configurations from settings.py ---
try:
    from config.settings import (
        BOT_TOKEN, WEBHOOK_URL, PORT,
        WEBHOOK_PATH as CFG_WEBHOOK_PATH,
        ADMIN_CHAT_ID, DEVELOPMENT_MODE, USE_WEBHOOK,
        LOG_FILE_PATH, PERSISTENCE_PATH
    )
    # Apply Development Mode log level adjustment AFTER initial basicConfig
    log_level = logging.DEBUG if DEVELOPMENT_MODE else logging.INFO
    logging.getLogger().setLevel(log_level)
    for handler in logging.getLogger().handlers: handler.setLevel(log_level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.INFO if not DEVELOPMENT_MODE else logging.DEBUG)
    logger.info(f"Logging level set to: {logging.getLevelName(log_level)} (DEVELOPMENT_MODE={DEVELOPMENT_MODE})")

    # Setup File Logging if configured
    if LOG_FILE_PATH:
        try:
            log_dir = os.path.dirname(LOG_FILE_PATH)
            if log_dir and not os.path.exists(log_dir): os.makedirs(log_dir, exist_ok=True)
            file_formatter = logging.Formatter(log_format)
            file_handler = logging.handlers.RotatingFileHandler(
                LOG_FILE_PATH, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
            )
            file_handler.setFormatter(file_formatter)
            logging.getLogger().addHandler(file_handler)
            logger.info(f"File logging enabled: {LOG_FILE_PATH}")
        except Exception as e: logger.error(f"Failed to configure file logging: {e}", exc_info=True)
    else: logger.info("File logging disabled.")

except ImportError:
    logger.critical("CRITICAL: Failed to import from config.settings.py. Using critical fallbacks.")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "CRITICAL_FAILURE_TOKEN_MISSING")
    WEBHOOK_URL = None; PORT = 8080; CFG_WEBHOOK_PATH = None; ADMIN_CHAT_ID = None; LOG_FILE_PATH = None; PERSISTENCE_PATH = None
    DEVELOPMENT_MODE = False; USE_WEBHOOK = False

# --- Startup Checks ---
if not BOT_TOKEN or BOT_TOKEN == "CRITICAL_FAILURE_TOKEN_MISSING":
    logger.critical("FATAL: BOT_TOKEN is missing or invalid. Halting execution.")
    sys.exit("Invalid BOT_TOKEN configuration.") # Use sys.exit for clarity in fatal errors

if USE_WEBHOOK and not WEBHOOK_URL:
    logger.critical("FATAL: USE_WEBHOOK is true, but WEBHOOK_URL is missing. Halting.")
    sys.exit("Webhook mode enabled, but WEBHOOK_URL is missing.")

# --- Import States & State Map (Critical for ConversationHandler) ---
try:
    from utils.state_definitions import * # Import all states
    if 'STATE_NAME_MAP' not in globals() or not isinstance(STATE_NAME_MAP, dict): raise ImportError("STATE_NAME_MAP missing")
    logger.info(f"Loaded {len(STATE_NAME_MAP)} states from state_definitions.")
except ImportError:
    logger.critical("CRITICAL: utils/state_definitions.py/STATE_NAME_MAP missing. Using fallbacks.")
    AWAITING_STEP_TWO_ACK, AWAITING_STEP_THREE_ACK, AWAITING_STEP_FIVE_CHOICE = 0,1,2 # type: ignore
    STEP_5_AWAITING_FINAL_ACTION, STEP_5_FINAL_CHANCE_STATE, STEP_5_REJECTION_WARNING_STATE = 3,4,5 # type: ignore
    STATE_NAME_MAP = {i: f"FALLBACK_STATE_{i}" for i in range(6)} # type: ignore

# --- Import Handlers (Use placeholders only if actual files/functions are missing) ---
# These MUST point to the actual implemented functions for the bot to work.
try: from handlers.step_1 import step_one_entry
except ImportError: logger.error("CRITICAL: H1 Missing."); async def step_one_entry(u,c): await u.message.reply_text("[ERR] H1 Init Failed."); return ConversationHandler.END # type: ignore
try: from handlers.step_2 import handle_step_2_ack # Assuming this handles both text and button
except ImportError: logger.warning("Using placeholder for handle_step_2_ack."); async def handle_step_2_ack(u,c): logger.info("PH: S2 Ack"); return AWAITING_STEP_THREE_ACK # type: ignore
try: from handlers.step_4 import handle_step_4_choice_initiate, handle_step_4_choice_query # Specific handlers for buttons
except ImportError: logger.warning("Using placeholders for handle_step_4_choice."); async def handle_step_4_choice_initiate(u,c): logger.info("PH: S4 Init Sync"); await u.callback_query.answer(); return STEP_5_AWAITING_FINAL_ACTION # type: ignore; async def handle_step_4_choice_query(u,c): logger.info("PH: S4 Query"); await u.callback_query.answer(); return STEP_5_AWAITING_FINAL_ACTION # type: ignore
try: from handlers.step_5 import handle_final_sync_button, handle_step5_text_input, handle_final_chance_callback, handle_rejection_warning_callback # Specific handlers for Step 5
except ImportError: logger.warning("Using placeholders for step_5 handlers."); async def handle_final_sync_button(u,c): logger.info("PH: S5 Final Sync"); await u.callback_query.answer(); return ConversationHandler.END # type: ignore ; async def handle_step5_text_input(u,c): logger.info("PH: S5 Text"); return STEP_5_AWAITING_FINAL_ACTION # type: ignore ; async def handle_final_chance_callback(u,c): logger.info("PH: S5 Final Chance CB"); await u.callback_query.answer(); return ConversationHandler.END # type: ignore ; async def handle_rejection_warning_callback(u,c): logger.info("PH: S5 Reject Warn CB"); await u.callback_query.answer(); return STEP_5_FINAL_CHANCE_STATE # type: ignore
try: from handlers.unknown import handle_unknown_message, handle_unknown_command, handle_unknown_callback
except ImportError: logger.warning("Using placeholders for unknown handlers."); async def handle_unknown_message(u,c):pass # type: ignore ; async def handle_unknown_command(u,c):pass # type: ignore ; async def handle_unknown_callback(u,c): await u.callback_query.answer() # type: ignore

# --- Global Variables ---
shutdown_event = asyncio.Event()
application: Application | None = None
FINAL_WEBHOOK_PATH: str | None = None # Type hint for clarity

# --- Secure Webhook Path Generation ---
def setup_secure_webhook_path() -> None:
    """Determines the final, secure webhook path for deployment. Modifies global FINAL_WEBHOOK_PATH."""
    global FINAL_WEBHOOK_PATH
    if not USE_WEBHOOK or not WEBHOOK_URL: # Only proceed if webhook mode is active and URL is set
        FINAL_WEBHOOK_PATH = None
        logger.info("Webhook mode not active or WEBHOOK_URL not set. Skipping secure path generation.")
        return

    configured_path = CFG_WEBHOOK_PATH
    # Example secure prefix, can be customized further if needed.
    # Ensure it starts with a slash and doesn't contain problematic characters.
    # A simple prefix like "/wh/" followed by a token is often sufficient.
    secure_prefix_indicator = "tgwh_auto_" # Used to identify auto-generated paths

    if configured_path and isinstance(configured_path, str) and configured_path.startswith("/") and len(configured_path) > 1:
        # Potentially validate configured_path further (e.g., no '..' or problematic chars)
        FINAL_WEBHOOK_PATH = configured_path
        logger.info(f"Using user-configured WEBHOOK_PATH: {FINAL_WEBHOOK_PATH}")
    else:
        if configured_path:
            logger.warning(f"Configured WEBHOOK_PATH ('{configured_path}') is invalid or empty. Generating a secure path.")
        else:
            logger.info("WEBHOOK_PATH not configured or empty. Generating a secure path.")
        secure_suffix = secrets.token_urlsafe(24) # Increased length for more security
        FINAL_WEBHOOK_PATH = f"/{secure_prefix_indicator}{secure_suffix}"
        logger.info(f"Using auto-generated secure WEBHOOK_PATH: {FINAL_WEBHOOK_PATH}")

# --- Signal Handler ---
def graceful_signal_handler(sig, frame):
    """Handles OS signals for graceful shutdown."""
    logger.info(f"Signal {sig} received. Setting shutdown event...")
    # Ensure loop is running before calling call_soon_threadsafe
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(shutdown_event.set)
        else: # If loop isn't running (e.g. during initial setup before run_bot), just set
            shutdown_event.set()
    except RuntimeError: # get_running_loop might raise RuntimeError if no loop is set
        logger.warning("No running event loop found for signal handler, setting event directly.")
        shutdown_event.set()


# --- Post Initialization Hook (Webhook Setup) ---
async def post_initialization_hook(app: Application) -> None:
    """Sets the webhook after PTB application initialization."""
    webhook_setup_successful = False
    full_webhook_url_for_notification = "N/A" # For admin notification

    if USE_WEBHOOK and WEBHOOK_URL and FINAL_WEBHOOK_PATH and BOT_TOKEN and not BOT_TOKEN.startswith("CRITICAL_FAILURE_TOKEN_MISSING"):
        parsed_url = urlparse(WEBHOOK_URL)
        if not parsed_url.scheme or not parsed_url.netloc: # Basic check for scheme and domain
            logger.critical(f"Invalid WEBHOOK_URL '{WEBHOOK_URL}'. Webhook NOT set.")
        else:
            # Ensure WEBHOOK_URL doesn't have a path component that conflicts
            base_webhook_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            full_webhook_url = f"{base_webhook_url}{FINAL_WEBHOOK_PATH}"
            full_webhook_url_for_notification = full_webhook_url # Store for notification
            logger.info(f"Attempting to set webhook (retries=3): {full_webhook_url}")
            max_retries = 3
            allowed_updates = [Update.MESSAGE, Update.CALLBACK_QUERY] # Be specific

            for attempt in range(max_retries):
                try:
                    # Secret token for webhook can be set here for added security if desired
                    # webhook_secret_token = secrets.token_urlsafe(32) # Example
                    await app.bot.set_webhook(
                        url=full_webhook_url,
                        allowed_updates=allowed_updates,
                        drop_pending_updates=True,
                        # secret_token=webhook_secret_token # Uncomment if using
                    )
                    webhook_info = await app.bot.get_webhook_info()
                    if webhook_info and webhook_info.url == full_webhook_url:
                        logger.info(f"Webhook set successfully (Attempt {attempt + 1}): {webhook_info.url}")
                        # if webhook_secret_token: logger.info("Webhook secret token also set.")
                        webhook_setup_successful = True
                        break
                    else:
                        logger.warning(f"Webhook set attempt {attempt + 1} failed. URL mismatch or No Info. Expected: {full_webhook_url}, Got: {webhook_info.url if webhook_info else 'None'}")
                except InvalidToken:
                    logger.critical("Invalid Bot Token. Cannot set webhook.")
                    break # No point retrying if token is bad
                except BadRequest as e:
                    logger.error(f"BadRequest setting webhook attempt {attempt + 1}: {e}. This might be a configuration issue (e.g., URL, SSL).", exc_info=(attempt == max_retries - 1))
                    if "url host is empty" in str(e).lower() or "wrong url" in str(e).lower():
                         logger.critical(f"The webhook URL '{full_webhook_url}' is likely malformed or inaccessible by Telegram.")
                         break # No point retrying if URL is fundamentally bad
                except Exception as e:
                    logger.error(f"Generic error setting webhook attempt {attempt + 1}: {e}", exc_info=(attempt == max_retries - 1))

                if attempt < max_retries - 1:
                    delay = 2**(attempt + 1) # Exponential backoff
                    logger.info(f"Retrying webhook setup in {delay} seconds...")
                    await asyncio.sleep(delay)

            if not webhook_setup_successful:
                logger.critical("Webhook setup FAILED after all retries.")
    elif USE_WEBHOOK:
        logger.warning("Skipping webhook setup due to missing WEBHOOK_URL, FINAL_WEBHOOK_PATH, or valid BOT_TOKEN.")
    else:
        logger.info("Polling mode configured. Skipping webhook setup.")

    if app.job_queue: logger.info(f"JobQueue available. Initial jobs: {len(app.job_queue.jobs())}")
    else: logger.warning("JobQueue not available (e.g. if persistence is not setup or app build issue).")

    if ADMIN_CHAT_ID:
        mode = "Webhook (Active)" if webhook_setup_successful else ("Webhook (Setup FAILED!)" if USE_WEBHOOK else "Polling")
        try:
            bot_info = await app.bot.get_me()
            from telegram.helpers import escape_markdown
            safe_bot_username = escape_markdown(bot_info.username or "UnknownBot", version=2)
            safe_webhook_url_display = escape_markdown(full_webhook_url_for_notification, version=2) if webhook_setup_successful else "N/A"

            startup_message = (
                f"✅ *Z1\\-Gray Bot Online*\n"
                f"*Mode:* `{mode}`\n"
                f"*Node:* `@{safe_bot_username}`\n"
                f"*TS:* `{time.strftime('%Y-%m-%d %H:%M:%S %Z')}`"
            )
            if USE_WEBHOOK: # Only show webhook URL line if webhook mode was intended
                 startup_message += f"\n*Webhook URL:* `{safe_webhook_url_display}`"

            await app.bot.send_message(chat_id=ADMIN_CHAT_ID, text=startup_message, parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f"Startup notification sent to ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
        except Exception as e: logger.error(f"Failed to send startup notification to ADMIN_CHAT_ID {ADMIN_CHAT_ID}: {e}", exc_info=True)

# === Conversation Fallback Handler for /cancel ===
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the /cancel command within the conversation."""
    user = update.effective_user
    user_id_log = user.id if user else "N/A"
    current_state_val = context.user_data.get(ConversationHandler.STATE) if context.user_data else None
    state_name = STATE_NAME_MAP.get(current_state_val, f"UNKNOWN({current_state_val})") if current_state_val is not None else "N/A"

    logger.info(f"[CONV_CANCEL] User {user_id_log} (State: {state_name}) executed /cancel.")
    if context.user_data: context.user_data.clear()

    # Check if message exists before replying (e.g., if called from a CallbackQuery context without a message)
    if update.message:
        await update.message.reply_text(
            "`[PROTOCOL_SESSION_TERMINATED]`\n`Session reset. Send /start to re-initiate.`",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=ReplyKeyboardRemove() # Good practice to remove any custom keyboards
        )
    elif update.callback_query:
        await update.callback_query.answer("Conversation cancelled.")
        # Optionally send a new message if appropriate in callback context
        if update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="`[PROTOCOL_SESSION_TERMINATED]`\n`Session reset. Send /start to re-initiate.`",
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=ReplyKeyboardRemove()
                )
            except Exception as e:
                logger.error(f"Error sending cancel confirmation in callback context: {e}")

    return ConversationHandler.END

# === Webhook Handler (for aiohttp integration) ===
async def telegram_webhook_handler(request: web.Request) -> web.Response:
    """Handles incoming webhook requests from Telegram via aiohttp."""
    global application
    if not application:
        logger.error("Webhook received but PTB Application not initialized.")
        return web.Response(status=503, text="Bot Service Unavailable")
    if not application.bot:
        logger.error("Webhook received but PTB Application.bot not initialized.")
        return web.Response(status=503, text="Bot Service (Bot instance) Unavailable")

    try:
        update_data = await request.json()
        # logger.debug(f"Received webhook data: {update_data}") # Uncomment for verbose debugging
    except Exception as e:
        logger.error(f"Failed to parse JSON from webhook request: {e}", exc_info=True)
        return web.Response(status=400, text="Bad Request: Invalid JSON")

    try:
        update = Update.de_json(update_data, application.bot)
        # Using asyncio.create_task for non-blocking update processing by PTB
        asyncio.create_task(application.process_update(update))
        return web.Response(status=200, text="OK") # Acknowledge Telegram immediately
    except Exception as e:
        update_id_str = update_data.get('update_id', 'N/A')
        logger.error(f"Error processing webhook update_id '{update_id_str}': {e}", exc_info=True)
        # Avoid sending detailed error messages back unless necessary for debugging specific Telegram issues.
        return web.Response(status=500, text="Internal Server Error processing update")


# === Main Bot Execution Function ===
async def run_bot() -> None:
    """Initializes PTB, sets up handlers, and runs either aiohttp server or polling."""
    global application

    if not BOT_TOKEN or BOT_TOKEN.startswith("CRITICAL_FAILURE_TOKEN_MISSING"):
        logger.critical("FATAL: Invalid BOT_TOKEN. Halting.")
        sys.exit("Invalid BOT_TOKEN configuration.") # sys.exit is better here

    setup_secure_webhook_path() # Determine FINAL_WEBHOOK_PATH if needed

    # --- Persistence ---
    persistence = None
    if PERSISTENCE_PATH:
        try:
            persistence_dir = os.path.dirname(PERSISTENCE_PATH)
            if persistence_dir and not os.path.exists(persistence_dir):
                os.makedirs(persistence_dir, exist_ok=True)
                logger.info(f"Created persistence directory: {persistence_dir}")
            persistence = PicklePersistence(filepath=PERSISTENCE_PATH)
            logger.info(f"PicklePersistence enabled: {PERSISTENCE_PATH}")
        except Exception as e:
            logger.error(f"Failed to initialize PicklePersistence at {PERSISTENCE_PATH}: {e}. Continuing without persistence.", exc_info=True)
            persistence = None # Ensure it's None if init fails

    # --- Build PTB Application ---
    builder = ApplicationBuilder().token(BOT_TOKEN).post_init(post_initialization_hook)
    # Drop pending updates only if not using persistence or if specifically desired.
    # If persistence is used, you might want to process old updates on restart.
    # Default for ApplicationBuilder is drop_pending_updates=False.
    # If you want to drop them with persistence, add .drop_pending_updates(True)
    # builder = builder.drop_pending_updates(True)


    if persistence:
        builder = builder.persistence(persistence)
    else: # If no persistence, explicitly drop pending updates to avoid processing old ones on restart
        builder = builder.drop_pending_updates(True)
        logger.info("No persistence: pending updates will be dropped on startup.")


    try:
        application = builder.build()
    except InvalidToken:
        logger.critical("FATAL: The provided BOT_TOKEN is invalid. Halting.")
        sys.exit("Invalid BOT_TOKEN during Application build.")
    except Exception as e:
        logger.critical(f"FATAL: Failed to build PTB Application: {e}", exc_info=True)
        sys.exit("Failed to build PTB Application.")


    # --- Define Z1-Gray ConversationHandler ---
    # !! REPLACE ALL PLACEHOLDER HANDLERS WITH ACTUAL IMPORTED FUNCTIONS !!
    z1_gray_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", step_one_entry)], # From handlers.step_1
        states={
            AWAITING_STEP_TWO_ACK: [
                 MessageHandler(filters.Regex(r'^(OK|Ok|ok|YES|Yes|yes)$'), handle_step_2_ack), # Actual handler import
                 CallbackQueryHandler(handle_step_2_ack, pattern="^review_diagnostics_pressed$"), # Actual handler import
                 MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message)
            ],
            AWAITING_STEP_FIVE_CHOICE: [
                 CallbackQueryHandler(handle_step_4_choice_initiate, pattern="^step4_initiate_sync$"), # Actual handler import
                 CallbackQueryHandler(handle_step_4_choice_query, pattern="^step4_query_necessity$"), # Actual handler import
                 MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message) # Or specific handler
            ],
            STEP_5_AWAITING_FINAL_ACTION: [
                 CallbackQueryHandler(handle_final_sync_button, pattern="^final_sync_initiated$"), # Actual handler import
                 MessageHandler(filters.TEXT & ~filters.COMMAND, handle_step5_text_input) # Actual handler import
            ],
             STEP_5_FINAL_CHANCE_STATE: [
                 CallbackQueryHandler(handle_final_sync_button, pattern="^final_sync_initiated$"), # Actual handler import
                 MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message) # Or specific handler
            ],
             # Add STEP_5_REJECTION_WARNING_STATE handler if using that state
             # STEP_5_REJECTION_WARNING_STATE: [CallbackQueryHandler(handle_rejection_warning_callback)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.COMMAND, handle_unknown_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.WEB_APP_DATA, handle_unknown_message), # Avoid matching web_app_data here
            CallbackQueryHandler(handle_unknown_callback)
        ],
        per_user=True,
        name="z1_gray_funnel_aiohttp_prod", # Unique name
        allow_reentry=True, # step_one_entry MUST clear user_data if this is true and state needs reset
        persistent=(persistence is not None),
        # conversation_timeout=timedelta(hours=1) # Optional: Add a timeout for the conversation
    )
    application.add_handler(z1_gray_conv_handler)

    # Optional: Other global handlers (e.g., help, status) can be added here
    # application.add_handler(CommandHandler("help", help_command_placeholder))
    # application.add_error_handler(error_handler_placeholder) # Recommended

    # --- Start Application ---
    # The condition for starting aiohttp server
    if USE_WEBHOOK and WEBHOOK_URL and FINAL_WEBHOOK_PATH:
        logger.info("Initializing PTB application for Webhook mode...")
        await application.initialize() # Initializes bot, persistence, job queue etc.
        logger.info("Starting PTB application background tasks (job queue processing)...")
        await application.start() # Starts JobQueue, but not polling
        # Webhook is set by post_initialization_hook called during builder.build() via post_init

        logger.info("Setting up and starting aiohttp web server...")
        aiohttp_app = web.Application()
        # Ensure FINAL_WEBHOOK_PATH starts with a '/' as router expects paths.
        # setup_secure_webhook_path should ensure this.
        if FINAL_WEBHOOK_PATH and not FINAL_WEBHOOK_PATH.startswith('/'):
            logger.error(f"FINAL_WEBHOOK_PATH '{FINAL_WEBHOOK_PATH}' does not start with '/'. This will likely fail.")
            # Potentially prepend '/' here if it's a common misconfiguration, or rely on setup_secure_webhook_path
        aiohttp_app.router.add_post(FINAL_WEBHOOK_PATH, telegram_webhook_handler)

        runner = web.AppRunner(aiohttp_app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=PORT) # Use configured PORT

        try:
            await site.start()
            logger.info(f"✅ AIOHTTP Webhook server running on 0.0.0.0:{PORT}, path {FINAL_WEBHOOK_PATH}")
            await shutdown_event.wait() # Keep alive until shutdown signal
        except OSError as e: # Catch specific errors like "address already in use"
             logger.critical(f"AIOHTTP server failed to start on 0.0.0.0:{PORT}: {e}. Is the port in use?", exc_info=True)
             # Attempt to stop PTB if it was started.
             if application.running: await application.stop()
             await application.shutdown()
             sys.exit(f"AIOHTTP server failed: {e}")
        except Exception as e:
            logger.critical(f"Critical error during aiohttp server run: {e}", exc_info=True)
        finally:
            logger.info("Shutting down aiohttp server...")
            await site.stop() # Stop listening for new connections
            await runner.cleanup() # Clean up AppRunner resources
            logger.info("aiohttp server shut down.")
    else:
        logger.info("Starting bot in POLLING mode...")
        # For polling, we need to initialize, start job queue, and then start polling
        await application.initialize()
        await application.start()
        # For polling, run_polling handles signals internally if stop_signals is not empty.
        # To use our custom shutdown_event with polling, we'd need a more complex setup.
        # Simplest for now is to let run_polling handle SIGINT, SIGTERM, SIGABRT by default.
        # Or pass stop_signals=[] and manage shutdown_event.wait() in a surrounding task.
        # Given the graceful_signal_handler, we can try to manage it.

        # Let run_polling handle its own signals for simplicity with polling mode
        # await application.run_polling(allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY])

        # If we want to use our shutdown_event for polling too:
        stop_polling_task = asyncio.create_task(shutdown_event.wait())
        polling_task = asyncio.create_task(
            application.run_polling(
                allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY],
                stop_signals=None # We manage stop via shutdown_event
            )
        )
        # Wait for either polling to finish or shutdown event
        done, pending = await asyncio.wait(
            [polling_task, stop_polling_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending: task.cancel() # Cancel the other task

        if stop_polling_task in done: logger.info("Polling stopped due to shutdown signal.")
        if polling_task in done and polling_task.exception():
            logger.error(f"Polling task exited with an exception: {polling_task.exception()}", exc_info=polling_task.exception())


    # --- Final PTB Shutdown ---
    # This will be reached after webhook server stops or polling stops
    logger.info("Initiating final PTB application shutdown...")
    if application and hasattr(application, 'running') and application.running:
        logger.info("PTB application is running, attempting to stop...")
        await application.stop() # Stops JobQueue
    if application:
        await application.shutdown() # Cleans up persistence, bot object etc.
    logger.info("PTB application shut down completely.")

# === Program Entry Point ===
if __name__ == "__main__":
    # Setup signal handlers for graceful shutdown
    # These will trigger shutdown_event.set()
    signal.signal(signal.SIGINT, graceful_signal_handler)
    signal.signal(signal.SIGTERM, graceful_signal_handler)

    logger.info("Z1-Gray Bot (aiohttp Integration) Bootstrapping...")
    try:
        asyncio.run(run_bot())
    except RuntimeError as e: # e.g. "Event loop is closed" if run_bot exits unexpectedly
        if "Event loop is closed" not in str(e): # Avoid logging this if it's a normal part of shutdown
            logger.critical(f"Unhandled RuntimeError during bot execution: {e}.", exc_info=True)
        else:
            logger.info(f"Event loop closed, likely part of shutdown: {e}")
        # sys.exit(1) # Exiting here might prevent finally block in some cases
    except (KeyboardInterrupt, SystemExit) as e: # SystemExit can be raised by sys.exit()
        logger.info(f"Process terminated by signal or explicit exit: {type(e).__name__} - {e}")
    except Exception as e:
        logger.critical(f"FATAL UNHANDLED EXCEPTION at top level: {e}", exc_info=True)
        sys.exit(1) # Ensure non-zero exit code for critical failures
    finally:
        logger.info("Z1-Gray Bot execution cycle concluded.")
        # Ensure all log messages are flushed, especially for file handlers
        logging.shutdown()