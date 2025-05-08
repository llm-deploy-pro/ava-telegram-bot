# handlers/step_2.py

import asyncio
import logging
import time # Added for failure timestamp
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler # Import CH for END constant
from telegram.constants import ParseMode # Import ParseMode
from telegram.error import TelegramError

# Assuming imports from project structure are correct
# ✅ Item ① Fix: Directly use imported names, not msg. prefix
from templates.messages_en import (
    # STEP_1_TRANSITION_TO_STEP_2, # Optional transition message (removed for simplicity, handle delay directly in job scheduling if needed)
    STEP_2_MSG_1_SCAN_INITIATE,
    STEP_2_MSG_2A_VARIANCE_HEADER,
    STEP_2_MSG_2B_ERROR_CLUSTER,
    STEP_2_MSG_2C_SIGNAL_DRIFT,
    STEP_2_MSG_3_DIAGNOSIS_AND_INTERVENTION,
    STEP_2_PROMPT_FOR_DIAGNOSIS_REVIEW,
    BTN_TEXT_REVIEW_DIAGNOSTICS,
    # Consider adding a specific error message template here or in a dedicated file
    # ERROR_MSG_STEP_2_FAILED = "`[SYSTEM_ERROR // PROTOCOL_INTERRUPTED]...`"
)
from utils.state_definitions import AWAITING_STEP_TWO_ACK # The state CH should be in AFTER this sequence prompts user
from utils.button_utils import build_single_button_keyboard # Assuming this util function exists
# from utils.helpers import ... # Import helpers if needed for dynamic values like variance

logger = logging.getLogger(__name__)

# This function is intended to be called by context.job_queue.run_once, scheduled by step_one_entry
async def start_step_two_automation_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Job callback function: Sends the automated message sequence for Step ②,
    concluding with the user prompt and button for AWAITING_STEP_TWO_ACK state.
    IMPORTANT: This function CANNOT return a state to ConversationHandler.
    The state transition (to AWAITING_STEP_TWO_ACK) must have already been set
    by the function that scheduled this job (i.e., step_one_entry returning that state).
    """
    job_context = context.job.data if context.job else {} # Protect against missing job context
    chat_id = job_context.get("chat_id")
    user_id = job_context.get("user_id")

    # Retrieve essential data stored in user_data by step_one_entry
    # ✅ Item ② Fix (from prev review): Robust check for essential data from user_data
    # Ensure user_data exists and contains the key. Use chat_id as primary key for user_data if per_user=True in CH
    user_data = context.application.user_data.get(user_id, {}) # Get user_data associated with user_id
    secure_id = user_data.get("secure_id")

    if not chat_id or not user_id or not secure_id:
        logger.error(f"[Step ② Job] CRITICAL data missing. chat_id={chat_id}, user_id={user_id}, secure_id={secure_id}. Aborting job.")
        # Attempt to inform admin or log this critical failure
        # Cannot easily end CH from here. Logging is crucial.
        return # Stop executing the job

    # Retrieve other potentially dynamic values (using defaults for MVP)
    variance_value = user_data.get("variance_value", "0.83") # Example, retrieve if needed
    threshold_value = user_data.get("threshold_value", "0.50") # Example

    log_prefix = f"[Step ② Sequence] User {user_id} (SecureID: {secure_id}): "
    logger.info(f"{log_prefix}Job started to send automated messages.")

    # Flag to track if any message failed, for potential fallback logic
    sequence_failed = False

    try:
        # --- Send Step ② Messages ---

        # Message 1: Scan Initiate
        logger.debug(f"{log_prefix}Sending SCAN_INITIATE...")
        # ✅ Item ② Fix: Using ParseMode.MARKDOWN (more forgiving)
        await context.bot.send_message(
            chat_id=chat_id,
            text=STEP_2_MSG_1_SCAN_INITIATE,
            parse_mode=ParseMode.MARKDOWN # Safer default
        )
        await asyncio.sleep(3.8) # Internal delay

        # Message 2: Variance Report (sent in parts)
        logger.debug(f"{log_prefix}Sending VARIANCE_HEADER...")
        await context.bot.send_message(
            chat_id=chat_id,
            text=STEP_2_MSG_2A_VARIANCE_HEADER.format(
                variance_value=variance_value, threshold_value=threshold_value
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(1.5)

        logger.debug(f"{log_prefix}Sending ERROR_CLUSTER...")
        await context.bot.send_message(
            chat_id=chat_id, text=STEP_2_MSG_2B_ERROR_CLUSTER, parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(1.2)

        logger.debug(f"{log_prefix}Sending SIGNAL_DRIFT...")
        await context.bot.send_message(
            chat_id=chat_id, text=STEP_2_MSG_2C_SIGNAL_DRIFT, parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(1.8)

        # Message 3: Diagnosis Summary and Intervention Required
        logger.debug(f"{log_prefix}Sending DIAGNOSIS_AND_INTERVENTION...")
        await context.bot.send_message(
            chat_id=chat_id, text=STEP_2_MSG_3_DIAGNOSIS_AND_INTERVENTION, parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(2.2)

        # Final Prompt with Button
        logger.debug(f"{log_prefix}Sending PROMPT_FOR_DIAGNOSIS_REVIEW with button...")
        # Assuming button_utils.build_single_button_keyboard returns InlineKeyboardMarkup
        try:
            keyboard_markup = InlineKeyboardMarkup(
                build_single_button_keyboard(
                    BTN_TEXT_REVIEW_DIAGNOSTICS, # Uses constant from templates
                    "review_diagnostics_pressed" # Callback data
                )
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=STEP_2_PROMPT_FOR_DIAGNOSIS_REVIEW,
                reply_markup=keyboard_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except NameError: # Fallback if button_utils or function is not defined
             logger.error(f"{log_prefix}button_utils.build_single_button_keyboard not found. Sending prompt without button.")
             await context.bot.send_message(
                 chat_id=chat_id,
                 text=STEP_2_PROMPT_FOR_DIAGNOSIS_REVIEW + "\n\n(Button generation failed. Please type 'OK')", # Modify prompt slightly
                 parse_mode=ParseMode.MARKDOWN
             )

        # ✅ Item ④ Fix: This job DOES NOT set the ConversationHandler state.
        # ConversationHandler should already be in AWAITING_STEP_TWO_ACK.
        logger.info(f"{log_prefix}Step ② automated sequence completed. User prompted for input in state AWAITING_STEP_TWO_ACK.")

    except TelegramError as te:
        sequence_failed = True
        # Log specific Telegram errors (e.g., blocked, chat not found) differently if needed
        logger.error(f"{log_prefix}TelegramError during Step ② sequence: {te}", exc_info=False) # Less verbose for common API errors
        # Optionally set failure flag in user_data if next handler needs to know
        user_data["step_2_failed"] = True
        user_data["step_2_failure_reason"] = f"TelegramError: {te}"
        logger.warning(f"{log_prefix}Marked step_2_failed=True in user_data due to TelegramError.")

    except Exception as e:
        sequence_failed = True
        logger.error(f"{log_prefix}Unexpected error during Step ② sequence: {e}", exc_info=True)
        # ✅ Item ③ Fix: Record failure context using user_data
        user_data["step_2_failed"] = True
        user_data["step_2_failure_reason"] = f"Exception: {e}"
        logger.warning(f"{log_prefix}Marked step_2_failed=True in user_data due to Exception.")
        # Attempt to notify the user (best effort)
        try:
            error_message_template = "`[SYSTEM_ERROR // PROTOCOL_HALTED]`\n`A critical error occurred during the diagnostic phase. Process cannot continue.`\n`Please type /start to attempt a new session.`"
            await context.bot.send_message(
                chat_id=chat_id,
                text=error_message_template,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"{log_prefix}Sent sequence failure notification to user.")
        except Exception as final_e:
            logger.error(f"{log_prefix}Failed to send error notification to user after sequence error: {final_e}")

    # No return value is needed as this is a job callback.
    # State management relies on the ConversationHandler structure defined in main.py
    # and the return values of handlers triggered by user actions.

# --- Handlers for AWAITING_STEP_TWO_ACK state ---
# These functions would typically be in this file or user_input_handler.py
# They are called by ConversationHandler based on user input AFTER the job above completes.

async def handle_step_2_ack_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user typing 'OK' (or similar regex match) after Step 2 prompt."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    secure_id = context.user_data.get("secure_id", "N/A")
    log_prefix = f"[Step 2 Ack Text] User {user.id} (SecureID: {secure_id}): "

    # ✅ Item ③ Fix: Check failure flag before proceeding
    if context.user_data.get("step_2_failed"):
        logger.warning(f"{log_prefix}Detected previous failure flag. Aborting further steps.")
        await update.message.reply_text("`[SYSTEM_NOTICE] Previous protocol phase encountered an error. Please type /start to re-initiate.`", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    logger.info(f"{log_prefix}Received valid text confirmation ('{update.message.text}'). Proceeding to Step 3 logic.")

    # Here, you would trigger Step 3's automated message sequence.
    # Similar to Step 1 -> Step 2, this might involve scheduling a job.
    # Example: context.job_queue.run_once(start_step_three_automation_job, ...)
    # After scheduling, return the state where Step 3's sequence ends and awaits user input (if any).
    # Assuming Step 3 also ends awaiting user input/action:
    from utils.state_definitions import AWAITING_STEP_THREE_ACK # Assuming Step 3 leads to this state
    # Placeholder: Send a simple confirmation and return next state for now
    await update.message.reply_text("`[ACKNOWLEDGED] // Compiling diagnostic report...`", parse_mode=ParseMode.MARKDOWN)
    # TODO: Schedule Step 3 automation job here
    logger.info(f"{log_prefix}Returning AWAITING_STEP_THREE_ACK. (Step 3 job scheduling placeholder)")
    return AWAITING_STEP_THREE_ACK # Return the next state

async def handle_step_2_ack_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user pressing the 'Review Diagnostics' button after Step 2 prompt."""
    query = update.callback_query
    user = update.effective_user
    chat_id = update.effective_chat.id
    secure_id = context.user_data.get("secure_id", "N/A")
    log_prefix = f"[Step 2 Ack Button] User {user.id} (SecureID: {secure_id}): "

    await query.answer() # Always answer callback queries

    # ✅ Item ③ Fix: Check failure flag
    if context.user_data.get("step_2_failed"):
        logger.warning(f"{log_prefix}Detected previous failure flag. Aborting further steps.")
        await query.edit_message_text("`[SYSTEM_NOTICE] Previous protocol phase encountered an error. Please type /start to re-initiate.`", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    logger.info(f"{log_prefix}Received button confirmation ('{query.data}'). Proceeding to Step 3 logic.")

    # Edit the message to show confirmation (optional, good UX)
    try:
        await query.edit_message_text("`[ACKNOWLEDGED] // Compiling diagnostic report... Please wait.`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.warning(f"{log_prefix}Could not edit message after button press: {e}")
        # If edit fails, maybe send a new message as confirmation
        try:
             await context.bot.send_message(chat_id, text="`[ACKNOWLEDGED] // Compiling diagnostic report...`", parse_mode=ParseMode.MARKDOWN)
        except Exception as send_e:
             logger.error(f"{log_prefix}Failed to send confirmation message either: {send_e}")


    # Trigger Step 3's automated message sequence (e.g., via job_queue).
    # Example: context.job_queue.run_once(start_step_three_automation_job, ...)
    from utils.state_definitions import AWAITING_STEP_THREE_ACK # Assuming Step 3 leads to this state
    # TODO: Schedule Step 3 automation job here
    logger.info(f"{log_prefix}Returning AWAITING_STEP_THREE_ACK. (Step 3 job scheduling placeholder)")
    return AWAITING_STEP_THREE_ACK # Return the next state