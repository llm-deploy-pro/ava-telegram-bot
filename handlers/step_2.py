# handlers/step_2.py

import asyncio
import logging
import time # Added for failure timestamp
from datetime import timedelta # Added for scheduling Step 3 job delay

from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler # Import CH for END constant
from telegram.constants import ParseMode # Import ParseMode
from telegram.error import TelegramError

# Assuming imports from project structure are correct
from templates.messages_en import (
    STEP_1_TRANSITION_TO_STEP_2, # Optional transition message (handle if needed in job scheduling)
    STEP_2_MSG_1_SCAN_INITIATE,
    STEP_2_MSG_2A_VARIANCE_HEADER,
    STEP_2_MSG_2B_ERROR_CLUSTER,
    STEP_2_MSG_2C_SIGNAL_DRIFT,
    STEP_2_MSG_3_DIAGNOSIS_AND_INTERVENTION,
    STEP_2_PROMPT_FOR_DIAGNOSIS_REVIEW,
    BTN_TEXT_REVIEW_DIAGNOSTICS,
    INPUT_CONFIRMATION_VALID_STEP2, # Response to valid ack
    INPUT_ERROR_INVALID_CONFIRMATION_STEP2 # Response to invalid ack text
    # Consider adding ERROR_MSG_STEP_2_FAILED template
)
from utils.state_definitions import AWAITING_STEP_TWO_ACK, AWAITING_STEP_THREE_ACK, AWAITING_STEP_FIVE_CHOICE # Import relevant states
from utils.button_utils import build_single_button_keyboard # Assuming this util function exists
# from utils.helpers import calculate_variance, get_threshold # Example if needed

logger = logging.getLogger(__name__)

# --- Job Callback to send Step 2 Automated Sequence ---
# This function is intended to be called by context.job_queue.run_once, scheduled by step_one_entry
async def start_step_two_automation_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Job callback: Sends Step ②'s automated messages and final prompt with button.
    It retrieves necessary data from job context.
    The ConversationHandler state should ALREADY be AWAITING_STEP_TWO_ACK, set by step_one_entry.
    """
    job_context = context.job.data if context.job else {}
    chat_id = job_context.get("chat_id")
    user_id = job_context.get("user_id")

    # Retrieve essential data stored in user_data by step_one_entry
    user_data = context.application.user_data.get(user_id, {})
    secure_id = user_data.get("secure_id")

    if not chat_id or not user_id or not secure_id:
        logger.error(f"[Step ② Job] CRITICAL data missing. chat_id={chat_id}, user_id={user_id}, secure_id={secure_id}. Aborting job.")
        if chat_id:
             try: await context.bot.send_message(chat_id, text="`[SYS_ERR // SESSION_DATA_CORRUPT]` Critical error. Please /start again.")
             except Exception as e: logger.error(f"Failed to send critical data error msg to {chat_id}: {e}")
        return

    # Retrieve other potentially dynamic values (using defaults for MVP)
    variance_value = user_data.get("variance_value", "0.83") # Example
    threshold_value = user_data.get("threshold_value", "0.50") # Example

    log_prefix = f"[Step ② Sequence] User {user_id} (SecureID: {secure_id}): "
    logger.info(f"{log_prefix}Job started to send automated messages.")

    sequence_failed = False

    try:
        # --- Optional Transition Message Handling ---
        # If step_one_entry scheduled this job with a delay that includes the transition message time.
        # Example: job scheduled for 5.5s, transition message template exists.
        # if hasattr(msg, 'STEP_1_TRANSITION_TO_STEP_2') and msg.STEP_1_TRANSITION_TO_STEP_2:
        #    await context.bot.send_message(chat_id, text=msg.STEP_1_TRANSITION_TO_STEP_2)
        #    logger.debug(f"{log_prefix}Sent transition message.")
        #    # The remaining delay would be implicitly handled by when this job *starts*.
        # Alternatively, the transition message could be its own job scheduled earlier.

        # --- Send Step ② Messages ---
        logger.debug(f"{log_prefix}Sending SCAN_INITIATE...")
        await context.bot.send_message(
            chat_id=chat_id, text=STEP_2_MSG_1_SCAN_INITIATE, parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(3.8)

        logger.debug(f"{log_prefix}Sending VARIANCE_HEADER...")
        await context.bot.send_message(
            chat_id=chat_id, text=STEP_2_MSG_2A_VARIANCE_HEADER.format(
                variance_value=variance_value, threshold_value=threshold_value
            ), parse_mode=ParseMode.MARKDOWN
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

        logger.debug(f"{log_prefix}Sending DIAGNOSIS_AND_INTERVENTION...")
        await context.bot.send_message(
            chat_id=chat_id, text=STEP_2_MSG_3_DIAGNOSIS_AND_INTERVENTION, parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(2.2)

        # Final Prompt with Button
        logger.debug(f"{log_prefix}Sending PROMPT_FOR_DIAGNOSIS_REVIEW with button...")
        try:
            keyboard_markup = InlineKeyboardMarkup(
                build_single_button_keyboard(
                    BTN_TEXT_REVIEW_DIAGNOSTICS,
                    "review_diagnostics_pressed" # Callback data
                )
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=STEP_2_PROMPT_FOR_DIAGNOSIS_REVIEW,
                reply_markup=keyboard_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except NameError:
             logger.error(f"{log_prefix}button_utils.build_single_button_keyboard likely missing. Sending prompt without button.")
             await context.bot.send_message(
                 chat_id=chat_id,
                 text=STEP_2_PROMPT_FOR_DIAGNOSIS_REVIEW + "\n\n`(Button unavailable. Please type 'OK' to continue.)`",
                 parse_mode=ParseMode.MARKDOWN
             )

        logger.info(f"{log_prefix}Step ② automated sequence completed successfully. User is in AWAITING_STEP_TWO_ACK state.")

    except TelegramError as te:
        sequence_failed = True
        logger.error(f"{log_prefix}TelegramError during Step ② sequence: {te}", exc_info=False)
        user_data["step_2_failed"] = True
        user_data["step_2_failure_reason"] = f"TelegramError: {te}"
    except Exception as e:
        sequence_failed = True
        logger.error(f"{log_prefix}Unexpected error during Step ② sequence: {e}", exc_info=True)
        user_data["step_2_failed"] = True
        user_data["step_2_failure_reason"] = f"Exception: {e}"

    finally:
        if sequence_failed:
            logger.warning(f"{log_prefix}Step ② sequence failed.")
            try:
                error_message = "`[SYSTEM_ERROR // DIAGNOSTIC_SCAN_FAILED]`\n`An error occurred during the analysis phase. Please type /start to try again.`"
                await context.bot.send_message(chat_id=chat_id, text=error_message, parse_mode=ParseMode.MARKDOWN)
            except Exception as notify_error:
                logger.error(f"{log_prefix}Failed to send failure notification: {notify_error}")
            # The ConversationHandler remains in AWAITING_STEP_TWO_ACK state,
            # The handler for this state MUST check the 'step_2_failed' flag.

# --- Handlers for AWAITING_STEP_TWO_ACK state ---
# These functions handle the user's response ('OK' text or button click) AFTER the job above completes.
# They should be IMPORTED and REGISTERED in main.py's ConversationHandler for the AWAITING_STEP_TWO_ACK state.

async def handle_step_2_ack_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user typing 'OK' (or similar regex match) after Step 2 prompt."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_data = context.user_data # Access user_data directly
    secure_id = user_data.get("secure_id", "N/A")
    log_prefix = f"[Step 2 Ack Text] User {user.id} (SecureID: {secure_id}): "

    # Check failure flag before proceeding
    if user_data.get("step_2_failed"):
        logger.warning(f"{log_prefix}Detected previous Step 2 failure flag. Aborting.")
        await update.message.reply_text("`[SYSTEM_NOTICE] Previous protocol phase encountered an error. Session reset. Please type /start to re-initiate.`", parse_mode=ParseMode.MARKDOWN)
        user_data.clear() # Clear data on failure
        return ConversationHandler.END

    logger.info(f"{log_prefix}Received valid text confirmation ('{update.message.text}'). Scheduling Step 3 automation.")

    # Send immediate confirmation
    await update.message.reply_text(INPUT_CONFIRMATION_VALID_STEP2, parse_mode=ParseMode.MARKDOWN)

    # Schedule Step 3 automation job
    if hasattr(context, "job_queue") and context.job_queue:
        job_data_for_step_3 = {"chat_id": chat_id, "user_id": user.id} # Pass necessary context
        try:
            from handlers.step_3 import start_step_three_automation_job # Import here or globally
            context.job_queue.run_once(
                start_step_three_automation_job,
                when=timedelta(seconds=1.0), # Short delay before Step 3 starts
                data=job_data_for_step_3,
                name=f"step_3_start_{chat_id}"
            )
            logger.info(f"{log_prefix}Scheduled Step 3 automation job.")
        except ImportError:
            logger.error(f"{log_prefix}Cannot schedule Step 3: handlers.step_3 not found.")
            await update.message.reply_text("`[SYSTEM_ERROR] Cannot proceed to next phase (Module missing). Please contact support.`")
            return ConversationHandler.END # End if cannot schedule
        except Exception as e:
             logger.error(f"{log_prefix}Error scheduling Step 3 job: {e}", exc_info=True)
             await update.message.reply_text("`[SYSTEM_ERROR] Cannot schedule next phase. Please contact support or /start again.`")
             return ConversationHandler.END # End on scheduling error
    else:
        logger.error(f"{log_prefix}JobQueue not available. Cannot schedule Step 3.")
        await update.message.reply_text("`[CRITICAL_SYSTEM_ERROR] Cannot proceed. Please contact support or /start later.`")
        return ConversationHandler.END # End if job queue is missing

    # Return the state the bot should be in *after* Step 3 and Step 4 auto messages complete
    # and the Step 4 prompt/buttons are shown.
    logger.info(f"{log_prefix}Transitioning ConversationHandler state to AWAITING_STEP_FIVE_CHOICE.")
    return AWAITING_STEP_FIVE_CHOICE # The state after Step 4 prompt is shown

async def handle_step_2_ack_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user pressing the 'Review Diagnostics' button after Step 2 prompt."""
    query = update.callback_query
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_data = context.user_data
    secure_id = user_data.get("secure_id", "N/A")
    log_prefix = f"[Step 2 Ack Button] User {user.id} (SecureID: {secure_id}): "

    await query.answer() # Always answer callback queries

    # Check failure flag
    if user_data.get("step_2_failed"):
        logger.warning(f"{log_prefix}Detected previous Step 2 failure flag. Aborting.")
        try:
            await query.edit_message_text("`[SYSTEM_NOTICE] Previous protocol phase encountered an error. Session reset. Please type /start to re-initiate.`", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"{log_prefix}Failed to edit message on failure ack: {e}")
        user_data.clear()
        return ConversationHandler.END

    logger.info(f"{log_prefix}Received button confirmation ('{query.data}'). Scheduling Step 3 automation.")

    # Edit the message to show confirmation
    try:
        await query.edit_message_text(INPUT_CONFIRMATION_VALID_STEP2, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.warning(f"{log_prefix}Could not edit message after button press: {e}")
        # If edit fails, still proceed with scheduling, maybe send a new message if important
        # try: await context.bot.send_message(chat_id, text=INPUT_CONFIRMATION_VALID_STEP2)
        # except: pass # Best effort

    # Schedule Step 3 automation job
    if hasattr(context, "job_queue") and context.job_queue:
        job_data_for_step_3 = {"chat_id": chat_id, "user_id": user.id}
        try:
            from handlers.step_3 import start_step_three_automation_job # Import here or globally
            context.job_queue.run_once(
                start_step_three_automation_job,
                when=timedelta(seconds=1.0),
                data=job_data_for_step_3,
                name=f"step_3_start_{chat_id}"
            )
            logger.info(f"{log_prefix}Scheduled Step 3 automation job.")
        except ImportError:
            logger.error(f"{log_prefix}Cannot schedule Step 3: handlers.step_3 not found.")
            # Try sending message since editing might have failed
            try: await context.bot.send_message(chat_id, text="`[SYSTEM_ERROR] Cannot proceed (Module missing). Contact support.`")
            except: pass
            return ConversationHandler.END
        except Exception as e:
             logger.error(f"{log_prefix}Error scheduling Step 3 job: {e}", exc_info=True)
             try: await context.bot.send_message(chat_id, text="`[SYSTEM_ERROR] Cannot schedule next phase. Contact support or /start again.`")
             except: pass
             return ConversationHandler.END
    else:
        logger.error(f"{log_prefix}JobQueue not available. Cannot schedule Step 3.")
        try: await context.bot.send_message(chat_id, text="`[CRITICAL_SYSTEM_ERROR] Cannot proceed. Contact support or /start later.`")
        except: pass
        return ConversationHandler.END

    # Return the state expected after Step 3 & 4 auto messages complete
    logger.info(f"{log_prefix}Transitioning ConversationHandler state to AWAITING_STEP_FIVE_CHOICE.")
    return AWAITING_STEP_FIVE_CHOICE

# Placeholder import for the function that starts Step 3 job (must exist in handlers/step_3.py)
try:
    from handlers.step_3 import start_step_three_automation_job
except ImportError:
    async def start_step_three_automation_job(context: ContextTypes.DEFAULT_TYPE): # type: ignore
         job_context = context.job.data if context.job else {}
         chat_id = job_context.get("chat_id")
         logger.error(f"[Step 2 Ack Handler] CRITICAL_PLACEHOLDER: start_step_three_automation_job is MISSING from handlers/step_3.py. Job for chat {chat_id} will fail to start Step 3.")