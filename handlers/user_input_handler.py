# handlers/user_input_handler.py

import logging
import time
import random # For rotating fallback messages
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError

# Assume utils and templates are importable
try:
    from utils.state_definitions import (
        AWAITING_STEP_TWO_ACK, AWAITING_STEP_FIVE_CHOICE,
        STEP_5_AWAITING_FINAL_ACTION, STEP_5_FINAL_CHANCE_STATE,
        # ✅ Item 2 Suggestion: Define this new state
        STEP_5_REJECTION_WARNING_STATE # State after initial rejection, before final chance
    )
    from templates.messages_en import (
        INPUT_CONFIRMATION_VALID_STEP2, INPUT_ERROR_INVALID_CONFIRMATION_STEP2,
        CTA_INPUT_VAGUE_POSITIVE_RESPONSE, CTA_INPUT_HESITATION_PRICE_RESPONSE,
        CTA_INPUT_HESITATION_BENEFIT_OR_LEGITIMACY_RESPONSE, CTA_INPUT_NEGATIVE_RESPONSE,
        BTN_TEXT_FINALIZE_SYNC_PRIMARY,
        BTN_TEXT_ACTIVATE_SECURE_SYNC_AB_PRICE, # Assumes one version for now
        # ✅ Item 3 Suggestion: Define A/B versions in templates
        BTN_TEXT_ACTIVATE_SECURE_SYNC_AB_PRICE_B, # Example A/B version
        BTN_TEXT_FINAL_CHANCE_SYNC,
        # ✅ Item 2 Suggestion: New message template needed
        STEP_5_REJECTION_WARNING_PROMPT, # Template for the rejection buffer prompt
        # ✅ Item 4 Suggestion: More strategic unknown input responses
        UNKNOWN_INPUT_FALLBACK_PROMPTS # A list of fallback prompts
    )
    from utils.helpers import get_formatted_time_left, get_formatted_time_left_from_deadline # Need deadline variant
    from utils.button_utils import build_single_button_keyboard, build_yes_no_buttons # Need yes/no for rejection warning
except ImportError as e:
    logging.getLogger(__name__).critical(f"CRITICAL: Failed to import modules in user_input_handler.py: {e}")
    # Define fallbacks
    AWAITING_STEP_TWO_ACK, AWAITING_STEP_FIVE_CHOICE, STEP_5_AWAITING_FINAL_ACTION, STEP_5_FINAL_CHANCE_STATE, STEP_5_REJECTION_WARNING_STATE = 0, 1, 2, 3, 4
    INPUT_CONFIRMATION_VALID_STEP2 = "`[ACKNOWLEDGED]` Proceeding..."
    INPUT_ERROR_INVALID_CONFIRMATION_STEP2 = "`[INPUT_ERROR]` Please type 'OK' or use the button."
    CTA_INPUT_VAGUE_POSITIVE_RESPONSE = "Preparing action..."
    # ... other fallback messages ...
    UNKNOWN_INPUT_FALLBACK_PROMPTS = ["`[SYS] Awaiting specific command or button press.`"]


logger = logging.getLogger(__name__)

# --- Main Input Router ---
# Ideally, specific states in main.py's ConversationHandler directly map to these functions,
# rather than routing based on user_data state here (which is less robust).
# This router is kept for conceptual clarity based on previous structure, but direct mapping is preferred.

async def route_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """
    Routes text input based on CURRENT ConversationHandler state.
    NOTE: It's more robust for main.py's CH definition to directly map states to these handlers.
    This function assumes it's called as a general MessageHandler within certain CH states.
    """
    user = update.effective_user
    if not user or not update.message or not update.message.text: return None

    # ✅ Item 1 Risk Mitigation: Get state reliably if possible, but handler mapping in main.py is key.
    # The state should be known because the CH mapped the update to *this* handler based on the *current state*.
    # We might not need to fetch it from user_data explicitly here if CH mapping is correct.
    # For logging/robustness:
    current_state = context.user_data.get(ConversationHandler.STATE)
    log_prefix = f"[Input Router] User {user.id} (State: {current_state}): "
    logger.info(f"{log_prefix}Routing text: '{update.message.text[:50]}...'")

    if current_state == AWAITING_STEP_TWO_ACK:
        return await _handle_step2_text_ack_logic(update, context)
    elif current_state in [AWAITING_STEP_FIVE_CHOICE, STEP_5_AWAITING_FINAL_ACTION, STEP_5_FINAL_CHANCE_STATE]:
         # All text input during the final stages can potentially be handled by the same logic
         return await _handle_step5_cta_text_logic(update, context, current_state)
    elif current_state == STEP_5_REJECTION_WARNING_STATE:
         # Handle input after rejection warning (e.g., confirming cancel or proceeding to final chance)
         return await _handle_rejection_warning_response(update, context) # Needs implementation
    else:
        logger.warning(f"{log_prefix} Text input received in unexpected state {current_state}. Sending unknown.")
        await handle_unknown_message(update, context) # Use the handler from unknown.py
        return current_state # Stay in the current state

# --- Specific Logic Functions ---

async def _handle_step2_text_ack_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles 'OK' text confirmation after Step 2."""
    user = update.effective_user
    user_data = context.user_data
    chat_id = update.effective_chat.id
    secure_id = user_data.get("secure_id", "N/A")
    text = update.message.text.strip().lower()
    log_prefix = f"[Step 2 Ack Logic] User {user.id} (SecID: {secure_id}): "

    if user_data.get("step_2_failed"):
        logger.warning(f"{log_prefix}Step 2 previously failed. Ending conv.")
        await update.message.reply_text("`[SYS_ERR] Step 2 failed previously. /start again.`", parse_mode=ParseMode.MARKDOWN)
        user_data.clear(); return ConversationHandler.END

    if text in ["ok", "okay", "yes", "proceed", "continue", "review", "diagnostics"]: # Broader keywords
        logger.info(f"{log_prefix}Valid ack ('{text}'). Scheduling Step 3.")
        await update.message.reply_text(INPUT_CONFIRMATION_VALID_STEP2, parse_mode=ParseMode.MARKDOWN)

        # Schedule Step 3 Job (JobQueue check recommended inside scheduling function/step_1)
        if hasattr(context, "job_queue") and context.job_queue:
            job_data = {"chat_id": chat_id, "user_id": user.id}
            try:
                from handlers.step_3 import start_step_three_automation_job
                context.job_queue.run_once(start_step_three_automation_job, timedelta(seconds=1.0), data=job_data, name=f"step_3_start_{chat_id}")
                logger.info(f"{log_prefix}Scheduled Step 3 job. Transitioning state to AWAITING_STEP_FIVE_CHOICE.")
                 # ✅ Item 2 (from review): Return state expected AFTER Step 3 & 4 automation
                return AWAITING_STEP_FIVE_CHOICE
            except ImportError: logger.error(f"{log_prefix}Cannot schedule Step 3: handlers.step_3 missing.")
            except Exception as e: logger.error(f"{log_prefix}Error scheduling Step 3 job: {e}", exc_info=True)
            # If scheduling fails, send error and end
            await update.message.reply_text("`[SYS_ERR] Failed to schedule next phase. /start again.`")
            return ConversationHandler.END
        else: # JobQueue missing
            logger.error(f"{log_prefix}JobQueue unavailable. Cannot schedule Step 3.")
            await update.message.reply_text("`[CRITICAL_SYS_ERR] Cannot proceed. /start later.`")
            return ConversationHandler.END
    else: # Invalid input for this state
        logger.info(f"{log_prefix}Invalid ack input: '{text}'. Re-prompting.")
        button_text = BTN_TEXT_REVIEW_DIAGNOSTICS # Get button text
        await update.message.reply_text(
            INPUT_ERROR_INVALID_CONFIRMATION_STEP2.format(button_text=button_text),
            parse_mode=ParseMode.MARKDOWN
            # Consider re-sending button: reply_markup=InlineKeyboardMarkup(...)
        )
        return AWAITING_STEP_TWO_ACK # Stay in this state


async def _handle_step5_cta_text_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, current_state: int | None) -> int:
    """Handles various text inputs during the final CTA stages."""
    user = update.effective_user
    user_data = context.user_data
    chat_id = update.effective_chat.id
    secure_id = user_data.get("secure_id", "N/A")
    message_text = update.message.text.strip().lower()
    log_prefix = f"[Step 5 Text Logic] User {user.id} (SecID: {secure_id}, State: {current_state}): "

    # --- Timer Checks ---
    main_expired, main_time_left = get_formatted_time_left(user_data.get("step_4_countdown_start"), user_data.get("step_4_total_duration"))
    final_chance_expire_at = user_data.get("final_chance_expire_at")
    final_chance_expired, final_chance_time_left = (False, "N/A")
    if final_chance_expire_at:
        final_chance_expired, final_chance_time_left = get_formatted_time_left_from_deadline(final_chance_expire_at) # Assumes helper exists

    # Handle expiration conditions first
    if current_state == STEP_5_FINAL_CHANCE_STATE and final_chance_expired:
        logger.info(f"{log_prefix}Final chance expired before text input handled.")
        await update.message.reply_text("`[FINAL_CHANCE_EXPIRED] Override window closed. /start again.`", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    elif current_state != STEP_5_FINAL_CHANCE_STATE and main_expired:
        logger.info(f"{log_prefix}Main window expired before text input handled.")
        await update.message.reply_text("`[SESSION_EXPIRED] Sync window closed. /start again.`", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    logger.info(f"{log_prefix}Received text: '{message_text[:50]}...'")

    # --- Input Classification & Response ---
    response_text = ""
    button_template = BTN_TEXT_FINALIZE_SYNC_PRIMARY # Default button text
    button_callback = "final_sync_initiated"       # Default callback data
    next_state = STEP_5_AWAITING_FINAL_ACTION      # Default state to return/remain in

    # ✅ Item 3: A/B Test Button Text Example
    cta_variant = user_data.get("cta_variant", "A") # Get variant, default to A

    if message_text in ["ok", "okay", "yes", "sure", "ready", "proceed", "do it", "sync", "finalize"]:
        response_text = CTA_INPUT_VAGUE_POSITIVE_RESPONSE
        # Keep default button
    elif "$" in message_text or "49" in message_text or "cost" in message_text or "price" in message_text or "pay" in message_text:
        response_text = CTA_INPUT_HESITATION_PRICE_RESPONSE
        button_template = BTN_TEXT_ACTIVATE_SECURE_SYNC_AB_PRICE # Example: Use Price button for this query
        if cta_variant == "B" and 'BTN_TEXT_ACTIVATE_SECURE_SYNC_AB_PRICE_B' in globals(): # Check if B variant exists
             button_template = BTN_TEXT_ACTIVATE_SECURE_SYNC_AB_PRICE_B
    elif any(word in message_text for word in ["real", "legit", "scam", "proof", "what do i get", "benefit", "result"]):
        response_text = CTA_INPUT_HESITATION_BENEFIT_OR_LEGITIMACY_RESPONSE.format(secure_id=secure_id)
        button_template = BTN_TEXT_ACTIVATE_SECURE_SYNC_AB_PRICE # Example: Use Price button
        if cta_variant == "B" and 'BTN_TEXT_ACTIVATE_SECURE_SYNC_AB_PRICE_B' in globals():
             button_template = BTN_TEXT_ACTIVATE_SECURE_SYNC_AB_PRICE_B
    elif any(word in message_text for word in ["no", "stop", "leave", "exit", "cancel", "not paying", "don't want"]):
        # ✅ Item 2 Suggestion: Instead of directly offering final chance, transition to a warning state first.
        logger.info(f"{log_prefix}User indicated rejection. Transitioning to REJECTION_WARNING state.")
        # Send a specific prompt for this warning state (needs template in messages_en.py)
        warning_prompt = STEP_5_REJECTION_WARNING_PROMPT.format(time_left=main_time_left) # Example template
        # Buttons: Confirm Rejection (-> End Conv) / Reconsider (-> Final Chance State)
        warning_keyboard = InlineKeyboardMarkup(build_yes_no_buttons("confirm_reject", "reconsider_final_chance")) # Example util
        await update.message.reply_text(warning_prompt, reply_markup=warning_keyboard, parse_mode=ParseMode.MARKDOWN)
        return STEP_5_REJECTION_WARNING_STATE # Go to the new intermediate state
    else:
        # ✅ Item 4 Suggestion: More strategic unknown input response
        # Rotate through a few options or use a slightly more engaging one
        fallback_options = UNKNOWN_INPUT_FALLBACK_PROMPTS if 'UNKNOWN_INPUT_FALLBACK_PROMPTS' in globals() and UNKNOWN_INPUT_FALLBACK_PROMPTS else ["`[SYS] Input not recognized. Use button or confirm/query/decline.`"]
        response_text = random.choice(fallback_options)
        # Keep default button

    # Send the determined response and button (unless handled by rejection warning path)
    try:
        keyboard = InlineKeyboardMarkup(build_single_button_keyboard(button_template, button_callback))
        await update.message.reply_text(response_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"{log_prefix}Failed to send response for text input '{message_text}': {e}", exc_info=True)
        await update.message.reply_text("`[SYS_ERR] Error processing input. Use button or /cancel.`")

    return next_state # Return the determined next state (usually remain in STEP_5_AWAITING_FINAL_ACTION)


# --- Placeholder for the new Rejection Warning State Handler ---
async def _handle_rejection_warning_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Handles user response after the initial rejection warning."""
    # This function would be mapped to STEP_5_REJECTION_WARNING_STATE in main.py
    # It processes button clicks: "Confirm Reject" -> END, "Reconsider" -> Offer Final Chance & go to STEP_5_FINAL_CHANCE_STATE
    logger.warning(f"[Rejection Warning Handler] Logic to be implemented for user {update.effective_user.id}.")
    # Example:
    # query = update.callback_query
    # await query.answer()
    # if query.data == "confirm_reject":
    #     await query.edit_message_text("`[SESSION_TERMINATED_BY_USER]`")
    #     return ConversationHandler.END
    # elif query.data == "reconsider_final_chance":
    #     # Initiate final chance sequence (set timer, send message+button)
    #     # ... (logic similar to the original negative response path) ...
    #     return STEP_5_FINAL_CHANCE_STATE
    # else: # Handle unexpected callback data or text input in this state
    #     await context.bot.send_message(update.effective_chat.id, "`[SYS] Please use the provided buttons.`")
    #     return STEP_5_REJECTION_WARNING_STATE # Stay here
    return STEP_5_FINAL_CHANCE_STATE # Placeholder return


# It's recommended to keep the main routing logic (route_text_input) but have main.py
# register the specific _handle_*_logic functions directly to their corresponding states
# in ConversationHandler for maximum clarity and adherence to PTB patterns.
# For example, in main.py:
# states = {
#     AWAITING_STEP_TWO_ACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_step2_text_ack_logic)],
#     STEP_5_AWAITING_FINAL_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_step5_cta_text_logic)],
#     STEP_5_REJECTION_WARNING_STATE: [CallbackQueryHandler(_handle_rejection_warning_response)],
#     STEP_5_FINAL_CHANCE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_step5_cta_text_logic)] # Or a dedicated final chance handler
# }
