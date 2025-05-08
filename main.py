#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
import os
import signal
import sys # For sys.exit()

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    PicklePersistence, # Added for optional persistence
)
from telegram.error import InvalidToken, BadRequest
from dotenv import load_dotenv
from aiohttp import web # Ensure this is imported

# --- 配置 Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING) # aiohttp access logs
logging.getLogger("telegram.ext").setLevel(logging.INFO) # PTB's own logging
logger = logging.getLogger(__name__)

# --- 加载环境变量 ---
load_dotenv() # 本地开发时加载 .env 文件

# --- 从环境变量获取配置 ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL_BASE = os.getenv("WEBHOOK_URL") # Render 会提供基础 URL, e.g., https://your-app.onrender.com
PORT = int(os.getenv("PORT", "8080")) # Render 会注入 PORT, default if not found
# Use the path provided in your snippet for aiohttp router and Telegram webhook.
FINAL_WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook") # Defaulting to /webhook as in your snippet

# --- 启动前检查 ---
if not BOT_TOKEN:
    logger.critical("FATAL: BOT_TOKEN environment variable not found.")
    sys.exit(1)
# WEBHOOK_URL_BASE is critical for webhook mode
if not WEBHOOK_URL_BASE:
    logger.critical("FATAL: WEBHOOK_URL_BASE environment variable not found.")
    sys.exit(1)

# --- 构建完整的 Webhook URL ---
# This will be used to tell Telegram where to send updates.
FULL_TELEGRAM_WEBHOOK_URL = f"{WEBHOOK_URL_BASE.rstrip('/')}{FINAL_WEBHOOK_PATH}"

logger.info(f"BOT_TOKEN loaded (partially hidden): {BOT_TOKEN[:5]}...{BOT_TOKEN[-4:]}")
logger.info(f"Base WEBHOOK_URL_BASE from env: {WEBHOOK_URL_BASE}")
logger.info(f"Final Webhook Path for aiohttp and Telegram: {FINAL_WEBHOOK_PATH}")
logger.info(f"Full URL to register with Telegram: {FULL_TELEGRAM_WEBHOOK_URL}")
logger.info(f"aiohttp server will listen on 0.0.0.0:{PORT}")


# --- (可选) 初始化 Persistence ---
# persistence = PicklePersistence(filepath="ava_bot_data.pkl")
# logger.info("PicklePersistence initialized. Bot state will be saved to ava_bot_data.pkl")

# --- 全局变量 ---
shutdown_event = asyncio.Event()
application: Application | None = None # PTB Application instance

# --- 对话状态常量 (Z1-灰 脚本阶段, from your snippet) ---
(
    CONFIRM_START,
    AWAIT_Q1_RESPONSE,
    AWAIT_Q2_RESPONSE,
    AWAIT_DIAGNOSIS_ACK,
    AWAIT_URGENCY_ACK,
    AWAIT_PAYMENT_PROMPT_ACK
) = range(6)

# === Z1-灰 Conversation Handlers (Copied from your snippet) ===
# ... (所有对话处理函数: start_conversation, handle_confirmation, etc. 保持不变) ...
async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    name = user.first_name if user else "User"
    logger.info(f"User {user.id} started the conversation.")
    context.user_data.pop("reached_phase5", None)
    context.user_data.pop("upgrade_used", None)
    emo_node_id = user.id % 10000
    text = (
        f"💫 Welcome, {name}, to the EmoSync Protocol.\n\n"
        f"I've detected your signal entering our resonance analysis system. Channel ID #U-{emo_node_id:04d} initializing...\n\n"
        f"[Running emotional sync handshake...]\n"
        f"[Calibrating baseline frequencies...]\n\n"
        f"✅ My sensors have locked onto your emotional signal node.\n\n"
        f"🧠 To proceed with the calibration and receive your live sync snapshot, please confirm you are ready."
        f"\n\n👉 Reply with **Yes** to continue."
    )
    try:
        await update.message.reply_text(text)
        return CONFIRM_START
    except Exception as e:
        logger.error(f"Error in start_conversation for user {user.id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ System error initiating contact. Please try /start again later.")
        except Exception:
            logger.error(f"Failed to send error message in start_conversation for user {user.id}")
        return ConversationHandler.END

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    logger.info(f"User {user_id} confirmed start in CONFIRM_START state.")
    text = (
        "🧠 Initial interface confirmed.\n"
        "Let’s begin your reactive diagnostic phase...\n\n"
        "💡 **Question 1:**\n"
        "When you feel emotional distance from someone important, your primary reaction is usually:\n"
        "A) Withdraw quietly, needing space\n"
        "B) Overcompensate, seeking reassurance or attention\n"
        "C) Say nothing externally, but feel significant internal frustration or resentment\n\n"
        "Please reply with **A**, **B**, or **C**."
    )
    try:
        await update.message.reply_text(text)
        return AWAIT_Q1_RESPONSE
    except Exception as e:
        logger.error(f"Error sending Q1 to user {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ System error during diagnostic initiation. Please use /cancel to exit.")
        except Exception:
             logger.error(f"Failed to send error message in handle_confirmation for user {user_id}")
        return ConversationHandler.END

async def handle_q1_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_input = update.message.text.strip().upper()
    logger.info(f"User {user_id} in AWAIT_Q1_RESPONSE state, replied: {user_input}")
    pseudo_analysis = ""
    if user_input == 'A':
        pseudo_analysis = "🟡 Detecting: Potential signal decay pattern under pressure… withdrawal signature noted."
    elif user_input == 'B':
        pseudo_analysis = "🟡 Detecting: Attraction loop overcompensation signature… energy spike indicates potential instability."
    elif user_input == 'C':
        pseudo_analysis = "🟡 Detecting: Internal conflict signature… resonance dissonance observed between external projection and internal state."
    text_part1 = (
        f"{pseudo_analysis}\n\n"
        f"[Running micro-loop pattern overlay...]\n"
        f"[Potential detected: signal misfire risk – latency in expected response cycle]\n\n"
        "Let's refine the vector..."
    )
    text_part2 = (
        "💡 **Question 2:**\n"
        "Do you believe your core emotional needs should be intuitively understood by those closest to you, often without explicit verbal communication?\n\n"
        "Please reply with **Yes** or **No**."
    )
    try:
        await update.message.reply_text(text_part1)
        await asyncio.sleep(1.5)
        await update.message.reply_text(text_part2)
        return AWAIT_Q2_RESPONSE
    except Exception as e:
        logger.error(f"Error sending pseudo-analysis and Q2 to user {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ System error during analysis phase. Please use /cancel to exit.")
        except Exception:
             logger.error(f"Failed to send error message in handle_q1_response for user {user_id}")
        return ConversationHandler.END

async def handle_q2_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_input = update.message.text.strip().lower()
    logger.info(f"User {user_id} in AWAIT_Q2_RESPONSE state, replied: {user_input}")
    risk_term = "Empathy Pathway Expectation Mismatch" if user_input == 'yes' else "Implicit Communication Channel Deficiency"
    interference_term = "Attraction Frequency Interference Risk"
    text_part1 = (
        f"⚠️ Response logged.\n"
        f"System analysis indicates: **{risk_term} combined with {interference_term}.**\n\n"
        f"[Preliminary instability factors confirmed... Compiling EmoSync Snapshot...]"
    )
    emo_node_id = user_id % 10000
    latency_val = 10 + (user_id % 100) / 10.0
    text_part2 = (
        f"🧪 **Ava Sync Snapshot — EMO Node #{emo_node_id:04d}**\n"
        "━━━━━━━━━━━━━\n"
        "• **Spectrum Resonance:** ⚠️ *Significantly Disrupted*\n"
        "• **Attraction Pulse Strength:** 🔻 *Sub-Optimal / Fluctuating*\n"
        f"• **Sync Latency Index:** ⏳ *{latency_val:.1f}s (Critically High)*\n"
        "• **Trust Signal Field Integrity:** 🔒 *Compromised (Tier 0 lock-in detected)*\n"
        "━━━━━━━━━━━━━\n\n"
        "🚨 **Critical Warning:** Your current operational mode exists within **unsynced emotional channels**. My projections show a high probability (>85%) of this pattern leading to chronic misalignment, severe trust distortion, and recurring attraction mechanism breakdowns.\n\n"
        "⚠️ **Immediate calibration protocol initiation is strongly advised.** Delay risks irreversible emotional drift and pattern solidification."
    )
    try:
        await update.message.reply_text(text_part1)
        await asyncio.sleep(2.0)
        await update.message.reply_text(text_part2)
        return AWAIT_DIAGNOSIS_ACK
    except Exception as e:
        logger.error(f"Error sending diagnosis to user {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ System error generating diagnostic report. Please use /cancel to exit.")
        except Exception:
             logger.error(f"Failed to send error message in handle_q2_response for user {user_id}")
        return ConversationHandler.END

async def handle_diagnosis_ack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_input = update.message.text
    logger.info(f"User {user_id} in AWAIT_DIAGNOSIS_ACK state, acknowledged diagnosis with: {user_input[:50]}...")
    emo_node_id = user_id % 10000
    fake_slot_meter = "Slots Remaining: [🟩🟩🟩🟧🟥🟥🟥🟥🟥]"
    text = (
        "⏱️ **ACTION REQUIRED: Your temporary access slot for EmoSync recalibration protocol (SAP-1) is now ACTIVE.**\n\n"
        "🟡 **System Alert:** Only **9** calibration activation keys remain available in the current allocation cycle due to high demand.\n"
        f"{fake_slot_meter}\n"
        "⏳ **Time Window:** This calibration window will automatically close in **4 minutes and 38 seconds**.\n\n"
        "⛔ **Consequences of Inaction:**\n"
        "   – Loss of priority sync rights for this cycle.\n"
        f"   – Your diagnostic data (#U-{emo_node_id:04d}) will be automatically purged from the active queue.\n"
        "   – Full system re-entry audit and recalibration fee will be required for future access.\n\n"
        "This is your **final pre-calibration opportunity** within this window. The system will not issue further prompts."
    ).format(emo_node_id=emo_node_id)
    try:
        await update.message.reply_text(text)
        return AWAIT_URGENCY_ACK
    except Exception as e:
        logger.error(f"Error sending urgency message to user {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ System error proceeding to activation phase. Please use /cancel to exit.")
        except Exception:
            logger.error(f"Failed to send error message in handle_diagnosis_ack for user {user_id}")
        return ConversationHandler.END

async def handle_urgency_ack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_input = update.message.text
    logger.info(f"User {user_id} in AWAIT_URGENCY_ACK state, acknowledged urgency with: {user_input[:50]}...")
    text = (
        "🔐 **To secure your calibration slot and initiate the EmoSync Structural Adjustment Protocol (SAP-1), a one-time calibration token activation is mandatory.**\n\n"
        "This token grants access to the foundational recalibration layer required based on your diagnostic snapshot.\n\n"
        "💸 **Activation Token Cost:** **$49 USD**\n\n"
        "This covers immediate access to:\n"
        "   – 🎓 Your personalized EmoSync Blueprint (Core Diagnostics PDF)\n"
        "   – 🧠 The 1-minute SAP-1 Diagnostic Interpretation Video Guide\n"
        "   – 🔑 Your unique Tier 1 Memory Unlock Key for the protocol.\n\n"
        "This is the **minimum system requirement** for all candidates selected for potential sync alignment.\n\n"
        "👉 **Please type `/upgrade` now to proceed with the activation.**\n\n"
        "Your EmoSync session status will remain 'Pending Calibration' and your slot unsecured until activation payment is verified by the system.\n"
        "⏳ *Time remaining in window is critical.*"
    )
    try:
        await update.message.reply_text(text)
        context.user_data["reached_phase5"] = True
        logger.info(f"User {user_id} reached phase 5. Flag 'reached_phase5' set.")
        return AWAIT_PAYMENT_PROMPT_ACK
    except Exception as e:
        logger.error(f"Error sending payment prompt to user {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ System error presenting activation requirements. Please use /cancel to exit.")
        except Exception:
            logger.error(f"Failed to send error message in handle_urgency_ack for user {user_id}")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info(f"User {user.id} canceled the conversation.")
    context.user_data.pop("reached_phase5", None)
    context.user_data.pop("upgrade_used", None)
    state = ConversationHandler.END
    try:
        await update.message.reply_text(
            "🛑 EmoSync Protocol calibration sequence aborted by user command. "
            "Your current session data has been purged. "
            "You may restart the process later using /start.",
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f"Error sending cancellation message to user {user.id}: {e}", exc_info=True)
    return state

async def handle_invalid_conversation_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else 'Unknown'
    logger.warning(f"[Fallback] User {user_id} sent unexpected input in conversation.")
    try:
        await update.message.reply_text(
            "⚠️ Ava only understands specific responses at this stage. "
            "Please follow the instructions or type /cancel to exit."
        )
    except Exception as e:
        logger.error(f"Error sending fallback message to user {user_id}: {e}", exc_info=True)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🛠 **EmoSync Protocol Help**\n"
        "Type /start to initiate or restart the emotional sync calibration sequence.\n"
        "During the sequence, follow the prompts carefully.\n"
        "Type /cancel at any time to abort the current sequence.\n"
        "Type /upgrade *only* after reaching the final activation step."
    )
    try:
        await update.message.reply_text(text)
        logger.info(f"Sent help message to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Failed to send help message: {e}", exc_info=True)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = "🧠 Ava Status: System Online | Protocol Ready | Calibration Inactive."
    try:
        await update.message.reply_text(text)
        logger.info(f"Sent status message to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Failed to send status message: {e}", exc_info=True)

async def upgrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    user_id = update.effective_user.id if update.effective_user else 'Unknown'
    state = ConversationHandler.END
    if context.user_data.get("upgrade_used", False):
        logger.warning(f"User {user_id} attempted repeated /upgrade after usage.")
        try:
            await update.message.reply_text(
                "⚠️ This upgrade path has already been used. Please use /start to initiate a new sync."
            )
        except Exception as e:
            logger.error(f"Error sending repeated upgrade rejection message to user {user_id}: {e}", exc_info=True)
        return None
    if not context.user_data.get("reached_phase5", False):
        logger.warning(f"User {user_id} attempted /upgrade without reaching phase 5.")
        try:
            await update.message.reply_text(
                "⚠️ You must complete the calibration sequence before activating your token. Please use /start to begin."
            )
        except Exception as e:
            logger.error(f"Error sending upgrade rejection message to user {user_id}: {e}", exc_info=True)
        return None
    logger.info(f"User {user_id} used /upgrade command (verified access).")
    text = (
        "Processing your activation request...\n\n"
        "🔒 Your emotional sync is currently locked.\n"
        "To unlock Ava’s deeper emotional modules and activate SAP-1, confirm your **$49 USD** calibration token purchase 🔓\n\n"
        "👉 **Visit your secure activation portal:** https://bit.ly/lovewithava\n\n" # Replace with your actual link
        "Once payment is verified, your EmoSync Blueprint and video guide will be accessible.\n\n"
        "✅ You may now restart the sequence using /start."
    )
    try:
        await update.message.reply_text(text)
        context.user_data.pop("reached_phase5", None)
        context.user_data["upgrade_used"] = True
        logger.info(f"Upgrade link sent to user {user_id}. Conversation ended via /upgrade.")
    except Exception as e:
        logger.error(f"Failed to send upgrade message/link to user {user_id}: {e}", exc_info=True)
    return state
# === End of Handlers ===


# === Webhook Handler (for aiohttp) ===
async def telegram_webhook_handler(request: web.Request) -> web.Response:
    """Handle webhook POST requests from Telegram."""
    global application # Use the global application instance
    if not application:
        logger.error("PTB Application not initialized when webhook received.")
        return web.Response(status=503, text="Bot not ready")
    try:
        update_data = await request.json()
        update = Update.de_json(update_data, application.bot)
        logger.debug(f"Webhook received update: {update.update_id}")
        # Process update in the background to avoid blocking the webhook response
        asyncio.create_task(application.process_update(update))
        # Acknowledge Telegram immediately
        return web.Response(status=200, text="OK")
    except Exception as e:
        update_id_info = "N/A"
        if 'update' in locals() and hasattr(update, 'update_id'):
            update_id_info = update.update_id
        logger.error(f"Error processing webhook update {update_id_info}: {e}", exc_info=True)
        return web.Response(status=500, text="Error processing update")

# === Signal Handler (Synchronous part) ===
def handle_signal_sync(sig, frame):
    """Sets the shutdown_event when an OS signal is received."""
    logger.info(f"Received OS signal {signal.Signals(sig).name}. Setting shutdown event.")
    # Use get_event_loop_policy().get_event_loop() for safety if called before loop is running
    loop = asyncio.get_event_loop_policy().get_event_loop()
    if loop.is_running():
        loop.call_soon_threadsafe(shutdown_event.set)
    else:
        logger.warning("Event loop was not running when signal received. Setting event directly (might not be awaited).")
        shutdown_event.set()


# === Main Application Logic ===
async def run_bot() -> None:
    """Initializes PTB, sets webhook, and runs the manual aiohttp server."""
    global application # Allow assignment to global variable

    logger.info("Starting Bot (Webhook Mode - Manual aiohttp Integration)...")

    # --- Build ConversationHandler ---
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_conversation)],
        states={
            CONFIRM_START:        [MessageHandler(filters.Regex(r'^(Yes|yes)$'), handle_confirmation)],
            AWAIT_Q1_RESPONSE:    [MessageHandler(filters.Regex(r'^(A|B|C|a|b|c)$'), handle_q1_response)],
            AWAIT_Q2_RESPONSE:    [MessageHandler(filters.Regex(r'^(Yes|No|yes|no)$'), handle_q2_response)],
            AWAIT_DIAGNOSIS_ACK:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_diagnosis_ack)],
            AWAIT_URGENCY_ACK:    [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_urgency_ack)],
            AWAIT_PAYMENT_PROMPT_ACK: [ CommandHandler("upgrade", upgrade_command) ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("upgrade", upgrade_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invalid_conversation_input),
            MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.TEXT, handle_invalid_conversation_input)
        ],
        conversation_timeout=600,
        per_user=True,
    )

    # --- Build PTB Application ---
    # persistence_obj = PicklePersistence(filepath="ava_bot_data.pkl") # Uncomment if using
    builder = ApplicationBuilder().token(BOT_TOKEN)
    # builder = builder.persistence(persistence_obj) # Uncomment if using
    application = builder.build()

    # --- Register Handlers ---
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    logger.info("PTB Application built with handlers.")

    # --- PTB Application Lifecycle: Initialize & Start ---
    # Prepare PTB to process updates. Does NOT start networking.
    try:
        await application.initialize()
        logger.info("PTB Application initialized.")
        await application.start()
        logger.info("PTB Application started (background components).")
    except Exception as e:
        logger.critical(f"Failed to initialize or start PTB Application: {e}", exc_info=True)
        shutdown_event.set() # Signal shutdown if PTB fails
        return

    # --- Set Webhook with Telegram ---
    # It's crucial this happens AFTER application.initialize() and BEFORE aiohttp starts
    try:
        logger.info(f"Attempting to set webhook with Telegram: {FULL_TELEGRAM_WEBHOOK_URL}")
        # Ensure allowed_updates covers all types your handlers might need
        await application.bot.set_webhook(
            url=FULL_TELEGRAM_WEBHOOK_URL,
            allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY] # Example
        )
        webhook_info = await application.bot.get_webhook_info()
        if webhook_info.url == FULL_TELEGRAM_WEBHOOK_URL:
            logger.info(f"Webhook successfully set/confirmed with Telegram: {webhook_info.url}")
        else:
            logger.error(f"Webhook URL mismatch after setting! Expected: {FULL_TELEGRAM_WEBHOOK_URL}, Got: {webhook_info.url if webhook_info else 'None'}. Check base URL and path.")
            # Consider if this should be fatal; depends on deployment. Logging error and continuing.
    except Exception as e:
        logger.critical(f"CRITICAL: Failed to set webhook with Telegram: {e}", exc_info=True)
        shutdown_event.set() # Signal shutdown
        return

    # --- Setup and Run Manual aiohttp Server ---
    # ❌ REMOVED: await application.run_webhook(...)
    # ✅ ADDED: Manual aiohttp setup starts here
    aiohttp_app = web.Application()
    # The router path *must* match FINAL_WEBHOOK_PATH used in FULL_TELEGRAM_WEBHOOK_URL
    aiohttp_app.router.add_post(FINAL_WEBHOOK_PATH, telegram_webhook_handler)
    logger.info(f"aiohttp router configured for POST requests on path: {FINAL_WEBHOOK_PATH}")

    runner = web.AppRunner(aiohttp_app)
    await runner.setup()
    # Listen on 0.0.0.0 for external connections (like Render's proxy)
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)

    try:
        await site.start() # Start the aiohttp server
        logger.info(f"✅ Webhook server (aiohttp) started successfully on 0.0.0.0:{PORT}")
        logger.info(f"Telegram should send updates to: {FULL_TELEGRAM_WEBHOOK_URL}")

        # Keep the application running until shutdown signal
        await shutdown_event.wait()
        logger.info("🔻 Shutdown signal received via event. Cleaning up...")

    except Exception as e:
        logger.critical(f"Error during aiohttp server execution: {e}", exc_info=True)
    finally:
        # --- Cleanup aiohttp server ---
        logger.info("Stopping aiohttp web server...")
        await site.stop()
        logger.info("aiohttp site stopped.")
        await runner.cleanup()
        logger.info("aiohttp runner cleaned up.")
        # PTB Application cleanup is handled in the main script's finally block

# === Program Entry Point ===
if __name__ == "__main__":
    # Register signal handlers
    try:
        signal.signal(signal.SIGINT, handle_signal_sync)
        signal.signal(signal.SIGTERM, handle_signal_sync)
    except ValueError:
        logger.warning("Could not set all OS signal handlers (may be on Windows).")
    except Exception as e:
        logger.error(f"Error setting OS signal handlers: {e}", exc_info=True)

    logger.info("Starting main asyncio event loop...")
    try:
        asyncio.run(run_bot()) # Use standard asyncio runner
    except (KeyboardInterrupt, SystemExit):
        logger.info("Process terminated by KeyboardInterrupt/SystemExit at top level.")
        # asyncio.run handles task cancellation. Signal handler sets shutdown_event.
    except RuntimeError as e:
        # Handle specific RuntimeErrors if needed
        if "Invalid BOT_TOKEN" in str(e):
            logger.debug("Top level caught known BOT_TOKEN RuntimeError.")
        elif "Event loop is closed" in str(e) or "cannot schedule" in str(e):
             logger.warning(f"Known asyncio RuntimeError during shutdown: {e}")
        else:
             logger.critical(f"Unhandled RuntimeError at top level: {e}", exc_info=True)
             sys.exit(1)
    except Exception as e:
        logger.critical(f"FATAL UNHANDLED EXCEPTION at top level: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Final cleanup attempt for PTB Application
        if application:
            logger.info("Performing final PTB Application cleanup...")
            # This runs after asyncio.run completes. Running async cleanup is best-effort.
            if hasattr(application, 'shutdown') and getattr(application, '_initialized', False):
                try:
                    # Try to run shutdown with a new temporary loop if main one is closed
                    asyncio.run(application.shutdown())
                    logger.info("PTB Application shutdown completed in final cleanup.")
                except RuntimeError as e: # Handle cases where loop is closed/can't run
                     logger.warning(f"Could not run async PTB shutdown in final cleanup (loop state: {e}). Resources might not be fully released.")
                except Exception as e:
                     logger.error(f"Error during final PTB application shutdown: {e}", exc_info=True)
            else:
                 logger.info("PTB Application was not initialized or doesn't need shutdown.")
        logger.info("Script execution finished.")