# utils/state_definitions.py

"""
State definitions for the Z1-Gray Telegram Bot's ConversationHandler.

This module centralizes all conversational states as integer constants,
ensuring consistency and ease of maintenance across the application.
The naming convention STEP_X_SPECIFIC_PURPOSE_STATE is used for clarity.

ConversationHandler.END is -1 (built-in)
ConversationHandler.TIMEOUT is -2 (built-in)
Custom states start from 0.
"""

# --- Step ①: SYSTEM INIT ---
# After the initial automated messages of Step ① are sent by `step_one_entry`,
# the bot transitions. If Step ②'s scan messages are also fully automated up to
# the point of user acknowledgement, the actual "waiting" state will be
# STEP_2_AWAITING_REVIEW_CHOICE_STATE.
# No specific "waiting" state is defined for *during* Step ①'s automated message delivery.
# `step_one_entry` in `handlers/step_1.py` will manage its internal flow and then
# return the next appropriate state (likely STEP_2_AWAITING_REVIEW_CHOICE_STATE
# after scheduling or sending Step 2's initial messages up to the prompt).

# --- Step ②: USER TRACE SCAN ---
# After Step ②'s automated scan messages are sent, the bot prompts the user
# to confirm if they wish to proceed with reviewing the detailed diagnostic report.
STEP_2_AWAITING_REVIEW_CHOICE_STATE = 0  # Awaiting user's "OK" or [REVIEW DIAGNOSTICS] button click.

# --- Step ③: DIAGNOSIS RESULT ---
# After the user confirms in Step ②, Step ③'s automated diagnostic messages are sent.
# If Step ④ (Access Lock) follows automatically after Step ③'s messages,
# then `handle_step_3_diagnosis` (or similar in `handlers/step_3.py`) would
# manage Step ③'s messages and then schedule Step ④, returning the next
# "waiting" state, which would be STEP_4_AWAITING_USER_DECISION_STATE.
# No specific "waiting" state is defined for *during* Step ③'s automated message delivery.

# --- Step ④: ACCESS LOCK ---
# After Step ④'s automated "Access Lock" messages (slots, countdown, risk) are sent,
# the bot presents two buttons: [OPTIMIZE & SECURE MY NODE] and [Query Protocol Necessity].
STEP_4_AWAITING_USER_DECISION_STATE = 1  # Awaiting user's click on one of the two action buttons.

# --- Step ⑤: SYNC CTA ---
# This state is entered if the user, after being presented with the buttons in Step ④,
# types text instead of clicking, or after specific button paths that lead to text input handling.
# It manages various user responses (positive, hesitant, negative) before the final CTA.
STEP_5_CTA_TEXT_INPUT_STATE = 2          # Handling varied text inputs before final sync confirmation.

# If the user explicitly rejects the offer during STEP_5_CTA_TEXT_INPUT_STATE,
# the bot offers a final, time-limited chance to proceed.
STEP_5_FINAL_CHANCE_STATE = 3            # Awaiting click on the "final chance" button or timeout.


# --- Optional: A list of all primary user-waiting states for potential programmatic use ---
# This can be useful for debugging, logging, or certain ConversationHandler configurations,
# though ConversationHandler's `states` dictionary is the primary definition source.
# Excludes states that are purely transitional or managed internally by automated sequences.
DEFINED_USER_INTERACTION_STATES = [
    STEP_2_AWAITING_REVIEW_CHOICE_STATE,
    STEP_4_AWAITING_USER_DECISION_STATE,
    STEP_5_CTA_TEXT_INPUT_STATE,
    STEP_5_FINAL_CHANCE_STATE,
]

# --- State Name Map ---
# A mapping from state integer values to their string names.
# This is crucial for logging in main.py and for general debugging.
# The keys are the state constants, and values are their string representations.
STATE_NAME_MAP = {
    STEP_2_AWAITING_REVIEW_CHOICE_STATE: "STEP_2_AWAITING_REVIEW_CHOICE_STATE",
    STEP_4_AWAITING_USER_DECISION_STATE: "STEP_4_AWAITING_USER_DECISION_STATE",
    STEP_5_CTA_TEXT_INPUT_STATE: "STEP_5_CTA_TEXT_INPUT_STATE",
    STEP_5_FINAL_CHANCE_STATE: "STEP_5_FINAL_CHANCE_STATE",
    # If you add more states above, remember to add them here as well.
    # Example for a hypothetical new state:
    # NEW_EXAMPLE_STATE : "NEW_EXAMPLE_STATE",
}

# Note on "Forbidden Input Stage" or "Allow Input Stage":
# These concepts are implemented by *how* handlers are defined for each
# specific state in `main.py`'s `ConversationHandler`.
# - If a state has no `MessageHandler(filters.TEXT, ...)` or only a very generic
#   "system busy" one, it effectively forbids meaningful text input.
# - If a state has specific `MessageHandler` or `CallbackQueryHandler` entries,
#   it explicitly allows and defines how to handle those inputs.
# Therefore, separate state constants for "FORBIDDEN_INPUT" are not strictly necessary
# at this definition level.

# Reminder: Do not include logging or other runtime logic in this definitions file.
# Its sole purpose is to provide a centralized, consistent set of state constants
# and the STATE_NAME_MAP.