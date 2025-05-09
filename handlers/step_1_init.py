from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.helpers import escape_markdown
from loguru import logger
from datetime import datetime
from utils.helpers import generate_secure_id, get_formatted_utc_time
from utils.message_templates import MSG_STEP1_AUTH_CONFIRMED, MSG_STEP1_ID_SYNC_RISK, MSG_STEP1_SCAN_AUTONOMOUS
from utils.state_definitions import AWAITING_STEP_2_SCAN_RESULTS

# 修改消息 1 的内容
MSG_STEP1_AUTH_CONFIRMED = (
    "🔷 \\[Z1\\-CORE\\_PROTOCOL\\_7\\] ACCESS GRANTED\n"
    "🔹 Primary Node: @AccessNodeIO\\_bot\n"
    "🔹 SECURE\\_ENCRYPTION\\_LAYER: ESTABLISHED"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    try:
        # 清理旧的会话数据
        if 'secure_id' in context.user_data:
            del context.user_data['secure_id']
        if 'session_start_iso' in context.user_data:
            del context.user_data['session_start_iso']

        # 生成 Secure ID
        user_id = update.effective_user.id
        secure_id = generate_secure_id(user_id)
        context.user_data['secure_id'] = secure_id
        context.user_data['session_start_iso'] = datetime.utcnow().isoformat()

        # 发送消息 1
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=MSG_STEP1_AUTH_CONFIRMED,
            parse_mode='MarkdownV2'
        )

        # 安排消息 2
        context.job_queue.run_once(
            send_message_2,
            3.5,
            context={'chat_id': update.effective_chat.id, 'secure_id': secure_id}
        )

        # 安排消息 3
        context.job_queue.run_once(
            send_message_3,
            4.5,
            context={'chat_id': update.effective_chat.id, 'secure_id': secure_id}
        )

        # 安排 Step ②
        context.job_queue.run_once(
            trigger_step_2_logic,
            5.5,
            context={'chat_id': update.effective_chat.id, 'secure_id': secure_id}
        )

        logger.info(f"/start command received from user {user_id}, Secure ID generated: {secure_id}")

        return AWAITING_STEP_2_SCAN_RESULTS

    except Exception as e:
        logger.error(f"Error in start handler: {e}")

async def send_message_2(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        chat_id = context.job.context['chat_id']
        secure_id = context.job.context['secure_id']
        formatted_current_time = get_formatted_utc_time()
        
        # 无需转义，因为 secure_id 和 formatted_current_time 都在代码块内
        message = MSG_STEP1_ID_SYNC_RISK.format(
            secure_id=secure_id, 
            formatted_current_time=formatted_current_time
        )
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"Error sending message 2: {e}")

async def send_message_3(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        chat_id = context.job.context['chat_id']
        secure_id = context.job.context['secure_id']
        
        # 无需转义，因为 secure_id 在代码块内
        message = MSG_STEP1_SCAN_AUTONOMOUS.format(secure_id=secure_id)
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"Error sending message 3: {e}")

async def trigger_step_2_logic(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # 这里调用 Step ② 的主处理函数
        pass
    except Exception as e:
        logger.error(f"Error triggering step 2 logic: {e}")

# 注册命令处理程序
start_handler = CommandHandler('start', start)
