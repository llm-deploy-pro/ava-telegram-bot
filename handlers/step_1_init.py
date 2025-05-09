from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.helpers import escape_markdown
from loguru import logger
from datetime import datetime, timedelta
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
        chat_id = update.effective_chat.id
        secure_id = generate_secure_id(user_id)
        context.user_data['secure_id'] = secure_id
        context.user_data['session_start_iso'] = datetime.utcnow().isoformat()

        # 发送消息 1
        await context.bot.send_message(
            chat_id=chat_id,
            text=MSG_STEP1_AUTH_CONFIRMED,
            parse_mode='MarkdownV2'
        )
        
        logger.info(f"已发送第一条消息给用户 {user_id}，开始安排延迟消息")

        # 安排消息 2 - 使用秒数而不是浮点数，并确保添加正确的数据和回调名称
        context.job_queue.run_once(
            callback=send_message_2,
            when=timedelta(seconds=3.5),
            data={'chat_id': chat_id, 'secure_id': secure_id, 'user_id': user_id},
            name=f"msg2_for_{user_id}"
        )
        
        logger.info(f"已安排消息2，延迟3.5秒")

        # 安排消息 3 - 同样修改参数
        context.job_queue.run_once(
            callback=send_message_3,
            when=timedelta(seconds=4.5),
            data={'chat_id': chat_id, 'secure_id': secure_id, 'user_id': user_id},
            name=f"msg3_for_{user_id}"
        )
        
        logger.info(f"已安排消息3，延迟4.5秒")

        # 安排 Step ② - 同样修改参数
        context.job_queue.run_once(
            callback=trigger_step_2_logic,
            when=timedelta(seconds=5.5),
            data={'chat_id': chat_id, 'secure_id': secure_id, 'user_id': user_id},
            name=f"step2_for_{user_id}"
        )
        
        logger.info(f"已安排Step2逻辑，延迟5.5秒")

        logger.info(f"/start command received from user {user_id}, Secure ID generated: {secure_id}")

        return AWAITING_STEP_2_SCAN_RESULTS

    except Exception as e:
        logger.error(f"Error in start handler: {e}")

async def send_message_2(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # 从job.data中获取数据（不是job.context）
        job_data = context.job.data
        chat_id = job_data['chat_id']
        secure_id = job_data['secure_id']
        user_id = job_data.get('user_id', 'unknown')
        
        logger.info(f"正在发送消息2给用户 {user_id}")
        
        formatted_current_time = get_formatted_utc_time()
        
        # 无需转义，因为 secure_id 和 formatted_current_time 都在代码块内
        message = MSG_STEP1_ID_SYNC_RISK.format(
            secure_id=secure_id, 
            formatted_current_time=formatted_current_time
        )
        
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='MarkdownV2')
        logger.info(f"消息2已发送给用户 {user_id}")
    except Exception as e:
        logger.error(f"Error sending message 2: {e}", exc_info=True)

async def send_message_3(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # 同样修改数据获取方式
        job_data = context.job.data
        chat_id = job_data['chat_id']
        secure_id = job_data['secure_id']
        user_id = job_data.get('user_id', 'unknown')
        
        logger.info(f"正在发送消息3给用户 {user_id}")
        
        # 无需转义，因为 secure_id 在代码块内
        message = MSG_STEP1_SCAN_AUTONOMOUS.format(secure_id=secure_id)
        
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='MarkdownV2')
        logger.info(f"消息3已发送给用户 {user_id}")
    except Exception as e:
        logger.error(f"Error sending message 3: {e}", exc_info=True)

async def trigger_step_2_logic(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # 同样修改数据获取方式
        job_data = context.job.data
        chat_id = job_data['chat_id']
        secure_id = job_data['secure_id']
        user_id = job_data.get('user_id', 'unknown')
        
        logger.info(f"触发Step 2逻辑，用户: {user_id}，Secure ID: {secure_id}")
        
        # 这里调用 Step ② 的主处理函数
        # 目前只是日志记录，后续可以扩展
        await context.bot.send_message(
            chat_id=chat_id, 
            text="*调试信息*: Step 2 逻辑已触发，但尚未实现完整功能。",
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Error triggering step 2 logic: {e}", exc_info=True)

# 注册命令处理程序
start_handler = CommandHandler('start', start)
