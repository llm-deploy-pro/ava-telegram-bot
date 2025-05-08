# handlers/step_4.py

import asyncio
import logging
import time
from telegram import Update, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import TelegramError

# Assuming imports from project structure are correct
from templates.messages_en import (
    STEP_4_MSG_1_CAPACITY_AND_WINDOW,
    STEP_4_MSG_2_RISK_AND_DISQUALIFICATION,
    STEP_4_PROMPT_FOR_USER_CHOICE, # Template should include {assigned_slot_id} placeholder
    BTN_TEXT_SECURE_NODE,
    BTN_TEXT_QUERY_NECESSITY,
    STEP_4_WINDOW_EXPIRED_NOTICE # New template for expiration
)
from utils.state_definitions import AWAITING_STEP_FIVE_CHOICE
from utils.button_utils import build_dual_button_keyboard
from utils.helpers import get_formatted_time_left # Assumes this handles remaining time and expired state

logger = logging.getLogger(__name__)

# Placeholder for the new expiration message template
STEP_4_WINDOW_EXPIRED_NOTICE = (
    "⏳ `[SYSTEM_ALERT // PROTOCOL_WINDOW_EXPIRED]`\n"
    "`The validity window for ENTRY_SYNC_49 activation associated with your ACCESS_KEY ({secure_id}) has closed.`\n"
    "`Node disqualification process initiated.`\n"
    "▶ `To attempt a new access protocol sequence, please use /start.`"
)

# This function is intended to be called by context.job_queue.run_once, scheduled by Step 3's logic handler
async def start_step_four_automation_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Job callback: Sends Step ④'s automated messages (ACCESS LOCK & Urgency)
    and concludes with the user choice prompt + buttons, if the window is still active.
    Leads to AWAITING_STEP_FIVE_CHOICE state (set by the calling handler).
    """
    job_context = context.job.data if context.job else {}
    chat_id = job_context.get("chat_id")
    user_id = job_context.get("user_id")
    # Get data potentially stored by Step 1 or 3
    user_data = context.application.user_data.get(user_id, {})
    secure_id = user_data.get("secure_id") # Essential from Step 1
    assigned_slot_id = user_data.get("assigned_slot_id", "N/A") # Get anchor from Step 3 data
    countdown_start_ts = user_data.get("step_4_countdown_start") # Essential from Step 3 job data/user_data
    total_duration_sec = user_data.get("step_4_total_duration") # Essential from Step 3 job data/user_data
    remaining_slots = user_data.get("step_4_initial_slots", 3) # Initial slots

    # Robust check for essential data needed to proceed
    if not all([chat_id, user_id, secure_id, countdown_start_ts, total_duration_sec]):
        logger.critical(
            f"[Step ④ Job] CRITICAL data missing. "
            f"chat_id={chat_id}, user_id={user_id}, secure_id={secure_id}, "
            f"start_ts={countdown_start_ts}, duration={total_duration_sec}. Aborting job."
        )
        if chat_id:
             try: await context.bot.send_message(chat_id, text="`[SYS_ERR // SESSION_DATA_INCONSISTENT]` Critical error. Please restart: /start.")
             except Exception as e: logger.error(f"Failed to send critical data error msg to {chat_id}: {e}")
        return

    log_prefix = f"[Step ④ Sequence] User {user_id} (SecureID: {secure_id}, SlotID: {assigned_slot_id}): "
    logger.info(f"{log_prefix}Starting ACCESS LOCK sequence.")

    sequence_failed = False # Flag for error handling

    try:
        # --- Check Timer FIRST ---
        # ✅ Item 3 (from review): Handle expired window before sending messages
        current_ts = time.time()
        is_expired, time_left_formatted_msg1 = get_formatted_time_left(countdown_start_ts, total_duration_sec, current_ts)

        if is_expired:
            logger.warning(f"{log_prefix}Protocol window expired before sending Step 4 Message 1. Sending expiration notice.")
            await context.bot.send_message(
                chat_id=chat_id,
                text=STEP_4_WINDOW_EXPIRED_NOTICE.format(secure_id=secure_id),
                parse_mode=ParseMode.MARKDOWN
            )
            # Mark state potentially for cleanup? Or just let CH timeout/cancel handle?
            user_data["step_4_window_expired"] = True
            return # End the job, no further messages or buttons needed

        # --- Send Step ④ Messages ---

        # Message 1 – Lock warning + remaining slots + CURRENT remaining time
        logger.debug(f"{log_prefix}Sending CAPACITY_AND_WINDOW... Slots: {remaining_slots}, Time Left: {time_left_formatted_msg1}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=STEP_4_MSG_1_CAPACITY_AND_WINDOW.format(
                remaining_slots=remaining_slots,
                time_left_formatted=time_left_formatted_msg1
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(2.8) # Internal delay

        # Message 2 – Disqualification escalation
        logger.debug(f"{log_prefix}Sending RISK_AND_DISQUALIFICATION...")
        await context.bot.send_message(
            chat_id=chat_id,
            text=STEP_4_MSG_2_RISK_AND_DISQUALIFICATION,
            parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(2.0) # Internal delay

        # Final Prompt – CTA buttons + CURRENT remaining time + Slot ID Anchor
        # ✅ Item 1 Fix: Recalculate time and include assigned_slot_id
        current_ts_prompt = time.time()
        is_expired_prompt, time_left_formatted_prompt = get_formatted_time_left(countdown_start_ts, total_duration_sec, current_ts_prompt)

        if is_expired_prompt:
             logger.warning(f"{log_prefix}Protocol window expired just before sending Step 4 Prompt. Sending expiration notice.")
             await context.bot.send_message(
                 chat_id=chat_id,
                 text=STEP_4_WINDOW_EXPIRED_NOTICE.format(secure_id=secure_id),
                 parse_mode=ParseMode.MARKDOWN
             )
             user_data["step_4_window_expired"] = True
             return # End the job

        logger.debug(f"{log_prefix}Sending PROMPT_FOR_USER_CHOICE with buttons. Time Left: {time_left_formatted_prompt}, SlotID: {assigned_slot_id}")
        # ✅ Item 2 Fix: Using clearer, unified callback data names
        keyboard = InlineKeyboardMarkup(
            build_dual_button_keyboard(
                button1_text=BTN_TEXT_SECURE_NODE,
                button1_callback="step4_initiate_sync", # Clearer callback data
                button2_text=BTN_TEXT_QUERY_NECESSITY,
                button2_callback="step4_query_necessity" # Clearer callback data
            )
        )

        # Assume STEP_4_PROMPT_FOR_USER_CHOICE template includes {assigned_slot_id}
        prompt_text = STEP_4_PROMPT_FOR_USER_CHOICE.format(
            secure_id=secure_id,
            time_left_formatted=time_left_formatted_prompt,
            assigned_slot_id=assigned_slot_id # ✅ Item 1 Fix: Pass slot ID
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text=prompt_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

        # State management confirmation (managed by the handler that scheduled this job)
        logger.info(f"{log_prefix}Step ④ automated sequence and prompt sent successfully. Awaiting user choice in state AWAITING_STEP_FIVE_CHOICE.")

    except TelegramError as te:
        sequence_failed = True
        logger.error(f"{log_prefix}TelegramError during Step ④ sequence: {te}", exc_info=False)
        user_data["step_4_failed"] = True
        user_data["step_4_failure_reason"] = f"TelegramError: {te}"
    except Exception as e:
        sequence_failed = True
        logger.error(f"{log_prefix}Unexpected error during Step ④ sequence: {e}", exc_info=True)
        user_data["step_4_failed"] = True
        user_data["step_4_failure_reason"] = f"Exception: {e}"

    finally:
        if sequence_failed:
            logger.warning(f"{log_prefix}Step ④ sequence failed to complete fully.")
            # Attempt to notify the user (best effort)
            try:
                error_message = (
                    "`[SYSTEM_ERROR // ACCESS_LOCK_SEQUENCE_FAILURE]`\n"
                    "`An internal error prevented the sync window update. Protocol integrity compromised.`\n"
                    "`Please type /start to re-establish a secure session.`"
                )
                await context.bot.send_message(chat_id=chat_id, text=error_message, parse_mode=ParseMode.MARKDOWN)
                logger.info(f"{log_prefix}Sent Step ④ failure notification to user.")
            except Exception as notify_error:
                logger.critical(f"{log_prefix}Failed to send Step ④ failure notification: {notify_error}")
            # User is likely left in AWAITING_STEP_FIVE_CHOICE state but with a failure flag.

# Note: Handlers for callback_data 'step4_initiate_sync' and 'step4_query_necessity'
# need to be implemented (likely in handlers/step_5.py or user_input_handler.py)
# and registered in main.py for the AWAITING_STEP_FIVE_CHOICE state.
# These handlers should check for the 'step_4_failed' and 'step_4_window_expired' flags
# in context.user_data before proceeding.
