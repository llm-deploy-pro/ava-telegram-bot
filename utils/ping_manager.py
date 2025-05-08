# utils/ping_manager.py

import logging
from datetime import timedelta
# from telegram import ChatAction # Not used in this version, commented out
from telegram.ext import ContextTypes, Job
from telegram.constants import ParseMode
from telegram.error import TelegramError

# Assumed imports from project structure
# Ensure these templates are defined in your messages_en.py or similar
try:
    from templates.messages_en import (
        PING_MSG_30_SECONDS,
        PING_MSG_60_SECONDS,
        PING_MSG_FINAL_TERMINATION
    )
except ImportError:
    logger = logging.getLogger(__name__) # Need logger early for fallback
    logger.warning("Could not import PING message templates. Using basic fallbacks.")
    PING_MSG_30_SECONDS = "[SYSTEM // IDLE_NOTICE] Session requires interaction to proceed."
    PING_MSG_60_SECONDS = "⚠️ [SYSTEM // IDLE_WARNING] Session timeout imminent. Please respond."
    PING_MSG_FINAL_TERMINATION = "❌ [SESSION_TERMINATED // TIMEOUT] Interaction window closed. Please /start again."

logger = logging.getLogger(__name__)

# --- Constants ---
PING_JOB_PREFIX = "user_ping_monitor_" # Prefix for job names for easy identification and cancellation

# --- Main Interface Functions ---

def schedule_ping_check(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int, # Added user_id for better context in logs and potentially user_data access
    secure_id: str, # Needed for the final termination message template
    timeout_seconds: int = 90, # Default full timeout window
    on_final_expiry_callback=None # Optional custom function on final timeout
) -> None:
    """
    Schedules a multi-stage ping sequence (e.g., at T-60s, T-30s, T) if the user stays idle.
    Automatically cancels any previous ping sequences for the same chat_id.

    Args:
        context: The PTB context object, must have access to job_queue.
        chat_id: The target chat ID to monitor and send pings to.
        user_id: The target user ID for logging and potentially accessing user_data.
        secure_id: User's Secure ID, used in the final termination message template.
        timeout_seconds: The total duration (in seconds) after which the final action triggers.
                         Ping timings are calculated relative to this. Minimum useful value > 60.
        on_final_expiry_callback: An optional async function to call upon final timeout instead
                                  of sending the default termination message.
                                  Expected signature: async def my_callback(context, chat_id, user_id, secure_id)
    """
    if not hasattr(context, 'job_queue') or not context.job_queue:
        logger.error(f"[PingManager] JobQueue not available in context for user {user_id}, chat {chat_id}. Pings disabled.")
        return

    # Ensure previous pings for this user/chat are cancelled first
    cancel_existing_ping(context, chat_id, user_id)

    log_prefix = f"[PingManager] User {user_id} (Chat {chat_id}): "
    logger.info(f"{log_prefix}Scheduling new ping monitor sequence. Total timeout: {timeout_seconds}s.")

    # Calculate relative times for pings based on total timeout
    # Pings are sent *before* the final timeout
    # Example: If timeout=90s, first ping at 90-60=30s, second at 90-30=60s, final at 90s.
    first_ping_delay = timeout_seconds - 60
    second_ping_delay = timeout_seconds - 30
    final_expiry_delay = timeout_seconds

    job_base_name = f"{PING_JOB_PREFIX}{chat_id}" # Base name for jobs in this sequence

    # Schedule first ping (e.g., at T-60s) if delay is positive
    if first_ping_delay > 0:
        context.job_queue.run_once(
            _ping_job_callback, # Use a single callback with type distinction
            when=timedelta(seconds=first_ping_delay),
            data={"chat_id": chat_id, "user_id": user_id, "ping_type": "30s_notice", "message_template": PING_MSG_30_SECONDS},
            name=f"{job_base_name}_t_minus_60",
            job_kwargs={"chat_id": chat_id, "user_id": user_id} # Pass identifiers to job context if needed separately
        )
        logger.debug(f"{log_prefix}Scheduled 30s notice ping at {first_ping_delay}s.")
    else:
        logger.debug(f"{log_prefix}Skipping 30s notice ping (timeout <= 60s).")


    # Schedule second ping (e.g., at T-30s) if delay is positive
    if second_ping_delay > 0:
        context.job_queue.run_once(
            _ping_job_callback,
            when=timedelta(seconds=second_ping_delay),
            data={"chat_id": chat_id, "user_id": user_id, "ping_type": "60s_warning", "message_template": PING_MSG_60_SECONDS},
            name=f"{job_base_name}_t_minus_30",
            job_kwargs={"chat_id": chat_id, "user_id": user_id}
        )
        logger.debug(f"{log_prefix}Scheduled 60s warning ping at {second_ping_delay}s.")
    else:
         logger.debug(f"{log_prefix}Skipping 60s warning ping (timeout <= 30s).")

    # Schedule the Final expiry action (at T=timeout_seconds)
    if final_expiry_delay > 0:
        context.job_queue.run_once(
            _ping_final_expire_job, # Use a dedicated job for the final action/callback
            when=timedelta(seconds=final_expiry_delay),
            data={
                "chat_id": chat_id,
                "user_id": user_id,
                "secure_id": secure_id, # Pass secure_id needed for default message/callback
                "custom_callback": on_final_expiry_callback # Pass the custom callback function if provided
            },
            name=f"{job_base_name}_final_expiry",
            job_kwargs={"chat_id": chat_id, "user_id": user_id}
        )
        logger.debug(f"{log_prefix}Scheduled final expiry action at {final_expiry_delay}s.")
    else:
         logger.warning(f"{log_prefix}Final expiry delay is zero or negative ({final_expiry_delay}s). Final action might not be scheduled correctly.")


def cancel_existing_ping(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> None:
    """
    Cancels any active ping monitor jobs specifically for this chat_id.
    """
    if not hasattr(context, 'job_queue') or not context.job_queue:
        # logger.warning(f"[PingManager] Cannot cancel pings for user {user_id}, chat {chat_id}: JobQueue unavailable.")
        return # Silently return if no jobqueue, might happen during shutdown etc.

    # Construct the base name used for jobs for this chat
    job_base_name_prefix = f"{PING_JOB_PREFIX}{chat_id}"
    jobs_to_remove: List[Job] = [] # Use typing.List

    # Iterate through potentially relevant jobs by name prefix
    # get_jobs_by_name returns a tuple, might be empty
    current_jobs = context.job_queue.get_jobs_by_name(f"{job_base_name_prefix}_t_minus_60") + \
                   context.job_queue.get_jobs_by_name(f"{job_base_name_prefix}_t_minus_30") + \
                   context.job_queue.get_jobs_by_name(f"{job_base_name_prefix}_final_expiry")

    for job in current_jobs:
        if job: # Ensure job is not None
             jobs_to_remove.append(job)

    if jobs_to_remove:
        logger.info(f"[PingManager] User {user_id} (Chat {chat_id}): Cancelling {len(jobs_to_remove)} active ping job(s).")
        for job in jobs_to_remove:
            job.schedule_removal()
            logger.debug(f"[PingManager] Scheduled removal for job: {job.name}")
    # else:
        # logger.debug(f"[PingManager] User {user_id} (Chat {chat_id}): No active ping jobs found to cancel.")


# --- Internal Ping Job Callbacks ---

async def _ping_job_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generic callback for sending intermediate ping messages."""
    job_data = context.job.data if context.job else {}
    chat_id = job_data.get("chat_id")
    user_id = job_data.get("user_id")
    ping_type = job_data.get("ping_type", "unknown")
    message_template = job_data.get("message_template", "[SYSTEM PING] Please respond.") # Fallback template

    if not chat_id or not user_id:
        logger.error(f"[Ping Job {ping_type}] Invalid context: Missing chat_id or user_id.")
        return

    log_prefix = f"[Ping Job - {ping_type}] User {user_id} (Chat {chat_id}): "
    logger.info(f"{log_prefix}Sending ping message.")

    try:
        # Ensure template is a string before sending
        if isinstance(message_template, str):
            await context.bot.send_message(
                chat_id=chat_id,
                text=message_template,
                parse_mode=ParseMode.MARKDOWN # Assume Markdown for ping messages
            )
            logger.debug(f"{log_prefix}Ping message sent successfully.")
        else:
            logger.error(f"{log_prefix}Invalid message template provided for ping type {ping_type}.")

    except TelegramError as te:
        logger.error(f"{log_prefix}TelegramError sending {ping_type} ping: {te}", exc_info=False)
        # If user blocked the bot, the job might repeatedly fail. PTB might handle this.
    except Exception as e:
        logger.error(f"{log_prefix}Unexpected error sending {ping_type} ping: {e}", exc_info=True)

async def _ping_final_expire_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for the final timeout action."""
    job_data = context.job.data if context.job else {}
    chat_id = job_data.get("chat_id")
    user_id = job_data.get("user_id")
    secure_id = job_data.get("secure_id", "N/A") # Get secure_id for message/callback
    custom_callback = job_data.get("custom_callback") # Get the custom function

    if not chat_id or not user_id:
        logger.error(f"[Ping Final Job] Invalid context: Missing chat_id or user_id.")
        return

    log_prefix = f"[Ping Final Expire] User {user_id} (Chat {chat_id}, SecureID: {secure_id}): "
    logger.info(f"{log_prefix}Executing final timeout action.")

    try:
        if callable(custom_callback):
            logger.info(f"{log_prefix}Executing custom final expiry callback function.")
            # Pass necessary identifiers to the custom callback
            await custom_callback(context, chat_id, user_id, secure_id)
            logger.info(f"{log_prefix}Custom callback executed successfully.")
        else:
            # Send the default termination message if no custom callback provided
            logger.info(f"{log_prefix}Sending default final termination message.")
            default_termination_msg = PING_MSG_FINAL_TERMINATION.format(secure_id=secure_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=default_termination_msg,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"{log_prefix}Default termination message sent.")
            # Optionally end the conversation here if desired as default behavior
            # This is complex as job callbacks don't directly interact with CH state returns.
            # Setting a flag in user_data is often safer.
            # context.application.user_data[user_id]['conversation_timed_out'] = True

    except TelegramError as te:
        logger.error(f"{log_prefix}TelegramError during final ping action: {te}", exc_info=False)
    except Exception as e:
        logger.error(f"{log_prefix}Unexpected error during final ping action: {e}", exc_info=True)
