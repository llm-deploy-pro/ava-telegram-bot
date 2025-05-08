#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main.py (Focus on fixing config import and subsequent errors)

import logging
import asyncio
import os
import signal
import sys
import secrets
from urllib.parse import urlparse
import logging.handlers
import time

# --- Absolute first: Configure sys.path for Render environment (DEBUGGING STEP) ---
# This is an attempt to forcefully ensure Python can find the 'config' package.
# Render usually handles this, but let's be explicit for debugging.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
    print(f"[SYS_PATH_DEBUG] Added PROJECT_ROOT to sys.path: {PROJECT_ROOT}", flush=True)

# Also add the parent of 'config' if 'main.py' is in 'src' and 'config' is at root
# e.g. if structure is /src/main.py and /config/settings.py
# then PROJECT_ROOT is /src, PROJECT_ROOT's parent is /
# PARENT_OF_PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
# if PARENT_OF_PROJECT_ROOT not in sys.path:
#     sys.path.insert(0, PARENT_OF_PROJECT_ROOT)
#     print(f"[SYS_PATH_DEBUG] Added PARENT_OF_PROJECT_ROOT to sys.path: {PARENT_OF_PROJECT_ROOT}", flush=True)


# --- Setup basic logging first, before any complex imports ---
log_format_initial = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d %(funcName)s] - %(message)s"
logging.basicConfig(format=log_format_initial, level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

logger.info(f"Python version: {sys.version}")
logger.info(f"Current sys.path after potential modifications: {sys.path}")
logger.info(f"Current working directory: {os.getcwd()}")
# Verify config package and settings.py file presence based on PROJECT_ROOT
CONFIG_DIR_ABS_PATH = os.path.join(PROJECT_ROOT, "config")
INIT_PY_ABS_PATH = os.path.join(CONFIG_DIR_ABS_PATH, "__init__.py")
SETTINGS_PY_ABS_PATH = os.path.join(CONFIG_DIR_ABS_PATH, "settings.py")

logger.info(f"Expected absolute path for 'config' directory: {CONFIG_DIR_ABS_PATH}")
logger.info(f"  'config' directory exists: {os.path.isdir(CONFIG_DIR_ABS_PATH)}")
logger.info(f"Expected absolute path for 'config/__init__.py': {INIT_PY_ABS_PATH}")
logger.info(f"  'config/__init__.py' exists: {os.path.isfile(INIT_PY_ABS_PATH)}")
logger.info(f"Expected absolute path for 'config/settings.py': {SETTINGS_PY_ABS_PATH}")
logger.info(f"  'config/settings.py' exists: {os.path.isfile(SETTINGS_PY_ABS_PATH)}")

if not os.path.isfile(INIT_PY_ABS_PATH):
    logger.critical(f"CRITICAL PRE-CHECK: 'config/__init__.py' NOT FOUND at '{INIT_PY_ABS_PATH}'. This is required for 'from config.settings import ...' to work. Please create an empty file there.")
    # sys.exit("Missing config/__init__.py") # Potentially exit early

from dotenv import load_dotenv
load_dotenv_success = load_dotenv() # Load .env before trying to access its variables
logger.info(f".env file loaded from default location: {load_dotenv_success}")


from telegram import Update, ReplyKeyboardRemove
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
from aiohttp import web

# --- Import Configurations from settings.py (More Robustly) ---
CONFIG_LOADED_SUCCESSFULLY = False
# Define fallbacks first
BOT_TOKEN_FALLBACK = "CRITICAL_FAILURE_TOKEN_MISSING_IN_MAIN_FALLBACK" # Made more specific
_BOT_TOKEN = os.getenv("BOT_TOKEN", BOT_TOKEN_FALLBACK)
_WEBHOOK_URL = None; _PORT = 8080; _CFG_WEBHOOK_PATH = None; _ADMIN_CHAT_ID = None;
_LOG_FILE_PATH = None; _PERSISTENCE_PATH = None; _DEVELOPMENT_MODE = False; _USE_WEBHOOK = False

logger.info(f"Pre-config import: Initial _BOT_TOKEN from env/fallback ends with '...{_BOT_TOKEN[-4:] if _BOT_TOKEN and len(_BOT_TOKEN)>4 else 'SHORT_OR_EMPTY'}'")

try:
    logger.info("Attempting to import specific variables from 'config.settings'...")
    # Try importing one by one for more granular error feedback if needed
    from config.settings import BOT_TOKEN as CFG_BOT_TOKEN
    logger.info(f"  Successfully imported BOT_TOKEN from config.settings. Ends with '...{CFG_BOT_TOKEN[-4:] if CFG_BOT_TOKEN and len(CFG_BOT_TOKEN)>4 else 'SHORT_OR_EMPTY'}'")

    from config.settings import WEBHOOK_URL as CFG_WEBHOOK_URL
    from config.settings import PORT as CFG_PORT
    from config.settings import WEBHOOK_PATH as CFG_SETTINGS_WEBHOOK_PATH
    from config.settings import ADMIN_CHAT_ID as CFG_ADMIN_CHAT_ID
    from config.settings import DEVELOPMENT_MODE as CFG_DEVELOPMENT_MODE
    from config.settings import USE_WEBHOOK as CFG_USE_WEBHOOK
    from config.settings import LOG_FILE_PATH as CFG_LOG_FILE_PATH
    from config.settings import PERSISTENCE_PATH as CFG_PERSISTENCE_PATH
    logger.info("Successfully imported all required variables from config.settings.")

    _BOT_TOKEN = CFG_BOT_TOKEN
    _WEBHOOK_URL = CFG_WEBHOOK_URL
    _PORT = CFG_PORT
    _CFG_WEBHOOK_PATH = CFG_SETTINGS_WEBHOOK_PATH
    _ADMIN_CHAT_ID = CFG_ADMIN_CHAT_ID
    _DEVELOPMENT_MODE = CFG_DEVELOPMENT_MODE
    _USE_WEBHOOK = CFG_USE_WEBHOOK
    _LOG_FILE_PATH = CFG_LOG_FILE_PATH
    _PERSISTENCE_PATH = CFG_PERSISTENCE_PATH
    CONFIG_LOADED_SUCCESSFULLY = True

except ImportError as e_import:
    logger.critical(f"CRITICAL: Failed to import from 'config.settings' (ImportError): {e_import}. Check that 'config/__init__.py' exists and 'config.settings.py' is free of errors that prevent import (e.g. syntax errors, or other unhandled exceptions during its own import phase).", exc_info=True)
except Exception as e_generic:
    logger.critical(f"CRITICAL: An unexpected EXCEPTION occurred WHILE importing from 'config.settings.py': {e_generic}. This could be an error within settings.py itself.", exc_info=True)

if not CONFIG_LOADED_SUCCESSFULLY:
    logger.error("******** CONFIGURATION LOAD FAILED. USING FALLBACKS. BOT WILL LIKELY MISBEHAVE OR CRASH. ********")
    logger.error(f"Using BOT_TOKEN (fallback): '...{_BOT_TOKEN[-4:] if _BOT_TOKEN and len(_BOT_TOKEN)>4 else 'SHORT_OR_EMPTY'}'")
    logger.error(f"Using USE_WEBHOOK (fallback): {_USE_WEBHOOK}")
    logger.error(f"Using WEBHOOK_URL (fallback): {_WEBHOOK_URL}")
else:
    logger.info("******** CONFIGURATION LOADED SUCCESSFULLY FROM config.settings.py. ********")
    logger.info(f"Using BOT_TOKEN (from settings): '...{_BOT_TOKEN[-4:] if _BOT_TOKEN and len(_BOT_TOKEN)>4 else 'SHORT_OR_EMPTY'}'")
    logger.info(f"Using USE_WEBHOOK (from settings): {_USE_WEBHOOK}")
    logger.info(f"Using WEBHOOK_URL (from settings): {_WEBHOOK_URL}")


# --- Assign to global-like uppercase variables ---
BOT_TOKEN = _BOT_TOKEN; WEBHOOK_URL = _WEBHOOK_URL; PORT = _PORT;
CFG_WEBHOOK_PATH = _CFG_WEBHOOK_PATH; ADMIN_CHAT_ID = _ADMIN_CHAT_ID;
DEVELOPMENT_MODE = _DEVELOPMENT_MODE; USE_WEBHOOK = _USE_WEBHOOK;
LOG_FILE_PATH = _LOG_FILE_PATH; PERSISTENCE_PATH = _PERSISTENCE_PATH


# --- Reconfigure Logging ---
# (Same as before, but now it's certain if settings were loaded)
if CONFIG_LOADED_SUCCESSFULLY:
    log_level_settings = logging.DEBUG if DEVELOPMENT_MODE else logging.INFO
    logging.getLogger().setLevel(log_level_settings)
    for handler_item in logging.getLogger().handlers:
        handler_item.setLevel(log_level_settings)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    ptb_log_level = logging.DEBUG if DEVELOPMENT_MODE else logging.INFO
    logging.getLogger("telegram.ext").setLevel(ptb_log_level)
    logging.getLogger("telegram.bot").setLevel(ptb_log_level)
    logger.info(f"Logging level re-configured to: {logging.getLevelName(log_level_settings)} (DEVELOPMENT_MODE={DEVELOPMENT_MODE})")
    if LOG_FILE_PATH:
        try:
            # (File logging setup - same as before)
            log_dir = os.path.dirname(LOG_FILE_PATH)
            if log_dir and not os.path.exists(log_dir): os.makedirs(log_dir, exist_ok=True)
            file_formatter = logging.Formatter(log_format_initial)
            file_handler = logging.handlers.RotatingFileHandler(LOG_FILE_PATH, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(log_level_settings)
            logging.getLogger().addHandler(file_handler)
            logger.info(f"File logging enabled: {LOG_FILE_PATH}")
        except Exception as e: logger.error(f"Failed to configure file logging to {LOG_FILE_PATH}: {e}", exc_info=True)
    else: logger.info("File logging not configured in settings.")
else:
    logger.warning("Logging remains at initial basicConfig INFO level due to settings import failure.")


# --- Startup Checks ---
if not BOT_TOKEN or BOT_TOKEN == BOT_TOKEN_FALLBACK:
    logger.critical(f"FATAL STARTUP CHECK: BOT_TOKEN is missing or using main fallback '{BOT_TOKEN_FALLBACK}'. Halting.")
    sys.exit("FATAL: Invalid BOT_TOKEN configuration.")

if USE_WEBHOOK and not WEBHOOK_URL: # This check is now more reliable
    logger.critical("FATAL STARTUP CHECK: USE_WEBHOOK is True, but WEBHOOK_URL is missing. Halting.")
    sys.exit("FATAL: Webhook mode enabled, but WEBHOOK_URL is missing.")

# --- Import States & State Map ---
# (Same as before)
try:
    from utils.state_definitions import *
    if 'STATE_NAME_MAP' not in globals() or not isinstance(STATE_NAME_MAP, dict):
        raise ImportError("STATE_NAME_MAP missing or not a dict.")
    logger.info(f"Loaded {len(STATE_NAME_MAP)} states from utils.state_definitions.")
except ImportError as e:
    logger.critical(f"CRITICAL: Failed to import from utils.state_definitions.py: {e}. Using fallbacks.", exc_info=True)
    AWAITING_STEP_TWO_ACK,AWAITING_STEP_THREE_ACK,AWAITING_STEP_FIVE_CHOICE=0,1,2 # type: ignore
    STEP_5_AWAITING_FINAL_ACTION,STEP_5_FINAL_CHANCE_STATE,STEP_5_REJECTION_WARNING_STATE=3,4,5 # type: ignore
    STATE_NAME_MAP={i:f"FALLBACK_STATE_{i}" for i in range(6)} # type: ignore

# --- Import Handlers (Placeholders) ---
# (Placeholders definitions are the same as your last working version for syntax)
# (Try-except blocks for handlers are the same)
try:
    from handlers.step_1 import step_one_entry
except ImportError:
    logger.error("CRITICAL: H1 Missing (handlers.step_1.step_one_entry). Using placeholder.")
    async def step_one_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: # type: ignore
        if update.message: await update.message.reply_text("[ERR] H1 (step_one_entry) Init Failed due to import error.")
        return ConversationHandler.END
try:
    from handlers.step_2 import handle_step_2_ack
except ImportError:
    logger.warning("Placeholder for handle_step_2_ack (handlers.step_2.handle_step_2_ack).")
    async def handle_step_2_ack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: # type: ignore
        logger.info("PH: S2 Ack triggered")
        if update.callback_query: await update.callback_query.answer("Placeholder: S2 Ack")
        elif update.message: await update.message.reply_text("Placeholder: S2 Ack")
        return AWAITING_STEP_THREE_ACK # type: ignore
try:
    from handlers.step_4 import handle_step_4_choice_initiate, handle_step_4_choice_query
except ImportError:
    logger.warning("Placeholders for handle_step_4_choice_initiate and handle_step_4_choice_query (handlers.step_4).")
    async def handle_step_4_choice_initiate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: # type: ignore
        logger.info("PH: S4 Init Sync triggered")
        if update.callback_query: await update.callback_query.answer("Placeholder: S4 Init Sync")
        return STEP_5_AWAITING_FINAL_ACTION # type: ignore
    async def handle_step_4_choice_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: # type: ignore
        logger.info("PH: S4 Query triggered")
        if update.callback_query: await update.callback_query.answer("Placeholder: S4 Query")
        return STEP_5_AWAITING_FINAL_ACTION # type: ignore
try:
    from handlers.step_5 import handle_final_sync_button, handle_step5_text_input, handle_final_chance_callback, handle_rejection_warning_callback
except ImportError:
    logger.warning("Placeholders for step_5 handlers (handlers.step_5).")
    async def handle_final_sync_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: # type: ignore
        logger.info("PH: S5 Final Sync Button triggered")
        if update.callback_query: await update.callback_query.answer("Placeholder: S5 Final Sync")
        return ConversationHandler.END # type: ignore
    async def handle_step5_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: # type: ignore
        logger.info("PH: S5 Text Input triggered")
        if update.message: await update.message.reply_text("Placeholder: S5 Text Input")
        return STEP_5_AWAITING_FINAL_ACTION # type: ignore
    async def handle_final_chance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: # type: ignore
        logger.info("PH: S5 Final Chance CB triggered")
        if update.callback_query: await update.callback_query.answer("Placeholder: S5 Final Chance CB")
        return ConversationHandler.END # type: ignore
    async def handle_rejection_warning_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: # type: ignore
        logger.info("PH: S5 Reject Warn CB triggered")
        if update.callback_query: await update.callback_query.answer("Placeholder: S5 Reject Warn CB")
        return STEP_5_FINAL_CHANCE_STATE # type: ignore
try:
    from handlers.unknown import handle_unknown_message, handle_unknown_command, handle_unknown_callback
except ImportError:
    logger.warning("Placeholders for unknown handlers (handlers.unknown).")
    async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: # type: ignore
        logger.info("PH: Unknown message handler triggered")
        if update.message: await update.message.reply_text("Placeholder: Unknown message.")
    async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: # type: ignore
        logger.info("PH: Unknown command handler triggered")
        if update.message: await update.message.reply_text("Placeholder: Unknown command.")
    async def handle_unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: # type: ignore
        logger.info("PH: Unknown callback handler triggered")
        if update.callback_query: await update.callback_query.answer("Placeholder: Unknown callback")


# --- Global Variables ---
shutdown_event = asyncio.Event()
application: Application | None = None
FINAL_WEBHOOK_PATH: str | None = None

# --- Secure Webhook Path Generation ---
# (Same as before, relies on global vars being correctly set)
def setup_secure_webhook_path() -> None:
    global FINAL_WEBHOOK_PATH
    if not USE_WEBHOOK or not WEBHOOK_URL:
        FINAL_WEBHOOK_PATH = None
        logger.info("setup_secure_webhook_path: Webhook mode not active or WEBHOOK_URL not set. Skipping.")
        return
    configured_path = CFG_WEBHOOK_PATH # User-configured path from settings
    secure_prefix_indicator = "tgwh_auto_"
    if configured_path and isinstance(configured_path, str) and configured_path.startswith("/") and len(configured_path) > 1:
        FINAL_WEBHOOK_PATH = configured_path
        logger.info(f"setup_secure_webhook_path: Using user-configured WEBHOOK_PATH: {FINAL_WEBHOOK_PATH}")
    else:
        if configured_path: logger.warning(f"setup_secure_webhook_path: Configured WEBHOOK_PATH ('{configured_path}') invalid. Generating.")
        else: logger.info("setup_secure_webhook_path: WEBHOOK_PATH not configured. Generating.")
        FINAL_WEBHOOK_PATH = f"/{secure_prefix_indicator}{secrets.token_urlsafe(24)}"
        logger.info(f"setup_secure_webhook_path: Using auto-generated WEBHOOK_PATH: {FINAL_WEBHOOK_PATH}")


# --- Signal Handler ---
# (Same as before)
def graceful_signal_handler(sig, frame):
    logger.info(f"Signal {sig} received. Setting shutdown event...")
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running(): loop.call_soon_threadsafe(shutdown_event.set)
        else: shutdown_event.set()
    except RuntimeError:
        logger.warning("No running event loop for signal handler, setting event directly.")
        shutdown_event.set()

# --- Post Initialization Hook (Webhook Setup) ---
# (Same as before - relies on global vars)
async def post_initialization_hook(app: Application) -> None:
    webhook_setup_successful = False
    full_webhook_url_for_notification = "N/A"
    if USE_WEBHOOK and WEBHOOK_URL and FINAL_WEBHOOK_PATH and BOT_TOKEN and BOT_TOKEN != BOT_TOKEN_FALLBACK:
        parsed_url = urlparse(WEBHOOK_URL)
        if not parsed_url.scheme or not parsed_url.netloc:
            logger.critical(f"post_initialization_hook: Invalid WEBHOOK_URL '{WEBHOOK_URL}'. Webhook NOT set.")
        else:
            base_webhook_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            full_webhook_url = f"{base_webhook_url}{FINAL_WEBHOOK_PATH}"
            full_webhook_url_for_notification = full_webhook_url
            logger.info(f"post_initialization_hook: Attempting to set webhook: {full_webhook_url}")
            # (Rest of set_webhook logic is same)
            max_retries = 3; allowed_updates = [Update.MESSAGE, Update.CALLBACK_QUERY]
            for attempt in range(max_retries):
                try:
                    await app.bot.set_webhook(url=full_webhook_url, allowed_updates=allowed_updates, drop_pending_updates=True)
                    webhook_info = await app.bot.get_webhook_info()
                    if webhook_info and webhook_info.url == full_webhook_url:
                        logger.info(f"post_initialization_hook: Webhook set successfully (Attempt {attempt + 1}): {webhook_info.url}")
                        webhook_setup_successful = True; break
                    else: logger.warning(f"post_initialization_hook: Webhook set attempt {attempt + 1} failed. URL mismatch/No Info. Expected: {full_webhook_url}, Got: {webhook_info.url if webhook_info else 'None'}")
                except InvalidToken: logger.critical("post_initialization_hook: Invalid Bot Token. Cannot set webhook."); break
                except BadRequest as e:
                    logger.error(f"post_initialization_hook: BadRequest setting webhook attempt {attempt + 1}: {e}.", exc_info=(attempt == max_retries - 1))
                    if "url host is empty" in str(e).lower() or "wrong url" in str(e).lower(): logger.critical(f"The webhook URL '{full_webhook_url}' is malformed/inaccessible."); break
                except Exception as e: logger.error(f"post_initialization_hook: Generic error setting webhook attempt {attempt + 1}: {e}", exc_info=(attempt == max_retries - 1))
                if attempt < max_retries - 1: await asyncio.sleep(2**(attempt + 1))
            if not webhook_setup_successful: logger.critical("post_initialization_hook: Webhook setup FAILED after all retries.")
    elif USE_WEBHOOK: logger.warning("post_initialization_hook: Skipping webhook setup (missing prerequisites or settings import failed).")
    else: logger.info("post_initialization_hook: Polling mode. Skipping webhook setup.")

    if app.job_queue: logger.info(f"post_initialization_hook: JobQueue available. Initial jobs: {len(app.job_queue.jobs())}")
    else: logger.warning("post_initialization_hook: JobQueue not available.")

    if ADMIN_CHAT_ID: # Check if ADMIN_CHAT_ID was successfully loaded
        # (Admin notification logic is same)
        mode = "Webhook (Active)" if webhook_setup_successful else ("Webhook (Setup FAILED!)" if USE_WEBHOOK else "Polling")
        try:
            bot_info = await app.bot.get_me()
            from telegram.helpers import escape_markdown
            safe_bot_username = escape_markdown(bot_info.username or "UnknownBot", version=2)
            safe_webhook_url_display = escape_markdown(full_webhook_url_for_notification, version=2) if webhook_setup_successful else "N/A"
            startup_message = (f"✅ *Z1\\-Gray Bot Online*\n*Mode:* `{mode}`\n*Node:* `@{safe_bot_username}`\n*TS:* `{time.strftime('%Y-%m-%d %H:%M:%S %Z')}`")
            if USE_WEBHOOK: startup_message += f"\n*Webhook URL:* `{safe_webhook_url_display}`"
            await app.bot.send_message(chat_id=ADMIN_CHAT_ID, text=startup_message, parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f"post_initialization_hook: Startup notification sent to ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
        except Exception as e: logger.error(f"post_initialization_hook: Failed to send startup notification: {e}", exc_info=True)

# === Conversation Fallback Handler ===
# (Same as before)
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user; user_id_log = user.id if user else "N/A"
    current_state_val = context.user_data.get(ConversationHandler.STATE) if context.user_data else None
    state_name = STATE_NAME_MAP.get(current_state_val, f"UNKNOWN({current_state_val})") if current_state_val is not None else "N/A"
    logger.info(f"[CONV_CANCEL] User {user_id_log} (State: {state_name}) executed /cancel.")
    if context.user_data: context.user_data.clear()
    if update.message: await update.message.reply_text("`[PROTOCOL_SESSION_TERMINATED]`\n`Session reset. Send /start to re-initiate.`", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=ReplyKeyboardRemove())
    elif update.callback_query:
        await update.callback_query.answer("Conversation cancelled.")
        if update.effective_chat:
            try: await context.bot.send_message(chat_id=update.effective_chat.id, text="`[PROTOCOL_SESSION_TERMINATED]`\n`Session reset. Send /start to re-initiate.`", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=ReplyKeyboardRemove())
            except Exception as e: logger.error(f"Error sending cancel confirmation in callback: {e}")
    return ConversationHandler.END

# === Webhook Handler (aiohttp) ===
# (Same as before)
async def telegram_webhook_handler(request: web.Request) -> web.Response:
    global application
    if not application or not application.bot :
        logger.error("telegram_webhook_handler: PTB Application or .bot not initialized.")
        return web.Response(status=503, text="Bot Service Unavailable")
    try: update_data = await request.json()
    except Exception as e: logger.error(f"telegram_webhook_handler: Failed to parse JSON: {e}", exc_info=True); return web.Response(status=400, text="Bad Request: Invalid JSON")
    try:
        update = Update.de_json(update_data, application.bot)
        asyncio.create_task(application.process_update(update))
        return web.Response(status=200, text="OK")
    except Exception as e:
        update_id_str = update_data.get('update_id', 'N/A')
        logger.error(f"telegram_webhook_handler: Error processing update_id '{update_id_str}': {e}", exc_info=True)
        return web.Response(status=500, text="Internal Server Error processing update")

# === Main Bot Execution Function ===
async def run_bot() -> None:
    global application

    if not BOT_TOKEN or BOT_TOKEN == BOT_TOKEN_FALLBACK:
        logger.critical("run_bot: CRITICAL - BOT_TOKEN is invalid even after config load attempts. Halting.")
        sys.exit("FATAL: BOT_TOKEN invalid at run_bot start.")

    logger.info(f"run_bot: BOT_TOKEN ends with '...{BOT_TOKEN[-4:] if BOT_TOKEN and len(BOT_TOKEN)>4 else 'SHORT_OR_EMPTY'}'")
    logger.info(f"run_bot: USE_WEBHOOK is {USE_WEBHOOK}, WEBHOOK_URL is {WEBHOOK_URL}")

    setup_secure_webhook_path() # Depends on USE_WEBHOOK and WEBHOOK_URL being correct

    persistence = None
    if PERSISTENCE_PATH:
        # (Persistence setup is same as before)
        try:
            persistence_dir = os.path.dirname(PERSISTENCE_PATH)
            if persistence_dir and not os.path.exists(persistence_dir): os.makedirs(persistence_dir, exist_ok=True); logger.info(f"Created persistence directory: {persistence_dir}")
            persistence = PicklePersistence(filepath=PERSISTENCE_PATH)
            logger.info(f"PicklePersistence enabled: {PERSISTENCE_PATH}")
        except Exception as e: logger.error(f"Failed to init PicklePersistence: {e}. No persistence.", exc_info=True); persistence = None
    else: logger.info("Persistence not configured (PERSISTENCE_PATH not set/loaded).")

    # --- Build PTB Application ---
    try:
        logger.info(f"run_bot: Building ApplicationBuilder with BOT_TOKEN.")
        builder = ApplicationBuilder().token(BOT_TOKEN).post_init(post_initialization_hook)

        if persistence:
            builder = builder.persistence(persistence)
            logger.info("run_bot: Persistence added to builder. Pending updates default to NOT dropped.")
            # If you require dropping with persistence: builder = builder.drop_pending_updates(True)
        else:
            builder = builder.drop_pending_updates(True) # This is correct for PTB v20.x
            logger.info("run_bot: No persistence. Added drop_pending_updates(True) to builder.")

        logger.info(f"run_bot: About to call builder.build(). Type of builder: {type(builder)}")
        application = builder.build()
        logger.info("run_bot: PTB Application built successfully.")

    except InvalidToken:
        logger.critical(f"run_bot: FATAL InvalidToken during Application build. BOT_TOKEN (ends '...{BOT_TOKEN[-4:] if BOT_TOKEN and len(BOT_TOKEN)>4 else 'SHORT'}') is invalid.")
        sys.exit("FATAL: Invalid BOT_TOKEN for Application build.")
    except AttributeError as e_attr: # Catch the specific error if it still occurs
        logger.critical(f"run_bot: FATAL AttributeError during ApplicationBuilder chain: {e_attr}. THIS IS UNEXPECTED for PTB v20.8+ if BOT_TOKEN was valid.", exc_info=True)
        logger.critical(f"run_bot: Type of 'builder' object right before .build() was called: {type(builder)}")
        sys.exit(f"FATAL: AttributeError building PTB Application: {e_attr}")
    except Exception as e_build:
        logger.critical(f"run_bot: FATAL Exception during Application build: {e_build}", exc_info=True)
        sys.exit(f"FATAL: Failed to build PTB Application: {e_build}")

    # --- Define ConversationHandler ---
    # (Same as before)
    z1_gray_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", step_one_entry)],
        states={
            AWAITING_STEP_TWO_ACK: [MessageHandler(filters.Regex(r'^(OK|Ok|ok|YES|Yes|yes)$'), handle_step_2_ack), CallbackQueryHandler(handle_step_2_ack, pattern="^review_diagnostics_pressed$"), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message)],
            AWAITING_STEP_FIVE_CHOICE: [CallbackQueryHandler(handle_step_4_choice_initiate, pattern="^step4_initiate_sync$"), CallbackQueryHandler(handle_step_4_choice_query, pattern="^step4_query_necessity$"), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message)],
            STEP_5_AWAITING_FINAL_ACTION: [CallbackQueryHandler(handle_final_sync_button, pattern="^final_sync_initiated$"), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_step5_text_input)],
            STEP_5_FINAL_CHANCE_STATE: [CallbackQueryHandler(handle_final_sync_button, pattern="^final_sync_initiated$"), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation), MessageHandler(filters.COMMAND, handle_unknown_command), MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.WEB_APP_DATA, handle_unknown_message), CallbackQueryHandler(handle_unknown_callback)],
        per_user=True, name="z1_gray_funnel_aiohttp_prod", allow_reentry=True, persistent=(persistence is not None),
    )
    application.add_handler(z1_gray_conv_handler)


    # --- Start Application (Webhook or Polling) ---
    # (Logic is same as before, but relies on global vars being correct now)
    if USE_WEBHOOK and WEBHOOK_URL and FINAL_WEBHOOK_PATH:
        logger.info("run_bot: Initializing PTB application for Webhook mode...")
        await application.initialize()
        await application.start() # Starts JobQueue
        logger.info("run_bot: Setting up and starting aiohttp web server...")
        aiohttp_app = web.Application()
        if not FINAL_WEBHOOK_PATH.startswith('/'):
            logger.critical(f"run_bot: FATAL - FINAL_WEBHOOK_PATH '{FINAL_WEBHOOK_PATH}' misconfigured (no leading '/'). Halting.")
            if application.running: await application.stop()
            await application.shutdown(); sys.exit("Webhook path misconfiguration.")
        aiohttp_app.router.add_post(FINAL_WEBHOOK_PATH, telegram_webhook_handler)
        runner = web.AppRunner(aiohttp_app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
        try:
            await site.start()
            logger.info(f"✅ run_bot: AIOHTTP Webhook server running on 0.0.0.0:{PORT}, path {FINAL_WEBHOOK_PATH}")
            await shutdown_event.wait()
        except OSError as e_os:
             logger.critical(f"run_bot: AIOHTTP server failed to start on 0.0.0.0:{PORT}: {e_os}. Port in use?", exc_info=True)
             if application.running: await application.stop()
             await application.shutdown(); sys.exit(f"AIOHTTP server failed: {e_os}")
        except Exception as e_aiohttp: logger.critical(f"run_bot: Critical error during aiohttp server run: {e_aiohttp}", exc_info=True)
        finally:
            logger.info("run_bot: Shutting down aiohttp server..."); await site.stop(); await runner.cleanup(); logger.info("run_bot: aiohttp server shut down.")
    else:
        logger.info(f"run_bot: Starting bot in POLLING mode (USE_WEBHOOK={USE_WEBHOOK}, WEBHOOK_URL={WEBHOOK_URL}, FINAL_WEBHOOK_PATH={FINAL_WEBHOOK_PATH}).")
        await application.initialize(drop_pending_updates=(not persistence)) # Drop if no persistence
        await application.start() # Starts JobQueue
        stop_polling_task = asyncio.create_task(shutdown_event.wait())
        polling_task = asyncio.create_task(application.run_polling(allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY], stop_signals=None))
        done, pending = await asyncio.wait([polling_task, stop_polling_task], return_when=asyncio.FIRST_COMPLETED)
        for task in pending: task.cancel()
        if stop_polling_task in done: logger.info("run_bot: Polling stopped due to shutdown signal.")
        if polling_task in done:
            try: polling_task.result()
            except asyncio.CancelledError: logger.info("run_bot: Polling task was cancelled.")
            except Exception as e_poll: logger.error(f"run_bot: Polling task exited with an exception: {e_poll}", exc_info=e_poll)

    # --- Final PTB Shutdown ---
    logger.info("run_bot: Initiating final PTB application shutdown...")
    if application:
        if hasattr(application, 'running') and application.running:
            logger.info("run_bot: PTB application is running, stopping JobQueue..."); await application.stop()
        await application.shutdown() # Cleanup
    logger.info("run_bot: PTB application shut down completely.")


# === Program Entry Point ===
if __name__ == "__main__":
    # Setup signal handlers earlier if possible, but they need graceful_signal_handler defined
    signal.signal(signal.SIGINT, graceful_signal_handler)
    signal.signal(signal.SIGTERM, graceful_signal_handler)

    logger.info(f"--- Z1-Gray Bot Bootstrapping (PID: {os.getpid()}) ---")
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit) as e_exit:
        logger.info(f"Process terminated: {type(e_exit).__name__} - {e_exit}")
    except RuntimeError as e_runtime:
        if "Event loop is closed" not in str(e_runtime):
            logger.critical(f"Unhandled RuntimeError: {e_runtime}.", exc_info=True)
        else: logger.info(f"Event loop closed, likely part of shutdown: {e_runtime}")
    except Exception as e_fatal:
        logger.critical(f"FATAL UNHANDLED EXCEPTION AT TOP LEVEL: {e_fatal}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info(f"--- Z1-Gray Bot execution cycle concluded (PID: {os.getpid()}) ---")
        logging.shutdown()