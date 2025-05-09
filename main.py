import asyncio
import os
import signal
import traceback
from datetime import timedelta # 用于 JobQueue 示例

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    PicklePersistence,
    MessageHandler,
    filters,
    ConversationHandler # 导入 ConversationHandler
)
from dotenv import load_dotenv

# --- 导入您的模块 ---
# 确保这些路径和模块名与您的项目结构一致
from handlers.step_1_init import start_handler # 核心 ConversationHandler
# from handlers.common_handlers import cancel_handler, unknown_command_handler # 如果有单独的通用handler
from utils.logger_config import logger
from utils import state_definitions # 假设状态在这里定义
# from utils import message_templates # 如果直接在 main 中用到
# from utils import helpers # 如果直接在 main 中用到

# --- 全局变量 ---
shutdown_event = asyncio.Event()

# --- 加载环境变量 ---
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
# 是否使用 polling 模式 (本地开发通常使用 polling)
USE_POLLING = os.getenv('USE_POLLING', 'false').lower() == 'true'
WEBHOOK_URL = os.getenv('WEBHOOK_URL') # Render 会提供这个 URL
WEBHOOK_PATH = os.getenv('WEBHOOK_PATH', '/webhook')
PORT = int(os.getenv('PORT', '10000')) # Render 通常使用 10000，本地测试可以是 8080, 8443 等
PERSISTENCE_FILEPATH = os.getenv('PERSISTENCE_PATH', 'bot_data.pkl')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID') # 可选，用于发送重要通知

# --- Webhook 路径配置 ---
if WEBHOOK_PATH and WEBHOOK_PATH.startswith('/'):
    WEBHOOK_PATH = WEBHOOK_PATH
elif WEBHOOK_PATH:
    WEBHOOK_PATH = f"/{WEBHOOK_PATH}"
else:
    # 强烈建议在 .env 或 Render 环境变量中明确设置 WEBHOOK_PATH
    # 避免使用基于 BOT_TOKEN 的路径，因为它可能在日志中暴露部分 Token
    WEBHOOK_PATH = "/telegram_webhook_z1g_secure" # 使用一个固定的、独特的路径
    logger.warning(f"WEBHOOK_PATH not set in environment, using default: {WEBHOOK_PATH}")

# --- 启动前检查 ---
if not BOT_TOKEN:
    logger.critical("错误: BOT_TOKEN 环境变量未设置")
    exit(1)
if not USE_POLLING and not WEBHOOK_URL:
    logger.critical("错误: 使用 webhook 模式时必须设置 WEBHOOK_URL 环境变量")
    exit(1)

logger.info(f"BOT_TOKEN 已加载，结尾为: ...{BOT_TOKEN[-4:]}")
logger.info(f"运行模式: {'轮询模式 (polling)' if USE_POLLING else '网络钩子模式 (webhook)'}")
if not USE_POLLING:
    logger.info(f"Webhook URL: {WEBHOOK_URL}")
    logger.info(f"Webhook 路径: {WEBHOOK_PATH}")
    logger.info(f"监听端口: {PORT}")
logger.info(f"持久化文件路径: {PERSISTENCE_FILEPATH}")
if ADMIN_CHAT_ID:
    logger.info(f"Admin chat ID for notifications: {ADMIN_CHAT_ID}")


# --- 通用 Handler 函数 (如果您的 ConversationHandler 没有覆盖这些) ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """取消当前操作并重置会话"""
    user = update.effective_user
    logger.info(f"用户 {user.id if user else '未知'} 触发了 /cancel 命令")
    
    if update.message:
        await update.message.reply_text(
            "操作已取消。您的会话已重置。\n发送 /start 开始新的会话。"
        )
    
    return ConversationHandler.END

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理未知命令"""
    if update.message:
        logger.warning(f"收到未知命令: {update.message.text} 来自用户 {update.effective_user.id if update.effective_user else '未知'}")
        await update.message.reply_text("抱歉，我不理解这个命令。请使用 /start 或其他可用命令。")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理更新过程中的错误"""
    logger.error(f"处理更新时发生异常: {context.error}", exc_info=context.error)
    
    # 可选：向用户发送消息
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="抱歉，系统出现了意外错误。请稍后再试。"
            )
        except Exception as e:
            logger.error(f"向用户 {update.effective_chat.id} 发送错误消息失败: {e}")

    # Optionally, send a detailed error to the admin
    if ADMIN_CHAT_ID:
        try:
            error_details = f"Error for update {update}:\n<pre>{context.error}</pre>"
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=error_details, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send detailed error to admin: {e}")

# --- Webhook 设置回调 (post_init) ---
async def post_init_webhook_setup(application: Application) -> None:
    """在应用程序初始化后设置 webhook"""
    if USE_POLLING:
        # 在轮询模式下，移除现有的 webhook
        logger.info("轮询模式启用：移除所有现有的 webhook")
        try:
            await application.bot.delete_webhook(drop_pending_updates=True)
            logger.info("已成功移除 webhook 以使用轮询模式")
        except Exception as e:
            logger.error(f"移除 webhook 失败: {e}")
        return

    # webhook 模式设置
    full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    logger.info(f"正在设置 webhook 到: {full_webhook_url}")
    
    try:
        await application.bot.set_webhook(
            url=full_webhook_url,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        webhook_info = await application.bot.get_webhook_info()
        if webhook_info.url == full_webhook_url:
            logger.info(f"Webhook 设置成功: {webhook_info.url}")
            if ADMIN_CHAT_ID:
                 await application.bot.send_message(ADMIN_CHAT_ID, f"✅ Z1-Gray Bot (Webhook) is online!\nURL: {webhook_info.url}")
        else:
            warning_msg = (
                f"Webhook set, but URL mismatch or issue.\n"
                f"Expected: {full_webhook_url}\n"
                f"Got: {webhook_info.url if webhook_info else 'No info'}\n"
                f"Info object: {webhook_info}"
            )
            logger.warning(warning_msg)
            if ADMIN_CHAT_ID:
                await application.bot.send_message(ADMIN_CHAT_ID, f"⚠️ Z1-Gray Bot Webhook Warning:\n{warning_msg}")

    except Exception as e:
        error_msg = f"CRITICAL: Failed to set webhook: {e}"
        logger.critical(error_msg, exc_info=True)
        if ADMIN_CHAT_ID:
            try:
                await application.bot.send_message(ADMIN_CHAT_ID, error_msg)
            except Exception as admin_e:
                logger.error(f"Failed to send webhook setup CRITICAL error to admin: {admin_e}")
        # Consider a more robust notification or fallback if webhook setup fails critically

# --- 优雅停机处理 ---
def signal_handler(signum, frame):
    logger.info(f"收到信号 {signal.Signals(signum).name}。正在初始化优雅关闭...")
    shutdown_event.set()

async def main() -> None:
    """运行 Bot"""
    logger.info(f"正在启动 Z1-Gray Bot ({('轮询模式' if USE_POLLING else 'Webhook 模式')})...")

    # 设置持久化
    try:
        # Render.com 默认情况下文件系统是短暂的，除非配置了持久磁盘。
        # 如果没有持久磁盘，PicklePersistence 的数据会在重启/重新部署后丢失。
        persistence = PicklePersistence(filepath=PERSISTENCE_FILEPATH)
        logger.info(f"PicklePersistence 将使用文件: {PERSISTENCE_FILEPATH}")
    except Exception as e:
        logger.error(f"Failed to initialize PicklePersistence: {e}. Persistence will be disabled.", exc_info=True)
        persistence = None

    # 初始化应用程序构建器
    builder = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init_webhook_setup)
    if persistence:
        builder = builder.persistence(persistence)
    
    application = builder.build()

    # 注册错误处理器 (必须尽早注册)
    application.add_error_handler(error_handler)

    # --- 注册您的核心 ConversationHandler ---
    # 确保 `start_handler` 是您项目中实际的、配置好的 ConversationHandler 实例
    if 'start_handler' in globals() and isinstance(start_handler, CommandHandler):
        application.add_handler(start_handler)
        logger.info("已添加主会话处理程序 (start_handler)")
    else:
        # 如果 start_handler 未正确导入或不是 ConversationHandler，Bot 的核心逻辑会缺失
        logger.error("错误: start_handler 不是有效的处理程序或未正确导入")
        # 作为备用，可以添加一个简单的 /start
        async def basic_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("基础启动。对话流程未加载。")
        application.add_handler(CommandHandler("start", basic_start))
        logger.info("已添加备用基础 /start 处理程序")

    # --- 注册其他全局 Handlers (如果需要且未被 ConversationHandler 覆盖) ---
    # 全局 /cancel 通常应由 ConversationHandler 的 fallbacks 处理
    application.add_handler(CommandHandler("cancel", cancel))
    logger.info("已添加全局 /cancel 处理程序")

    # 处理所有其他未匹配的命令
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    logger.info("已添加未知命令处理程序")

    # --- 初始化和启动应用组件 ---
    try:
        await application.initialize() # 初始化 handlers, etc.
        await application.start()      # 启动 JobQueue 等后台任务
                                   # post_init (set_webhook) 会在这里之后执行

        # 根据模式启动 polling 或 webhook
        if USE_POLLING:
            logger.info("使用轮询模式进行本地开发")
            await application.updater.start_polling(drop_pending_updates=True)
            logger.info("Bot 已成功开始轮询。按 Ctrl+C 停止。")
        else:
            # --- 启动内置 Webhook 服务器 ---
            # url_path 传递给 start_webhook 时不应包含前导 '/'
            clean_webhook_path = WEBHOOK_PATH.lstrip('/')
            logger.info(f"正在启动本地 webhook HTTP 服务器，监听 0.0.0.0:{PORT} 路径 '/{clean_webhook_path}'")
            
            await application.updater.start_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=clean_webhook_path
            )
            logger.info(f"Webhook HTTP 服务器已启动。Bot 应该可以在 {WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH} 接收更新")

    except Exception as e:
        logger.critical(f"启动应用程序时发生严重错误: {e}", exc_info=True)
        if ADMIN_CHAT_ID:
            try:
                await application.bot.send_message(ADMIN_CHAT_ID, f"🚨 Z1-Gray Bot CRITICAL STARTUP FAILURE: {e}")
            except Exception as admin_e:
                logger.error(f"Failed to send CRITICAL STARTUP FAILURE to admin: {admin_e}")
        # 尝试优雅关闭
        await application.stop()
        await application.shutdown()
        return # 关键错误，直接退出

    # --- 等待停机信号 ---
    await shutdown_event.wait()

    # --- 优雅停机 ---
    logger.info("正在优雅关闭 Bot...")
    try:
        if application.updater and hasattr(application.updater, 'running') and application.updater.running: # 检查 updater 是否存在且在运行
            await application.updater.stop() # 停止 webhook 服务器或 polling
        await application.stop()         # 停止 JobQueue 等
        await application.shutdown()     # 清理 PTB 资源
    except Exception as e:
        logger.error(f"Bot 关闭过程中发生错误: {e}", exc_info=True)
    finally:
        logger.info("Bot 关闭序列完成")


if __name__ == '__main__':
    # 设置信号处理器
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    except ValueError:
        logger.warning("无法设置信号处理器。通过信号进行优雅关闭可能无法工作。")

    print("正在启动 Bot...")
    try:
        print("运行主函数...")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("进程被用户或系统终止")
        logger.info("进程被用户或系统终止")
    except Exception as e:
        print(f"未处理的异常: {e}")
        print(f"追踪信息: {traceback.format_exc()}")
        logger.critical(f"主异步循环中未处理的异常: {e}")
        logger.critical(f"错误追踪信息: {traceback.format_exc()}")
    finally:
        logger.info("应用程序退出")