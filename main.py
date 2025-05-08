#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
import os
import signal
import sys
import secrets
from urllib.parse import urlparse
from datetime import timedelta
import time # Added for admin message timestamp

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler, # Added CallbackQueryHandler
    PicklePersistence,
)
from telegram.error import InvalidToken, BadRequest
from telegram.constants import ParseMode # Added ParseMode
from dotenv import load_dotenv
from aiohttp import web

# --- 配置 Logging ---
# Use the detailed format from the final optimized version
log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
logging.basicConfig(format=log_format, level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.INFO) # Adjust based on DEVELOPMENT_MODE later if needed
logger = logging.getLogger(__name__)

# --- 加载环境变量 ---
load_dotenv()

# --- 从环境变量获取配置 ---
# Use variables consistent with the final optimized main.py
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") # Renamed from WEBHOOK_URL_BASE for consistency
PORT = int(os.getenv("PORT", "8080"))
CFG_WEBHOOK_PATH = os.getenv("WEBHOOK_PATH") # Get user configured path first
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"
DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "false").lower() in ("true", "1", "yes")
PERSISTENCE_PATH = os.getenv("PERSISTENCE_PATH") # For optional persistence
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH") # For optional file logging

# Reconfigure logging level based on DEVELOPMENT_MODE
log_level = logging.DEBUG if DEVELOPMENT_MODE else logging.INFO
logging.getLogger().setLevel(log_level) # Set root logger level
for handler in logging.getLogger().handlers: handler.setLevel(log_level)
logging.getLogger("telegram.ext").setLevel(logging.INFO if not DEVELOPMENT_MODE else logging.DEBUG)
logger.info(f"Logging level set to: {logging.getLevelName(log_level)} (DEVELOPMENT_MODE={DEVELOPMENT_MODE})")

# File Logging setup (optional)
if LOG_FILE_PATH:
    try:
        import logging.handlers
        log_dir = os.path.dirname(LOG_FILE_PATH)
        if log_dir and not os.path.exists(log_dir): os.makedirs(log_dir, exist_ok=True)
        file_formatter = logging.Formatter(log_format)
        file_handler = logging.handlers.RotatingFileHandler(LOG_FILE_PATH, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        logging.getLogger().addHandler(file_handler)
        logger.info(f"File logging enabled: {LOG_FILE_PATH}")
    except Exception as e:
        logger.error(f"Failed to configure file logging to {LOG_FILE_PATH}: {e}", exc_info=True)

# --- 启动前检查 ---
if not BOT_TOKEN or BOT_TOKEN.startswith("YOUR_FALLBACK_TOKEN"): # Check for placeholder too
    logger.critical("FATAL: BOT_TOKEN missing or invalid. Halting.")
    # Use raise RuntimeError for a cleaner exit than sys.exit in main async context
    raise RuntimeError("Invalid BOT_TOKEN configuration.")

if USE_WEBHOOK and not WEBHOOK_URL:
    logger.critical("FATAL: USE_WEBHOOK is true, but WEBHOOK_URL environment variable is not found. Halting.")
    raise RuntimeError("Webhook mode enabled, but WEBHOOK_URL is missing.")

# --- Secure Webhook Path Generation ---
def get_secure_webhook_path() -> str:
    # ... (Use the secure path generation logic from the previous optimized version) ...
    configured_path = CFG_WEBHOOK_PATH
    secure_prefix = "/z1_secure_"
    if configured_path and isinstance(configured_path, str) and configured_path.startswith(secure_prefix):
        return configured_path
    else:
        if configured_path: logger.warning(f"Configured WEBHOOK_PATH ('{configured_path}') invalid/insecure. Generating secure path.")
        else: logger.info("WEBHOOK_PATH not configured. Generating secure path.")
        secure_suffix = secrets.token_urlsafe(16)
        generated_path = f"/tgwh_auto_{secure_suffix}"
        logger.info(f"Using auto-generated secure WEBHOOK_PATH: {generated_path}")
        return generated_path

FINAL_WEBHOOK好的，我完全理解了。您希望保留这份集成了 `aiohttp` 以手动处理Webhook的 `main.py`_PATH = get_secure_webhook_path() if USE_WEBHOOK and WEBHOOK_URL else None
if USE_WEBHOOK and not FINAL_WEBHOOK_PATH:
     logger.warning("Webhook mode selected but final path could not be determined securely.")
     # Decide if this is fatal or if we fall back to polling. Let 的**基础架构和Webhook调用方式**，但是需要将其中定义的**对话逻辑（`ConversationHandler` 的 `states` 和对应的处理函数）** 替换为我们最终确定的**Z1-Gray五步剧本**的逻辑。

这意味着我们需要：

1.  **保留 `main.py` 中 `aiohttp` 服务器's make it non-fatal for now.
     USE_WEBHOOK = False
     logger.info("Falling back to POLLING mode due to Webhook Path issue.")

# --- 构建完整的 Telegram Webhook URL (用于 set_webhook) ---
FULL_TELEGRAM_WEBHOOK_URL = f"{WEBHOOK_URL.rstrip('/')}{FINAL_WEBHOOK_PATH}" if USE_WEBHOOK and WEBHOOK_URL and FINAL_WEBHOOK_PATH else None

if USE_WEBHOOK:
    logger.info(f"Bot configured for WEBHOOK mode.")
    logger.info(f的设置、启动和Webhook处理函数 (`telegram_webhook_handler`) 的整体结构。**
2.  **保留信号处理、日志配置、全局变量等基础设施。**
3.  **删除**原有的 `CONFIRM_START` 到 `AWAIT_PAYMENT_PROMPT_ACK` 的状态常量定义。
4.  **删除**原有的 `start_conversation`, `handle_confirmation`, `handle_q1_response`, `handle_q2_response`, `handle_diagnosis_ack`, `handle_urgency_ack`, `cancel`, `handle_invalid_conversation_input`, `help_command`, `status_command`, `upgrade_command"Base URL: {WEBHOOK_URL}")
    logger.info(f"Webhook Path: {FINAL_WEBHOOK_PATH}")
    logger.info(f"Full URL to register with Telegram: {FULL_TELEGRAM_WEBHOOK_URL}")
    logger.info(f"aiohttp server to listen on 0.0.0.0:{PORT}")
else:
    logger.info("Bot configured for POLLING mode.")

# --- 全局变量 ---
shutdown_event = asyncio.Event()
application: Application | None = None # PTB Application instance

# --- Z1-Gray 状态常量 (从 utils.state_definitions 导入) ---
# IMPORTANT: Ensure utils/state_definitions.py exists and defines these states
try:
    from utils.state_definitions import (
        AWAITING_STEP_TWO_ACK,
        AWAITING_STEP_THREE_ACK, # If Step 3 needs an explicit ACK state
        AWAITING_STEP_FIVE_CHOICE,
        STEP_5_AWAITING_FINAL` 这些与旧剧本相关的handler函数。
5.  **引入**我们为Z1-Gray设计的状态常量（从 `utils.state_definitions` 导入）。
6.  **引入**我们为Z1-Gray设计的各个步骤的入口函数和处理函数（从 `handlers/` 目录导入）。
7.  **重新构建 `ConversationHandler`**，使用新的Z1-Gray状态和对应的（从 `handlers/` 导入的）处理器函数。
8.  确保 `ApplicationBuilder` 和 `application` 的初始化与注册流程正确。

**以下是将Z1-Gray剧本逻辑整合到您提供的 `aiohttp` 集成版 `main.py` 架构中的优化后完整代码：**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main.py (Z1-Gray Version with aiohttp integration)

import logging
import asyncio
import os
import signal
import sys
import secrets
from urllib.parse import urlparse
from datetime import timedelta
import logging.handlers
import time

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,_ACTION,
        STEP_5_FINAL_CHANCE_STATE,
        STEP_5_REJECTION_WARNING_STATE, # If using the buffer state
        STATE_NAME_MAP
    )
    logger.info("Successfully loaded Z1-Gray states from state_definitions.")
except ImportError:
    logger.critical("CRITICAL: Failed to load states from utils/state_definitions.py. Defining minimal fallbacks.")
    AWAITING_STEP_TWO_ACK, AWAITING_STEP_THREE_ACK, AWAITING_STEP_FIVE_CHOICE = 0, 1, 2
    STEP_5_AWAITING_FINAL_ACTION, STEP_5_FINAL_CHANCE_STATE, STEP_5_REJECTION_WARNING_STATE = 3, 4, 5
    STATE_NAME_MAP = {i: f"FALLBACK_STATE_{i}" for i in range(6)}

# === Z1-Gray Conversation Handlers (Placeholders - MUST BE REPLACED) ===
# Import the *actual* implemented handlers from your handlers/ directory
try: from handlers.step_1 import step_one_entry
except ImportError: logger.error("CRITICAL: handlers.step_1.step_one_entry MISSING."); async def step_one_entry(u,c): await u.message.reply_text("[ERR] H1 Missing."); return ConversationHandler.END # type: ignore
try: from handlers.step_2 import handle_step_2_ack # Example name for handler processing Step 2 Ack
except ImportError: logger.warning("Using placeholder for handle_step_2_ack."); async def handle_step_2_ack(u,c): logger.info("PH: Handling Step 2 Ack"); return AWAITING_STEP_THREE_ACK # type: ignore
try: from handlers.step_4 import handle_step_4_choice # Example name for handler processing Step 4 Buttons
except ImportError: logger.warning("Using placeholder for handle
    ContextTypes,
    PicklePersistence # Keep import for optional persistence
)
from telegram.error import InvalidToken, BadRequest
from telegram.constants import ParseMode
from dotenv import load_dotenv
from aiohttp import web # Ensure aiohttp is imported

# --- Configure Logging ---
# Basic config first, in case settings import fails
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__) # Get logger instance for early logs

# --- Attempt to import configurations and handlers ---
try:
    from config.settings import (
        BOT_TOKEN, WEBHOOK_URL, PORT,
        WEBHOOK_PATH as CFG_WEBHOOK_PATH,
        ADMIN_CHAT_ID, DEVELOPMENT_MODE, USE_WEBHOOK, # Assuming USE_WEBHOOK is correctly set to true for this file
        LOG_FILE_PATH, PERSISTENCE_PATH
    )
    # Reconfigure logging based on loaded settings
    log_level = logging.DEBUG if DEVELOPMENT_MODE else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]: root_logger.removeHandler(handler) # Clear default handlers
    logging.basicConfig(format=log_format, level=log_level, handlers=[logging.StreamHandler()])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING) # Silence aiohttp access logs if desired
    logging.getLogger("telegram.ext").setLevel(logging.INFO if not DEVELOPMENT_MODE else logging.DEBUG)
    logger.info("Logging reconfigured based on settings.py.")

    # Setup File Logging if path is configured
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
    WEBHOOK_URL = None; PORT = 8080; CFG_WEBHOOK_PATH = None; ADMIN_step_4_choice."); async def handle_step_4_choice(u,c): logger.info("PH: Handling Step 4 Choice"); await u.callback_query.answer(); return STEP_5_AWAITING_FINAL_ACTION # type: ignore
try: from handlers.step_5 import handle_final_sync_button, handle_step5_text_input, handle_final_chance_button # Example handlers
except ImportError: logger.warning("Using placeholders for step_5 handlers."); async def handle_final_sync_button(u,c): logger.info("PH: Handling Final Sync"); await u.callback_query.answer(); return ConversationHandler.END # type: ignore ; async def handle_step5_text_input(u,c): logger.info("PH: Handling Step 5 Text"); return STEP_5_AWAITING_FINAL_ACTION # type: ignore; async def handle_final_chance_button(u,c): logger.info("PH: Handling Final Chance"); await u.callback_query.answer(); return ConversationHandler.END # type: ignore
try: from handlers.unknown import handle_unknown_message, handle_unknown_command, handle_unknown_callback
except ImportError: logger.warning("Using placeholders for unknown handlers."); async def handle_unknown_message(u,c):pass # type: ignore ; async def handle_unknown_command(u,c):pass # type: ignore ; async def handle_unknown_callback(u,c): await u.callback_query.answer() # type: ignore

# === Conversation Fallback Handler for /cancel ===
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id_log = user.id if user else "N/A"
    current_state_val = context.user_data.get(ConversationHandler.STATE)
    state_name = STATE_NAME_MAP.get(current_state_val, f"UNKNOWN({current_state_val})") if current_state_val is not None else "N/A"
    logger.info(f"[CONV_CANCEL] User {user_id_log} (State: {state_name}) executed /cancel.")
    context.user_data.clear()
    await update.message.reply_text(
        "`[PROTOCOL_SESSION_TERMINATED]`\n`User directive: SESSION_RESET. System idle.`\n`/start` `to re-initiate.`",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return ConversationHandler.END

# === Webhook Handler (for aiohttp integration) ===
async def telegram_webhook_handler(request: web.Request) -> web.Response:
    """Handle webhook POST requests from Telegram and process them via PTB."""
    global application
    if not application:
        logger.error("Webhook received but PTB Application not initialized.")
        return web.Response(status=503, text="Bot Application Not Ready")
    try:
        update_data = await request.json()
        update = Update.de_json(update_data, application.bot)
        # Use process_update which handles updates concurrently
        asyncio.create_task(application.process_update(update))
        return web.Response(status=200, text="OK") # Acknowledge Telegram quickly
    except Exception as e:
        logger.error(f"Error processing webhook request body or update: {e}", exc_info=True)
        return web.Response(status=400, text="Error processing update data") # Bad request if JSON fails or de_json fails

# === Signal Handler (Synchronous part - needed for clean shutdown) ===
def handle_signal_sync(sig, frame):
    logger.info(f"Received OS signal {signal.Signals(sig).name}. Setting shutdown event.")
    loop = asyncio.get_event_loop_policy().get_event_loop()
    if loop.is_running(): loop.call_soon_threadsafe(shutdown_event.set)
    else: shutdown_event.set()

# === Post Initialization Hook (Webhook Setup) ---
async def post_init_hook(app: ApplicationBuilder.application_type) -> None:
    webhook_setup_successful = False
    allowed_updates = [Update.MESSAGE, Update.CALLBACK_QUERY] # Minimal needed

    if USE_WEBHOOK and WEBHOOK_URL and FINAL_WEBHOOK_PATH and BOT_TOKEN and not BOT_TOKEN.startswith("YOUR_FALLBACK"):
        parsed_url = urlparse(WEBHOOK_URL)
        if not parsed_url.scheme == "https" or not parsed_url.netloc:
            logger.critical(f"Invalid WEBHOOK_URL '{WEBHOOK_URL}'. Webhook NOT set.")
        else:
            full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}{FINAL_WEBHOOK_PATH}"
            logger.info(f"Attempting to set webhook (retries=3): {full_webhook_url}")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await app.bot.set_webhook(url=full_webhook_url, allowed_updates=allowed_updates, drop_pending_updates=True)
                    webhook_info = await app.bot.get_webhook_info()
                    if webhook_info and webhook_info.url == full_webhook_url:
                        logger.info(f"Webhook set successfully on attempt {attempt + 1}: {webhook_info.url}")
                        webhook_setup_successful = True
                        break
                    else: logger.warning(f"Webhook set attempt {attempt + 1} failed. URL mismatch/No Info. Got: {webhook_info.url if webhook_info else 'None'}")
                except Exception as e: logger.error(f"Error setting webhook attempt {attempt + 1}: {e}", exc_info=(attempt == max_retries - 1))
                if attempt < max_retries - 1:
                    wait_time = 2**(attempt + 1); logger.info(f"Retrying webhook setup in {wait_time}s...")
                    await asyncio.sleep(wait_time)
            if not webhook_setup_successful: logger.critical("Webhook setup FAILED after retries.")
    else:
        logger.info("Polling mode active or Webhook config invalid/missing.")

    # Admin notification logic remains the same as your last provided version...
    if ADMIN_CHAT_ID:
        mode = "Webhook (Active)" if webhook_setup_successful else ("Webhook (Setup FAILED!)" if USE_WEBHOOK else "Polling")
        try:
            bot_info = await app.bot.get_me()
            from telegram.helpers import escape_markdown
            safe_bot_username = escape_markdown(bot_info.username or "Unknown", version=2)
            safe_webhook_url = escape_markdown(full_webhook_url, version=2) if webhook_setup_successful else "N/A"
            startup_message = f"✅ *Z1\\-Gray Bot Online*\n*Mode:* `{mode}`\n*Node:* `@{safe_bot_username}`\n*TS:* `{time.strftime('%Y-%m-%d %H:%M:%S %Z')}`"
            if webhook_setup_successful: startup_message += f"\n*Webhook:* `{safe_webhook_url}`"
            await app.bot.send_message(chat_id=ADMIN_CHAT_ID, text=startup_message, parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f"Startup notification sent to ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
        except Exception as e: logger.error(f"Failed to send startup notification: {e}")


# === Main Application Logic ===
async def run_bot() -> None:
    """Initializes PTB, sets webhook, and runs the aiohttp server FOR webhook mode."""
    global application

    if not BOT_TOKEN or BOT_TOKEN.startswith("YOUR_FALLBACK"):
        logger.critical("FATAL: Invalid BOT_TOKEN. Halting.")
        raise RuntimeError("Invalid BOT_TOKEN configuration.")

    setup_secure_webhook_path() # Determine FINAL_WEBHOOK_PATH

    # --- Persistence ---
    persistence = None
    if PERSISTENCE_PATH:
        try:
            persistence_dir = os.path.dirname(PERSIST_CHAT_ID = None; LOG_FILE_PATH = None; PERSISTENCE_PATH = None
    DEVELOPMENT_MODE = False; USE_WEBHOOK = True # Assume webhook if settings fail? Or default to False? Let's default to False for safety.


# --- Import Z1-Gray Handlers (MUST EXIST or use placeholders) ---
try: from handlers.step_1 import step_one_entry
except ImportError: logger.error("CRITICAL: H1 Missing."); async def step_one_entry(u,c): await u.message.reply_text("[SYS_ERR] H1 Init Failed."); return ConversationHandler.END # type: ignore
# Import handlers for specific states - REPLACE PLACEHOLDERS
# from handlers.step_2 import handle_step_2_ack_text, handle_step_2_ack_button
# from handlers.step_4 import handle_step_4_choice_initiate, handle_step_4_choice_query
# from handlers.step_5 import handle_step_5_finalize_click, handle_step_5_text_input, handle_step_5_final_chance
async def handle_step_2_ack(u,c): logger.info("Placeholder S2 Ack"); return AWAITING_STEP_FIVE_CHOICE # type: ignore
async def handle_step_4_choice(u,c): logger.info("Placeholder S4 Choice"); await u.callback_query.answer(); return STEP_5_AWAITING_FINAL_ACTION # type: ignore
async def handle_step_5_text(u,c): logger.info("Placeholder S5 Text"); return STEP_5_AWAITING_FINAL_ACTION # type: ignore
async def handle_step_5_final_click(u,c): logger.info("Placeholder S5 Final Click"); await u.callback_query.answer(); return ConversationHandler.END # type: ignore
async def handle_step_5_final_chance(u,c): logger.info("Placeholder S5 Final Chance"); return STEP_5_FINAL_CHANCE_STATE # type: ignore

try: from handlers.unknown import handle_unknown_message, handle_unknown_command, handle_unknown_callback
except ImportError: logger.warning("Using placeholders for unknown handlers."); async def handle_unknown_message(u,c): await u.message.reply_text("[SYS] Unknown input.") # type: ignore ; async def handle_unknown_command(u,c): await u.message.reply_text("[SYS] Unknown command.")# type: ignore ; async def handle_unknown_callback(u,c): await u.callback_query.answer("Unknown.") # type: ignore

# --- Import Z1-Gray States ---
try:
    from utils.state_definitions import * # Import all defined states
    if 'STATE_NAME_MAP' not in globals(): raise ImportError("STATE_NAME_MAP missing")
except ImportError:
    logger.critical("CRITICAL: utils/state_definitions.py / STATE_NAME_MAP missing. Using fallbacks.")
    AWAITING_STEP_TWO_ACK, AWAITING_STEP_FIVE_CHOICE, STEP_5_AWAITING_FINAL_ACTION, STEP_5_FINAL_CHANCE_STATE = 0,1,2,3 # type: ignore
    STATE_NAME_MAP = {0:"S2_ACK_FB", 1:"S5_CHOICE_FB", 2:"S5_ACTION_FB", 3:"S5_FINAL_FB"} # type: ignore

# --- Global Variables ---
shutdown_event = asyncio.Event()
application: Application | None = None
FINAL_WEBHOOK_PATH = None

# --- Secure Webhook Path Generation ---
def setup_secure_webhook_path() -> None:
    global FINAL_WEBHOOK_PATH
    if not WEBHOOK_URL: return
    configured_path = CFG_WEBHOOK_PATH
    secure_prefix = "/z1_secure_"
    if configured_path and configured_path.startswith(secure_prefix):
        FINAL_WEBHOOK_PATH = configured_path
    else:
        secure_suffix = secrets.token_urlsafe(16)
        FINAL_WEBHOOK_PATH = f"/tgwh_auto_{secure_suffix}"
        logger.warning(f"Using auto-generated secure WEBHOOK_PATH: {FINAL_WEBHOOK_PATH}")
    logger.info(f"Final Webhook Path determined: {FINAL_WEBHOOK_PATH}")

# --- Signal Handler (Synchronous part for setting event) ---
def handle_signal_sync(sig, frame):
    logger.info(f"Received OS signal {sig}. Setting shutdown event.")
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(shutdown_event.set)
    except RuntimeError: # Fallback if loop isn't running or accessible
         logger.warning("Could not get running loop to set shutdown event threadsafe. Setting directly.")
         shutdown_event.set()

# --- Webhook Handler (for aiohttp) ---
async def telegram_webhook_handler(request: web.Request) -> web.Response:
    """Handles incoming webhook requests from Telegram via aiohttp."""
    global application
    if not application:
        logger.error("Webhook received but PTB Application not initialized.")
        return web.Response(status=503, text="Bot Service Unavailable")
    try:
        update_data = await request.json()
    except asyncio.CancelledError:
         raise # Propagate cancellation
    except Exception as e:
        logger.error(f"Failed to parse JSON from webhook request: {e}")
        return web.Response(status=400, text="Bad Request: Invalid JSON")

    try:
        update = Update.de_json(update_data, application.bot)
        # Use asyncio.create_task for fire-and-forget processing
        asyncio.create_task(application.process_update(update))
        return web.Response(status=200, text="OK") # Acknowledge Telegram quickly
    except asyncio.CancelledError:
        raise
    except Exception as e:
        update_id_info = update.update_id if 'update' inENCE_PATH)
            if persistence_dir and not os.path.exists(persistence_dir): os.makedirs(persistence_dir, exist_ok=True)
            persistence = PicklePersistence(filepath=PERSISTENCE_PATH)
            logger.info(f"PicklePersistence enabled: {PERSISTENCE_PATH}")
        except Exception as e: logger.error(f"Failed to init PicklePersistence: {e}. Persistence disabled.")

    # --- Build PTB Application ---
    builder = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init_hook).drop_pending_updates(True)
    if persistence: builder = builder.persistence(persistence)
    application = builder.build()

    # --- Define Z1-Gray ConversationHandler ---
    # Replace ALL placeholders below with actual imported handlers
    z1_gray_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", step_one_entry)],
        states={
            AWAITING_STEP_TWO_ACK: [
                 MessageHandler(filters.Regex(r'^(OK|Ok|ok|YES|Yes|yes)$'), handle_step_2_ack), # REPLACE placeholder
                 CallbackQueryHandler(handle_step_2_ack, pattern="^review_diagnostics_pressed$"), # REPLACE placeholder
                 MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message) # Fallback for this state
            ],
            # ... Add ALL other AWAITING_* states mapping to their SPECIFIC handlers ...
            AWAITING_STEP_FIVE_CHOICE: [
                 CallbackQueryHandler(handle_step_4_choice, pattern="^step4_initiate_sync$"), # REPLACE
                 CallbackQueryHandler(handle_step_4_choice, pattern="^step4_query_necessity$"), # REPLACE
                 MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message) # Or a specific text handler for this state
            ],
            STEP_5_AWAITING_FINAL_ACTION: [
                 CallbackQueryHandler(handle_final_sync_button, pattern="^final_sync_initiated$"), # REPLACE
                 MessageHandler(filters.TEXT & ~filters.COMMAND, handle_step5_text_input) # REPLACE
            ],
             STEP_5_FINAL_CHANCE_STATE: [
                 CallbackQueryHandler(handle_final_sync_button, pattern="^final_sync_initiated$"), # Maybe same button action?
                 MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message) # Handle text during final chance
            ],
             # STEP_5_REJECTION_WARNING_STATE: [ ... handlers ... ], # Add if implemented
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.COMMAND, handle_unknown_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message),
            CallbackQueryHandler(handle_unknown_callback)
        ],
        per_user=True,
        name="z1_gray_funnel_prod_aiohttp", # Specific name
        allow_reentry=True, # step_one_entry MUST clear user_data
        persistent=(persistence is not None),
    )
    application.add_handler(z1_gray_conv_handler)

    # Optional: Add other handlers like /help, /status outside the conversation
    # application.add_handler(CommandHandler("help", help_command_placeholder))
    # application.add_handler(CommandHandler("status", status_command_placeholder))

    # --- Start PTB & aiohttp (Webhook Mode) ---
    if USE_WEBHOOK and FULL_TELEGRAM_WEBHOOK_URL:
        logger.info("Initializing PTB application for Webhook mode...")
        await application.initialize()
        logger.info("Starting PTB application background tasks...")
        await application.start()
        # Set webhook *after* initialization and start
        # await post_init_hook(application) # Set webhook now done via post_init

        logger.info("Setting up aiohttp web server...")
        aiohttp_app = web.Application()
        aiohttp_app.router.add_post(FINAL_WEBHOOK_PATH, telegram_webhook_handler)
        runner = web.AppRunner(aiohttp_app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=PORT)

        try:
            await site.start()
            logger.info(f"✅ aiohttp Webhook server started successfully on 0.0.0.0:{PORT}")
            await shutdown_event.wait() # Keep running until signal
        except Exception as e:
            logger.critical(f"Error starting/running aiohttp server: {e}", exc_info=True)
        finally:
            logger.info("Shutting down aiohttp server...")
            await site.stop()
            await runner.cleanup()
            logger.info("aiohttp server shut down.")
    else:
        # --- Start Polling (Development Mode) ---
        logger.info("Starting bot in POLLING mode...")
        # allowed_updates defined earlier
        await application.run_polling(allowed_updates=allowed_updates, stop_signals=[]) # Use custom signal handling

    # --- Final PTB Shutdown ---
    logger.info("Initiating final PTB application shutdown...")
    if hasattr(application, 'running') and application.running: await application.stop()
    await application.shutdown()
    logger.info("PTB application shut down.")

# === Program Entry Point ===
if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal_sync)
    signal.signal(signal.SIGTERM, handle_signal_sync)
    logger.info("Z1-Gray Bot (aiohttp webhook integrated) Bootstrapping...")
    try:
        asyncio.run(run_bot())
    except RuntimeError as e: logger.critical(f"Runtime Error: {e}. Execution halted.") ; sys.exit(1)
    except (KeyboardInterrupt, SystemExit): logger.info("Process terminated by user/system signal.")
    except Exception as e: logger.critical(f"FATAL UNHANDLED EXCEPTION: {e}", exc_info=True) ; sys.exit(1)
    finally: logger.info("Z1-Gray Bot execution cycle concluded.")