# utils/message_templates.py

# 消息模板，使用正确的 MarkdownV2 转义
MSG_STEP1_AUTH_CONFIRMED = (
    "🔷 \\[Z1\\-CORE\\_PROTOCOL\\_7\\] ACCESS GRANTED\n"
    "🔹 Primary Node: @AccessNodeIO\\_bot\n"
    "🔹 SECURE\\_ENCRYPTION\\_LAYER: ESTABLISHED"
)

MSG_STEP1_ID_SYNC_RISK = (
    "🔑 USER\\_SECURE\\_IDENTIFIER \\(USID\\): `{secure_id}`\n"
    "⚡️ AUTHENTICATION\\_SIGNATURE: VALIDATED & ACTIVE\n"
    "⏱️ SYSTEM\\_TIME\\_SYNCHRONIZED: `{formatted_current_time}`\n\n"
    "⚠️ CRITICAL\\_ALERT: Initial telemetry readings suggest potential quantum flux variance in your data stream\\. Integrity protocols triggered\\."
)

MSG_STEP1_SCAN_AUTONOMOUS = (
    "⚙️ NODE\\_INTEGRITY\\_PROTOCOL: ACTIVATING LEVEL\\-3 DIAGNOSTICS\n"
    "↳ Calibrating Deep\\-Resonance Trace Matrix for USID: `{secure_id}`\\.\\.\\.\n"
    "↳ Cross\\-Verifying Quantum Entanglement Signatures\\.\\.\\.\n\n"
    "**Automated diagnostic sequence auto\\-initiating\\.**\n"
    "SYSTEM\\_MODE: AUTONOMOUS\\_LOCKDOWN // User intervention countermanded\\."
)
