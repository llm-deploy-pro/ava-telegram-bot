# handlers/step_3.py

import asyncio
import logging
import time
import secrets # For pseudo Slot ID generation
from datetime import timedelta # For scheduling Step 4 job

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler # Import CH for END constant if needed
from telegram.constants import ParseMode
from telegram.error import TelegramError

# Assuming imports from project structure are correct
from templates.messages_en import (
    STEP_3_MSG_1_ANALYSIS_COMPLETE,
    STEP_3_MSG_2_CORE_ISSUES,
    STEP_3_MSG_3_RECOMMENDATION_AND_SCARCITY,
    STEP_3_MSG_EXPLANATION_BRIDGE, # Explanatory bridge message
    # STEP_3_TRANSITION_TO_STEP_4, # Optional transition message (handle scheduling if used)
    FALLBACK_CTA_TEXT_STEP_4_FAILED, # Fallback message if Step 4 job fails schedule
    BTN_TEXT_FALLBACK_REENGAGE_SYNC # Fallback button text
)
# Assuming state_definitions contains the necessary states
from utils.state_definitions import AWAITING_STEP_FIVE_CHOICE # The target state after Step 4 automation completes

# Assuming button_utils has the required function for fallback button
from utils.button_utils import build_single_button_keyboard

# Assuming helpers has the necessary functions
from utils.helpers import get_remaining_slots, estimate_validity_window, get_current_timestamp

# Import the function that will start Step 4's sequence (will be called by job_queue)
try:
    from handlers.step_4 import start_step_four_automation_job
except ImportError:
    async def start_step_four_automation_job(context: ContextTypes.DEFAULT_TYPE): # type: ignore
        job_context = context.job.data if context.job else {}
        chat_id = job_context.get("chat_id")
        user_id = job_context.get("user_id")
        logger.error(
            f"[Step 3 Job] CRITICAL_PLACEHOLDER: start_step_four_automation_job is MISSING in handlers/step_4.py. "
            f"Cannot automatically proceed to Step 4 for user {user_id}, chat {chat_id}."
        )
        if chat_id:
            try:
                await context.bot.send_message(chat_id, text="`[SYSTEM_NOTICE] Protocol sequence halted due to module error. Please contact support or try /start later.`")
            except Exception as e:
                logger.error(f"Failed to send Step 4 missing error msg to {chat_id}: {e}")
    logger.warning("handlers.step_4.py or start_step_four_automation_job not found. Using placeholder.")

logger = logging.getLogger(__name__)

def _generate_pseudo_slot_id():
    return f"Z1S-{secrets.token_hex(3).upper()}"

async def start_step_three_automation_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_context = context.job.data if context.job else {}
    chat_id = job_context.get("chat_id")
    user_id = job_context.get("user_id")

    user_data = context.application.user_data.get(user_id, {})
    secure_id = user_data.get("secure_id")
    variance_value = user_data.get("variance_value", "0.83")

    if not chat_id or not user_id or not secure_id:
        logger.error(f"[Step ③ Job] Missing critical data for execution. "
                     f"chat_id={chat_id}, user_id={user_id}, secure_id={secure_id}. Aborting job.")
        user_data["step_3_failed"] = True
        user_data["step_3_failure_reason"] = "Missing Initial Context in Job"
        return

    log_prefix = f"[Step ③ Sequence] User {user_id} (SecureID: {secure_id}): "
    logger.info(f"{log_prefix}Job started to send DIAGNOSIS RESULT.")

    sequence_failed = False
    step_4_job_successfully_scheduled = False

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=STEP_3_MSG_1_ANALYSIS_COMPLETE.format(secure_id=secure_id),
            parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(3.0)

        await context.bot.send_message(
            chat_id=chat_id,
            text=STEP_3_MSG_2_CORE_ISSUES,
            parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(3.5)

        available_slots = get_remaining_slots()
        total_window_seconds = 434
        estimated_window_time_str = estimate_validity_window(seconds=total_window_seconds)
        countdown_start_timestamp = get_current_timestamp()
        pseudo_slot_id = _generate_pseudo_slot_id()

        user_data["step_4_countdown_start"] = countdown_start_timestamp
        user_data["step_4_total_duration"] = total_window_seconds
        user_data["step_4_initial_slots"] = available_slots
        user_data["assigned_slot_id"] = pseudo_slot_id

        message_3_text = STEP_3_MSG_3_RECOMMENDATION_AND_SCARCITY.format(
                available_slots=available_slots,
                estimated_window_time=estimated_window_time_str
            ) + f"\n`ASSIGNED_SLOT_ID: {pseudo_slot_id}`"

        await context.bot.send_message(
            chat_id=chat_id,
            text=message_3_text,
            parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(1.5)

        logger.debug(f"{log_prefix}Sending EXPLANATION_BRIDGE...")
        if STEP_3_MSG_EXPLANATION_BRIDGE:
            explanation_text = STEP_3_MSG_EXPLANATION_BRIDGE.format(variance_value=variance_value)
            await context.bot.send_message(
                chat_id=chat_id,
                text=explanation_text,
                parse_mode=ParseMode.MARKDOWN
            )
            await asyncio.sleep(2.5)
        else:
            logger.warning(f"{log_prefix}STEP_3_MSG_EXPLANATION_BRIDGE template missing.")
            await asyncio.sleep(1.0)

        inter_step_delay_3_to_4 = 3.0

        if hasattr(context, "job_queue") and context.job_queue:
            job_data_for_step_4 = {
                "chat_id": chat_id,
                "user_id": user_id,
            }
            context.job_queue.run_once(
                start_step_four_automation_job,
                when=timedelta(seconds=inter_step_delay_3_to_4),
                data=job_data_for_step_4,
                name=f"step_4_start_{chat_id}_{int(time.time())}"
            )
            step_4_job_successfully_scheduled = True
            logger.info(f"{log_prefix}Step ③ messages sent. Scheduled Step ④ job successfully.")
        else:
            logger.error(f"{log_prefix}CRITICAL: JobQueue not available on context. Cannot schedule Step ④ automation.")
            sequence_failed = True

    except TelegramError as te:
        sequence_failed = True
        logger.error(f"{log_prefix}TelegramError during Step ③ sequence: {te}", exc_info=False)
        user_data["step_3_failed"] = True
        user_data["step_3_failure_reason"] = f"TelegramError: {te}"
    except Exception as e:
        sequence_failed = True
        logger.error(f"{log_prefix}Unexpected error during Step ③ sequence: {e}", exc_info=True)
        user_data["step_3_failed"] = True
        user_data["step_3_failure_reason"] = f"Exception: {e}"

    finally:
        if sequence_failed or not step_4_job_successfully_scheduled:
            logger.warning(f"{log_prefix}Step ③ failed or could not schedule Step ④. Initiating fallback CTA.")
            user_data["step_3_or_4_schedule_failed"] = True
            try:
                fallback_keyboard = InlineKeyboardMarkup(
                    build_single_button_keyboard(
                        BTN_TEXT_FALLBACK_REENGAGE_SYNC,
                        "fallback_sync_trigger_step3"
                    )
                )
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=FALLBACK_CTA_TEXT_STEP_4_FAILED,
                    reply_markup=fallback_keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"{log_prefix}Sent fallback CTA to user due to Step 4 scheduling failure.")
            except Exception as notify_error:
                logger.critical(f"{log_prefix}Failed to send fallback CTA after Step ③ failure: {notify_error}")
