# handlers/step_5.py (Conceptual Refinements Included)

import logging
import time
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError

# Assume correct imports from templates, utils etc.
from templates.messages_en import (
    STEP_5_MSG_1_FINAL_NODE_STATUS, STEP_5_MSG_2_KEY_EXPIRATION_WARNING,
    STEP_5_MSG_3_EXECUTION_PROMPT, CTA_INPUT_VAGUE_POSITIVE_RESPONSE,
    CTA_INPUT_HESITATION_PRICE_RESPONSE, CTA_INPUT_HESITATION_BENEFIT_OR_LEGITIMACY_RESPONSE,
    CTA_INPUT_NEGATIVE_RESPONSE, BTN_TEXT_FINALIZE_SYNC_PRIMARY,
    BTN_TEXT_ACTIVATE_SECURE_SYNC_AB_PRICE, BTN_TEXT_FINAL_CHANCE_SYNC
)
# ✅ Item 4 Fix: Use consistent state names from state_definitions
from utils.state_definitions import STEP_5_AWAITING_FINAL_ACTION, STEP_5_FINAL_CHANCE_STATE # Example names
from utils.helpers import get_formatted_time_left # Assumes returns (is_expired, time_str)
from utils.button_utils import build_single_button_keyboard

logger = logging.getLogger(__name__)

# --- Handler triggered by Step 4's "Initiate Sync" button ---
# ✅ Item 1 Fix: Renamed for clarity, this function sends the Step 5 sequence
async def send_step_five_cta_sequence(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends the Step 5 message sequence and prompts for final action."""
    query = update.callback_query
    await query.answer() # Answer immediately

    user = update.effective_user
    user_data = context.user_data
    chat_id = update.effective_chat.id
    secure_id = user_data.get("secure_id", "N/A")
    countdown_start = user_data.get("step_4_countdown_start")
    countdown_total = user_data.get("step_4_total_duration")

    log_prefix = f"[Step 5 Entry] User {user.id} (SecureID: {secure_id}): "

    # ✅ Item 2 Fix: Robust check and clear time calculation
    if not countdown_start or not countdown_total:
         logger.error(f"{log_prefix}Missing countdown data in user_data. Aborting Step 5.")
         await context.bot.send_message(chat_id, text="`[SYS_ERR] Session data error. Please /start again.`")
         return ConversationHandler.END

    is_expired, time_left_str = get_formatted_time_left(countdown_start, countdown_total)
    if is_expired:
        logger.info(f"{log_prefix}Access window expired before Step 5 sequence started.")
        await context.bot.send_message(chat_id=chat_id, text="`[SESSION_EXPIRED] Your access window has expired. Please restart via /start.`", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    logger.info(f"{log_prefix}Sending Step 5 CTA sequence. Time left: {time_left_str}")

    try:
        # Send Message 1: Final Status Recap
        await context.bot.send_message(chat_id=chat_id, text=STEP_5_MSG_1_FINAL_NODE_STATUS.format(secure_id=secure_id), parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(1.5) # Example delay

        # Send Message 2: Expiration countdown (using the main Step 4 timer)
        await context.bot.send_message(chat_id=chat_id, text=STEP_5_MSG_2_KEY_EXPIRATION_WARNING.format(secure_id=secure_id, time_left_final_cta=time_left_str), parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(1.5) # Example delay

        # Send Message 3: Final CTA Prompt and Button
        keyboard = InlineKeyboardMarkup(build_single_button_keyboard(BTN_TEXT_FINALIZE_SYNC_PRIMARY, "final_sync_initiated"))
        await context.bot.send_message(
            chat_id=chat_id,
            text=STEP_5_MSG_3_EXECUTION_PROMPT.format(secure_id=secure_id),
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"{log_prefix}Step 5 prompt sent. Transitioning to STEP_5_AWAITING_FINAL_ACTION.")
        # ✅ Item 1 Fix: Return the state where final button click or text is handled
        return STEP_5_AWAITING_FINAL_ACTION

    except Exception as e:
        logger.error(f"{log_prefix}Error sending Step 5 sequence: {e}", exc_info=True)
        await context.bot.send_message(chat_id, text="`[SYS_ERR] Error displaying final options. Please try /start again.`")
        return ConversationHandler.END


# --- Handler for the final CTA button click ---
async def handle_final_sync_initiated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the final 'FINALIZE SYNC' button press."""
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    user_data = context.user_data
    secure_id = user_data.get("secure_id", "N/A")
    log_prefix = f"[Final Sync Click] User {user.id} (SecureID: {secure_id}): "

    # Final check for expiration maybe? Or assume if button is clickable, it's ok.
    # For robustness, check main timer again.
    countdown_start = user_data.get("step_4_countdown_start")
    countdown_total = user_data.get("step_4_total_duration")
    if countdown_start and countdown_total:
        is_expired, _ = get_formatted_time_left(countdown_start, countdown_total)
        if is_expired:
            logger.warning(f"{log_prefix}User clicked finalize button AFTER main window expired.")
            await query.edit_message_text("`[ACTION_EXPIRED] The sync window closed while you decided. Please restart with /start.`", parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END

    logger.info(f"{log_prefix}Confirmed FINAL SYNC. Initiating ENTRY_SYNC_49 process (simulation).")

    try:
        await query.edit_message_text(
            text="`[SYNC_COMMAND_ACCEPTED]`\n`ENTRY_SYNC_49 protocol authorized and initiated.`\n`Processing secure activation channel... This may take a moment.`",
            parse_mode=ParseMode.MARKDOWN
        )
        # TODO: Add logic here to actually redirect to payment or activate service
        logger.info(f"{log_prefix}Simulated successful activation. Ending conversation.")

    except Exception as e:
        logger.error(f"{log_prefix}Could not edit final confirmation message: {e}")
        # Attempt to send new message if edit failed
        try:
            await context.bot.send_message(update.effective_chat.id, text="`[SYNC_INITIATED]` Activation proceeding.")
        except: pass # Best effort

    # Successfully initiated the sync/payment process
    return ConversationHandler.END


# --- Handler for text input during the final CTA stage ---
async def handle_step5_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles user text input when awaiting the final CTA button press."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_data = context.user_data
    secure_id = user_data.get("secure_id", "N/A")
    message_text = update.message.text.strip().lower() if update.message and update.message.text else ""
    log_prefix = f"[Step 5 Text Input] User {user.id} (SecureID: {secure_id}): "

    # Check timers: Main window timer AND potential "final chance" timer
    main_expired, main_time_left = get_formatted_time_left(user_data.get("step_4_countdown_start"), user_data.get("step_4_total_duration"))
    final_chance_expire_at = user_data.get("final_chance_expire_at")
    final_chance_expired, final_chance_time_left = (False, "N/A")
    if final_chance_expire_at:
        final_chance_expired, final_chance_time_left = get_formatted_time_left_from_deadline(final_chance_expire_at) # Needs this helper

    if main_expired and not final_chance_expire_at: # Main window expired, no final chance active
        logger.info(f"{log_prefix}Main window expired before text input handled.")
        await update.message.reply_text("`[SESSION_EXPIRED] Your sync window expired. Please /start again.`", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    elif final_chance_expired: # Final chance window expired
        logger.info(f"{log_prefix}Final chance window expired before text input handled.")
        await update.message.reply_text("`[FINAL_CHANCE_EXPIRED] The override window has closed. Node disqualified. Please /start again.`", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    logger.info(f"{log_prefix}Received text: '{message_text[:50]}...'") # Log received text

    # --- Input Classification Logic ---
    response_text = ""
    button_text = BTN_TEXT_FINALIZE_SYNC_PRIMARY # Default button
    button_callback = "final_sync_initiated"
    next_state = STEP_5_AWAITING_FINAL_ACTION # Default state to return

    if message_text in ["ok", "okay", "yes", "sure", "ready", "proceed", "do it"]:
        response_text = CTA_INPUT_VAGUE_POSITIVE_RESPONSE
        # Keep default button
    elif "$" in message_text or "49" in message_text or "cost" in message_text or "price" in message_text or "pay" in message_text:
        response_text = CTA_INPUT_HESITATION_PRICE_RESPONSE
        button_text = BTN_TEXT_ACTIVATE_SECURE_SYNC_AB_PRICE # Show price on button
        button_callback = "final_sync_initiated" # Still leads to same final action
    elif any(word in message_text for word in ["real", "legit", "scam", "proof", "what do i get", "benefit", "result"]):
        response_text = CTA_INPUT_HESITATION_BENEFIT_OR_LEGITIMACY_RESPONSE.format(secure_id=secure_id)
        button_text = BTN_TEXT_ACTIVATE_SECURE_SYNC_AB_PRICE # Show price on button
        button_callback = "final_sync_initiated"
    elif any(word in message_text for word in ["no", "stop", "leave", "exit", "cancel", "not paying", "don't want"]):
        # Initiate final chance sequence
        final_chance_duration_sec = 119 # ~ 2 minutes
        expire_ts = time.time() + final_chance_duration_sec
        user_data["final_chance_expire_at"] = expire_ts
        _, final_chance_time_str = get_formatted_time_left(time.time(), final_chance_duration_sec) # Get initial display time

        response_text = CTA_INPUT_NEGATIVE_RESPONSE.format(secure_id=secure_id, final_chance_time_left=final_chance_time_str)
        # ✅ Item 6 Fix: Use button utils and template constant
        final_button_text = BTN_TEXT_FINAL_CHANCE_SYNC.format(time_left=final_chance_time_str) # Format button text
        keyboard = InlineKeyboardMarkup(build_single_button_keyboard(final_button_text, "final_sync_initiated"))
        await update.message.reply_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        logger.info(f"{log_prefix}User indicated rejection. Offered final chance expiring at {expire_ts}.")
        # ✅ Item 4 Fix: Return specific state for final chance
        return STEP_5_FINAL_CHANCE_STATE # Transition to a state that specifically waits for this button or timeout
    else:
        # Default fallback for unrecognized text in this specific state
        response_text = "`[SYSTEM_INPUT_UNRECOGNIZED // AWAITING_FINAL_COMMAND]`\n`To finalize node synchronization, please use the button below or confirm your intent.`"
        # Keep default button

    # Send the determined response and button
    try:
        keyboard = InlineKeyboardMarkup(build_single_button_keyboard(button_text, button_callback))
        await update.message.reply_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"{log_prefix}Failed to send response for text input '{message_text}': {e}")
        # Fallback if sending response fails
        await update.message.reply_text("`[SYS_ERR] Error processing your input. Please use the last provided button or type /cancel.`")

    return next_state # Return the state where we continue waiting for final action

# Placeholder for handler for the "Query Necessity" button from Step 4
async def handle_step4_query_necessity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the 'Query Protocol Necessity' button click from Step 4."""
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    user_data = context.user_data
    chat_id = update.effective_chat.id
    secure_id = user_data.get("secure_id", "N/A")
    log_prefix = f"[Step 4 Query] User {user.id} (SecureID: {secure_id}): "

    # Check main timer expiration
    countdown_start = user_data.get("step_4_countdown_start")
    countdown_total = user_data.get("step_4_total_duration")
    if countdown_start and countdown_total:
        is_expired, time_left_str = get_formatted_time_left(countdown_start, countdown_total)
        if is_expired:
            logger.info(f"{log_prefix}Access window expired before query handled.")
            await query.edit_message_text("`[SESSION_EXPIRED] Your access window expired while querying. Please /start again.`", parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END
    else:
        logger.error(f"{log_prefix}Missing countdown data for query response.")
        await query.edit_message_text("`[SYS_ERR] Session data error. Please /start again.`")
        return ConversationHandler.END

    # Retrieve necessary dynamic data for the response message
    variance_value = user_data.get("variance_value", "0.83")
    remaining_slots = user_data.get("step_4_initial_slots", 3) # Or dynamically get current slots

    logger.info(f"{log_prefix}User queried protocol necessity. Sending clarification and CTA.")

    response_text = STEP_4_RESPONSE_TO_QUERY_NECESSITY.format(
        variance_value=variance_value,
        time_left_formatted=time_left_str,
        remaining_slots=remaining_slots,
        secure_id=secure_id # Added secure_id if needed in template
    )
    keyboard = InlineKeyboardMarkup(
        build_single_button_keyboard(
            BTN_TEXT_EXECUTE_SYNC_POST_QUERY, # Button text from templates
            "final_sync_initiated" # Still leads to the final sync action
        )
    )

    try:
        # Edit the original message containing the two choice buttons
        await query.edit_message_text(
            text=response_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"{log_prefix}Failed to edit message for query response: {e}")
        # Fallback: Send a new message if editing fails
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=response_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as send_e:
            logger.error(f"{log_prefix}Failed to send new message for query response: {send_e}")
            await context.bot.send_message(chat_id, text="`[SYS_ERR] Could not display protocol details. Please try /start again.`")
            return ConversationHandler.END

    # After showing the query response and the execution button, user is back in the state awaiting final action
    logger.info(f"{log_prefix}Query response sent. Transitioning state to STEP_5_AWAITING_FINAL_ACTION.")
    return STEP_5_AWAITING_FINAL_ACTION
