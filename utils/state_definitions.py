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
# (Comments as before)

# --- Step ②: USER TRACE SCAN ---
STEP_2_AWAITING_REVIEW_CHOICE_STATE = 0  # Awaiting user's "OK" or [REVIEW DIAGNOSTICS] button click.

# --- Step ③: DIAGNOSIS RESULT ---
# (Comments as before)
# Note: No specific state defined for Step 3 in your current active states.
# If AWAITING_STEP_THREE_ACK was meant for something else, adjust accordingly.

# --- Step ④: ACCESS LOCK ---
STEP_4_AWAITING_USER_DECISION_STATE = 1  # Awaiting user's click on one of the two action buttons.

# --- Step ⑤: SYNC CTA ---
STEP_5_CTA_TEXT_INPUT_STATE = 2          # Handling varied text inputs before final sync confirmation.
STEP_5_FINAL_CHANCE_STATE = 3            # Awaiting click on the "final chance" button or timeout.


# --- Optional: A list of all primary user-waiting states for potential programmatic use ---
DEFINED_USER_INTERACTION_STATES = [
    STEP_2_AWAITING_REVIEW_CHOICE_STATE,
    STEP_4_AWAITING_USER_DECISION_STATE,
    STEP_5_CTA_TEXT_INPUT_STATE,
    STEP_5_FINAL_CHANCE_STATE,
]

# --- State Name Map ---
STATE_NAME_MAP = {
    STEP_2_AWAITING_REVIEW_CHOICE_STATE: "STEP_2_AWAITING_REVIEW_CHOICE_STATE",
    STEP_4_AWAITING_USER_DECISION_STATE: "STEP_4_AWAITING_USER_DECISION_STATE",
    STEP_5_CTA_TEXT_INPUT_STATE: "STEP_5_CTA_TEXT_INPUT_STATE",
    STEP_5_FINAL_CHANCE_STATE: "STEP_5_FINAL_CHANCE_STATE",
}

# --- Optional Aliases for Backward Compatibility or common references in main.py fallbacks ---
# This helps if main.py accidentally uses old fallback names after a failed import,
# or if parts of main.py were not fully updated to new state names.
AWAITING_STEP_TWO_ACK = STEP_2_AWAITING_REVIEW_CHOICE_STATE

# Regarding AWAITING_STEP_THREE_ACK:
# Your original fallback in main.py mapped it to 1, which is STEP_4_AWAITING_USER_DECISION_STATE.
# If there's no distinct "Step 3 waiting state", this alias might be confusing.
# Let's assume for now it was intended to map to a state that's effectively Step 4's waiting point.
# Or, if you have a conceptual Step 3 waiting point that maps to STEP_4_AWAITING_USER_DECISION_STATE,
# this alias could reflect that.
# If AWAITING_STEP_THREE_ACK is truly unused or its mapping is unclear, you can omit this alias.
# For completeness based on the prompt's suggestion:
# AWAITING_STEP_THREE_ACK = STEP_4_AWAITING_USER_DECISION_STATE # Or map to a different state if Step 3 has its own constant
# ^^^ 注意：这一行目前是注释掉的，因为 STEP_4_AWAITING_USER_DECISION_STATE 已经是 1，
# 如果你需要一个独立的 AWAITING_STEP_THREE_ACK 并且它也等于 1，那没问题。
# 但如果它有其他含义，或者你没有实际的“等待步骤三确认”的状态，最好明确。
# 如果只是为了让 main.py 的 fallback 不报错，可以暂时这样。

# Your original main.py fallback also had:
# AWAITING_STEP_FIVE_CHOICE (mapped to 2, which is STEP_5_CTA_TEXT_INPUT_STATE)
# STEP_5_AWAITING_FINAL_ACTION (mapped to 3, which is STEP_5_FINAL_CHANCE_STATE)
# If these old names might still be referenced, add aliases:
AWAITING_STEP_FIVE_CHOICE = STEP_5_CTA_TEXT_INPUT_STATE
STEP_5_AWAITING_FINAL_ACTION = STEP_5_FINAL_CHANCE_STATE


# Note on "Forbidden Input Stage" or "Allow Input Stage":
# (Comments as before)

# Reminder: Do not include logging or other runtime logic in this definitions file.
# Its sole purpose is to provide a centralized, consistent set of state constants
# and the STATE_NAME_MAP.