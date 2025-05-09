# utils/state_definitions.py

"""
State definitions for the Z1-Gray Telegram Bot's ConversationHandler.

This module centralizes all conversational states, ensuring consistency 
and ease of maintenance across the application.
"""

# --- 字符串形式的状态定义 (用于向后兼容) ---
AWAITING_STEP_2_SCAN_RESULTS = "AWAITING_STEP_2_SCAN_RESULTS"
AWAITING_STEP_2_ACK = "AWAITING_STEP_2_ACK"
AWAITING_STEP_3_CONFIRMATION = "AWAITING_STEP_3_CONFIRMATION"
AWAITING_STEP_4_DECISION = "AWAITING_STEP_4_DECISION"
AWAITING_FINAL_PAYMENT = "AWAITING_FINAL_PAYMENT"

# --- 整数形式的状态定义 (用于 ConversationHandler) ---
# ConversationHandler.END is -1 (built-in)
# ConversationHandler.TIMEOUT is -2 (built-in)
# Custom states start from 0.

# --- Step ②: USER TRACE SCAN ---
STEP_2_AWAITING_REVIEW_CHOICE_STATE = 0  # Awaiting user's "OK" or [REVIEW DIAGNOSTICS] button click.

# --- Step ④: ACCESS LOCK ---
STEP_4_AWAITING_USER_DECISION_STATE = 1  # Awaiting user's click on one of the two action buttons.

# --- Step ⑤: SYNC CTA ---
STEP_5_CTA_TEXT_INPUT_STATE = 2          # Handling varied text inputs before final sync confirmation.
STEP_5_FINAL_CHANCE_STATE = 3            # Awaiting click on the "final chance" button or timeout.

# --- 所有主要用户等待状态的列表 ---
DEFINED_USER_INTERACTION_STATES = [
    STEP_2_AWAITING_REVIEW_CHOICE_STATE,
    STEP_4_AWAITING_USER_DECISION_STATE,
    STEP_5_CTA_TEXT_INPUT_STATE,
    STEP_5_FINAL_CHANCE_STATE,
]

# --- 状态名称映射 ---
STATE_NAME_MAP = {
    STEP_2_AWAITING_REVIEW_CHOICE_STATE: "STEP_2_AWAITING_REVIEW_CHOICE_STATE",
    STEP_4_AWAITING_USER_DECISION_STATE: "STEP_4_AWAITING_USER_DECISION_STATE",
    STEP_5_CTA_TEXT_INPUT_STATE: "STEP_5_CTA_TEXT_INPUT_STATE",
    STEP_5_FINAL_CHANCE_STATE: "STEP_5_FINAL_CHANCE_STATE",
}

# --- 向后兼容的别名 ---
AWAITING_STEP_TWO_ACK = STEP_2_AWAITING_REVIEW_CHOICE_STATE
AWAITING_STEP_FIVE_CHOICE = STEP_5_CTA_TEXT_INPUT_STATE
STEP_5_AWAITING_FINAL_ACTION = STEP_5_FINAL_CHANCE_STATE
