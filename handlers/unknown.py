# handlers/unknown.py

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler # ConversationHandler for state check example
from telegram.constants import ParseMode

# It's good practice to define message templates centrally,
# possibly in templates/messages_en.py or a dedicated error_messages.py.
# For this example, they are defined here for clarity of this module's function.

# System response for unrecognized text input during a conversation flow
UNKNOWN_TEXT_RESPONSE_TEMPLATE = (
    "`[SYSTEM_NOTICE // INPUT_UNRECOGNIZED]`\n"
    "`Current protocol sequence does not process this type of input.`\n"
    "▶ `Please follow on-screen instructions or use available buttons.`\n"
    "▶ `If stuck, you may type /cancel to reset the protocol sequence.`"
)

# System response for unrecognized or outdated callback query (button press)
UNKNOWN_CALLBACK_RESPONSE_TEMPLATE = (
    "`[SYSTEM_ALERT // CALLBACK_INVALID]`\n"
    "`The interactive element you selected is no longer active or is not valid `\n"
    "`for the current stage of the protocol.`\n"
    "▶ `Please refer to the latest system messages for active options.`\n"
    "▶ `Alternatively, type /start to re-initialize the access protocol.`"
)

logger = logging.getLogger(__name__)

def _get_current_conversation_state_for_log(context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Helper function to attempt to retrieve the current ConversationHandler state for logging.
    This is a best-effort approach and might need adjustment based on how states are stored
    or if multiple ConversationHandlers are in use.
    """
    state_key_for_log = "UnknownOrNoConversationState"
    try:
        # This assumes a single, named ConversationHandler or that the state is stored
        # in user_data under a predictable key by the ConversationHandler.
        # If you named your ConversationHandler (e.g., name="z1_gray_funnel"),
        # PTB might store its state in context.user_data[(<handler_name_tuple>, )]
        # or context.chat_data for per_chat conversations.
        # A simpler, though less direct, way is if your handlers themselves update a known
        # user_data key with the current state for logging/debugging.
        if context.user_data and isinstance(context.user_data.get(ConversationHandler.STATE), (int, str)): # Check if state exists and is of expected type
            raw_state = context.user_data.get(ConversationHandler.STATE)
            # You might have a mapping from integer states to string names in state_definitions.py
            # For now, just log the raw state if it's simple.
            state_key_for_log = str(raw_state)
        # If you have a list of all states in state_definitions, you could try to find the name:
        # from utils.state_definitions import DEFINED_USER_INTERACTION_STATES, ALL_STATES_MAP (hypothetical map)
        # if raw_state in ALL_STATES_MAP: state_key_for_log = ALL_STATES_MAP[raw_state]

    except Exception:
        logger.debug("Could not reliably determine current conversation state for unknown input log.", exc_info=False)
    return state_key_for_log


async def handle_unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles text messages that are not caught by more specific handlers
    within a ConversationHandler's states or fallbacks (if this is used as a CH fallback).
    """
    user = update.effective_user
    if not user or not update.message or not update.message.text:
        logger.warning("[UNKNOWN TEXT HANDLER] Received an update without user or message text.")
        return

    current_conv_state = _get_current_conversation_state_for_log(context)
    logger.warning(
        f"[UNKNOWN_TEXT_INPUT] User {user.id} (@{user.username if user.username else 'N/A'}) "
        f"sent unexpected text in conv_state '{current_conv_state}': {update.message.text[:100]!r}" # Log first 100 chars
    )

    try:
        await update.message.reply_text(
            UNKNOWN_TEXT_RESPONSE_TEMPLATE,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        logger.error(
            f"Failed to send UNKNOWN_TEXT_RESPONSE to user {user.id}. Error: {e}",
            exc_info=True
        )


async def handle_unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles callback queries (button presses) that are not caught by more specific
    CallbackQueryHandlers within a ConversationHandler's states or fallbacks.
    """
    query = update.callback_query
    user = update.effective_user

    if not query or not user:
        logger.warning("[UNKNOWN CALLBACK HANDLER] Received an update without query or user.")
        if query: await query.answer("Error: Invalid request.", show_alert=True) # Answer to stop loading
        return

    current_conv_state = _get_current_conversation_state_for_log(context)
    callback_data_preview = query.data[:50] if query.data else "N/A" # Preview of callback data

    logger.warning(
        f"[UNKNOWN_CALLBACK_QUERY] User {user.id} (@{user.username if user.username else 'N/A'}) "
        f"triggered unknown callback in conv_state '{current_conv_state}': {callback_data_preview!r}"
    )

    try:
        await query.answer()  # Crucial: Always answer the callback query to stop the loading icon.
        if query.message: # Check if the original message still exists
            await query.edit_message_text(
                text=UNKNOWN_CALLBACK_RESPONSE_TEMPLATE,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else: # If original message is gone, try sending a new message
            await context.bot.send_message(
                chat_id=user.id, # Send to user directly
                text=UNKNOWN_CALLBACK_RESPONSE_TEMPLATE,
                parse_mode=ParseMode.MARKDOWN_V2
            )
    except Exception as e:
        logger.error(
            f"Failed to send/edit UNKNOWN_CALLBACK_RESPONSE for user {user.id} (callback: {callback_data_preview!r}). Error: {e}",
            exc_info=True
        )
        # Even if sending message fails, ensure the callback was answered if possible.
        if not query._answered: # Check if query was answered before exception
            try:
                await query.answer("System error processing this action.", show_alert=True)
            except Exception as final_answer_e:
                logger.error(f"Failed to even answer unknown callback query after error: {final_answer_e}")

# Note: How these handlers are registered in main.py (e.g., in ConversationHandler.fallbacks
# or as lower-priority global handlers) will determine their exact scope and when they trigger.
# For ConversationHandler, they are excellent as fallbacks.
