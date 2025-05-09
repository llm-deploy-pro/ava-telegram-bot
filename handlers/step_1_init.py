from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler # 确保 ConversationHandler 被导入如果最终 start 是入口
from telegram.helpers import escape_markdown # 建议导入以备不时之需
from loguru import logger
from datetime import datetime, timedelta, timezone # 确保 timezone 被导入
# 假设您的 utils 模块按预期工作
from utils.helpers import generate_secure_id, get_formatted_utc_time
from utils.message_templates import MSG_STEP1_ID_SYNC_RISK, MSG_STEP1_SCAN_AUTONOMOUS # MSG_STEP1_AUTH_CONFIRMED 在下面重定义
from utils.state_definitions import AWAITING_STEP_2_SCAN_RESULTS

# 您在文件顶部重新定义并转义了 MSG_STEP1_AUTH_CONFIRMED，这是正确的。
# 确保所有在 message_templates.py 中的其他模板也做了必要的静态文本转义。
MSG_STEP1_AUTH_CONFIRMED = (
    "🔷 \\[Z1\\-CORE\\_PROTOCOL\\_7\\] ACCESS GRANTED\n"
    "🔹 Primary Node: @AccessNodeIO\\_bot\n" # 通常 @Username 不需要转义，但转义了也不会错
    "🔹 SECURE\\_ENCRYPTION\\_LAYER: ESTABLISHED"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Handles the /start command and initiates Step 1 sequence."""
    if not update.effective_user or not update.effective_chat:
        logger.warning("Received /start command with no effective user or chat.")
        # 根据您的 ConversationHandler 设计，可能需要返回 ConversationHandler.END
        # 或者一个特定的错误状态。如果这是一个独立的 CommandHandler，则可能不需要返回。
        # 假设这是 ConversationHandler 的入口，则需要返回一个状态或 END。
        return ConversationHandler.END 

    user = update.effective_user
    chat_id = update.effective_chat.id
    user_id_str = str(user.id) # 确保 user_id 是字符串类型，用于哈希和job name

    logger.info(f"/start command received from user {user_id_str} in chat {chat_id}")

    try:
        # 清理旧的会话数据 (确保幂等性)
        if 'secure_id' in context.user_data:
            logger.info(f"Clearing previous session data for user {user_id_str}")
            # 如果使用 PicklePersistence，这样清除是有效的
            context.user_data.pop('secure_id', None)
            context.user_data.pop('session_start_iso', None)
            # 如果有其他特定于会话的数据，也应在此清除

        # 生成 Secure ID
        secure_id = generate_secure_id(user_id_str) # helpers.py 中的函数
        context.user_data['secure_id'] = secure_id
        context.user_data['session_start_iso'] = datetime.now(timezone.utc).isoformat() # 使用带时区信息的时间

        logger.info(f"Generated Secure ID {secure_id} for user {user_id_str}")

        # 发送消息 1 (即时)
        await context.bot.send_message(
            chat_id=chat_id,
            text=MSG_STEP1_AUTH_CONFIRMED, # 已在文件顶部转义
            parse_mode='MarkdownV2'
        )
        logger.info(f"Sent MSG_STEP1_AUTH_CONFIRMED to user {user_id_str}")

        # 安排消息 2 (延迟 3.5 秒)
        context.job_queue.run_once(
            callback=send_message_2,
            when=timedelta(seconds=3.5),
            data={'chat_id': chat_id, 'secure_id': secure_id, 'user_id': user_id_str},
            name=f"msg2_for_{user_id_str}_{chat_id}" # 更唯一的 job name
        )
        logger.info(f"Scheduled MSG_STEP1_ID_SYNC_RISK for user {user_id_str}, delay 3.5s")

        # 安排消息 3 (总延迟 8.0 秒, 即消息2之后4.5秒)
        context.job_queue.run_once(
            callback=send_message_3,
            when=timedelta(seconds=8.0),
            data={'chat_id': chat_id, 'secure_id': secure_id, 'user_id': user_id_str},
            name=f"msg3_for_{user_id_str}_{chat_id}"
        )
        logger.info(f"Scheduled MSG_STEP1_SCAN_AUTONOMOUS for user {user_id_str}, delay 8.0s (4.5s after message 2)")

        # 安排 Step ② 逻辑触发 (总延迟 9.0 秒, 即消息3之后1秒)
        context.job_queue.run_once(
            callback=trigger_step_2_logic,
            when=timedelta(seconds=9.0),
            data={'chat_id': chat_id, 'secure_id': secure_id, 'user_id': user_id_str},
            name=f"step2_for_{user_id_str}_{chat_id}"
        )
        logger.info(f"Scheduled trigger_step_2_logic for user {user_id_str}, delay 9.0s (1.0s after message 3)")

        return AWAITING_STEP_2_SCAN_RESULTS # 返回下一个状态给 ConversationHandler

    except Exception as e:
        logger.error(f"Error in start handler for user {user_id_str}: {e}", exc_info=True)
        try:
            await context.bot.send_message(chat_id=chat_id, text="System initialization error. Please try again later.")
        except Exception as e_send:
             logger.error(f"Failed to send error message to user {user_id_str}: {e_send}")
        return ConversationHandler.END # 出错则结束会话

async def send_message_2(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job callback to send the second message of Step 1."""
    try:
        job_data = context.job.data
        chat_id = job_data['chat_id']
        secure_id = job_data['secure_id']
        user_id = job_data.get('user_id', 'unknown_in_msg2')
        
        logger.info(f"Executing send_message_2 for user {user_id}")
        
        formatted_current_time = get_formatted_utc_time() # helpers.py 中的函数
        
        # 假设 MSG_STEP1_ID_SYNC_RISK 模板中 {secure_id} 和 {formatted_current_time}
        # 是被 Markdown 代码块 `` ` `` 包围的，因此变量本身无需 escape_markdown。
        # 如果不是，并且变量内容可能包含特殊字符，则需要转义变量。
        message_text = MSG_STEP1_ID_SYNC_RISK.format(
            secure_id=secure_id, 
            formatted_current_time=formatted_current_time
        )
        
        await context.bot.send_message(chat_id=chat_id, text=message_text, parse_mode='MarkdownV2')
        logger.info(f"Sent MSG_STEP1_ID_SYNC_RISK to user {user_id}")
    except Exception as e:
        user_id_err = context.job.data.get('user_id', 'unknown_in_msg2_err') if context.job else 'unknown_job_in_msg2_err'
        logger.error(f"Error in send_message_2 for user {user_id_err}: {e}", exc_info=True)

async def send_message_3(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job callback to send the third message of Step 1."""
    try:
        job_data = context.job.data
        chat_id = job_data['chat_id']
        secure_id = job_data['secure_id']
        user_id = job_data.get('user_id', 'unknown_in_msg3')
        
        logger.info(f"Executing send_message_3 for user {user_id}")
        
        # 假设 MSG_STEP1_SCAN_AUTONOMOUS 模板中 {secure_id}
        # 是被 Markdown 代码块 `` ` `` 包围的。
        message_text = MSG_STEP1_SCAN_AUTONOMOUS.format(secure_id=secure_id)
        
        await context.bot.send_message(chat_id=chat_id, text=message_text, parse_mode='MarkdownV2')
        logger.info(f"Sent MSG_STEP1_SCAN_AUTONOMOUS to user {user_id}")
    except Exception as e:
        user_id_err = context.job.data.get('user_id', 'unknown_in_msg3_err') if context.job else 'unknown_job_in_msg3_err'
        logger.error(f"Error in send_message_3 for user {user_id_err}: {e}", exc_info=True)

async def trigger_step_2_logic(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job callback to trigger the logic for Step 2."""
    try:
        job_data = context.job.data
        chat_id = job_data['chat_id']
        secure_id = job_data['secure_id']
        user_id = job_data.get('user_id', 'unknown_in_step2_trigger')
        
        logger.info(f"Executing trigger_step_2_logic for user: {user_id}, Secure ID: {secure_id}")
        
        # --- 在这里实际调用 Step 2 的主处理函数或调度其 JobQueue ---
        # 例如:
        # from handlers.step_2_scan import schedule_step_2_messages # 假设函数名
        # await schedule_step_2_messages(context, chat_id, user_id, secure_id)
        # ---- 占位符 ----
        debug_message_text = "*调试信息*: Step 2 逻辑已触发，但尚未实现完整功能。"
        await context.bot.send_message(
            chat_id=chat_id, 
            text=debug_message_text,
            parse_mode='MarkdownV2' # 确保调试信息也遵循 Markdown 规范
        )
        logger.info(f"Placeholder for Step 2 logic executed for user {user_id}")
        # ----------------
    except Exception as e:
        user_id_err = context.job.data.get('user_id', 'unknown_in_step2_err') if context.job else 'unknown_job_in_step2_err'
        logger.error(f"Error in trigger_step_2_logic for user {user_id_err}: {e}", exc_info=True)

# 导出 handler (通常在 main.py 中构建 ConversationHandler 并使用此 start 函数作为入口)
start_handler = CommandHandler('start', start)