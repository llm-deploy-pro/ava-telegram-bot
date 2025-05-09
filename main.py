import asyncio
import os
import signal
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
WEBHOOK_PATH_ENV = os.getenv('WEBHOOK_PATH') # 例如 "/your_secret_webhook_path"
PORT = int(os.getenv('PORT', '10000')) # Render 通常使用 10000，本地测试可以是 8080, 8443 等
PERSISTENCE_FILEPATH = os.getenv('PERSISTENCE_PATH', 'bot_data.pkl')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID') # 可选，用于发送重要通知

# --- Webhook 路径配置 ---
if WEBHOOK_PATH_ENV and WEBHOOK_PATH_ENV.startswith('/'):
    WEBHOOK_PATH = WEBHOOK_PATH_ENV
elif WEBHOOK_PATH_ENV:
    WEBHOOK_PATH = f"/{WEBHOOK_PATH_ENV}"
else:
    # 强烈建议在 .env 或 Render 环境变量中明确设置 WEBHOOK_PATH
    # 避免使用基于 BOT_TOKEN 的路径，因为它可能在日志中暴露部分 Token
    WEBHOOK_PATH = "/telegram_webhook_z1g_secure" # 使用一个固定的、独特的路径
    logger.warning(f"WEBHOOK_PATH not set in environment, using default: {WEBHOOK_PATH}")

# --- 启动前检查 ---
if not BOT_TOKEN:
    logger.critical("FATAL: BOT_TOKEN not found in environment variables.")
    exit(1)
if not USE_POLLING and not WEBHOOK_URL:
    logger.critical("FATAL: WEBHOOK_URL not found. Required for Webhook mode.")
    exit(1)

logger.info(f"BOT_TOKEN loaded, ends with: ...{BOT_TOKEN[-4:]}")
if USE_POLLING:
    logger.info("Running in POLLING mode (for local development)")
else:
    logger.info(f"Running in WEBHOOK mode with URL: {WEBHOOK_URL}")
    logger.info(f"Webhook path to be used: {WEBHOOK_PATH}")
    logger.info(f"Application will listen on PORT: {PORT}")
logger.info(f"Persistence filepath: {PERSISTENCE_FILEPATH}")
if ADMIN_CHAT_ID:
    logger.info(f"Admin chat ID for notifications: {ADMIN_CHAT_ID}")


# --- 通用 Handler 函数 (如果您的 ConversationHandler 没有覆盖这些) ---
async def global_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Global cancel command if not part of a conversation or as a final fallback."""
    user = update.effective_user
    logger.info(f"User {user.id if user else 'Unknown'} triggered global /cancel.")
    if update.message:
        await update.message.reply_text(
            "Operation cancelled. Your session (if any) has been reset.\n"
            "Send /start to begin a new session."
        )
    # 对于全局 cancel，很难知道它是否应该结束一个 ConversationHandler
    # 通常 ConversationHandler 内部的 cancel 是最佳实践
    return ConversationHandler.END # 假设这是被用作 ConversationHandler 的 fallback

async def unknown_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles unknown commands not caught by other handlers."""
    if update.message:
        logger.warning(f"Unknown command received: {update.message.text} from user {update.effective_user.id if update.effective_user else 'Unknown'}")
        await update.message.reply_text("Sorry, I didn't understand that command. Please use /start or other available commands.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates and send a user-friendly message."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    # Optionally, send a message to the user
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, an unexpected error occurred on our side. Please try again in a moment."
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user {update.effective_chat.id}: {e}")

    # Optionally, send a detailed error to the admin
    if ADMIN_CHAT_ID:
        try:
            error_details = f"Error for update {update}:\n<pre>{context.error}</pre>"
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=error_details, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send detailed error to admin: {e}")

# --- Webhook 设置回调 (post_init) ---
async def post_init_webhook_setup(application: Application) -> None:
    """Sets the webhook after the application has been initialized."""
    if USE_POLLING:
        # 在 polling 模式下，确保删除任何现有的 webhook
        logger.info("Polling mode active: removing any existing webhook...")
        try:
            await application.bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook removed successfully for polling mode.")
        except Exception as e:
            logger.error(f"Error removing webhook for polling: {e}")
        return

    # webhook 模式设置
    full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    logger.info(f"Attempting to set webhook to: {full_webhook_url}")
    try:
        await application.bot.set_webhook(
            url=full_webhook_url,
            allowed_updates=Update.ALL_TYPES, # Or specify: [Update.MESSAGE, Update.CALLBACK_QUERY, etc.]
            drop_pending_updates=True,
            secret_token=BOT_TOKEN[:16] # 可选：增加一层安全性，需要您在启动 webhook 时也提供
        )
        webhook_info = await application.bot.get_webhook_info()
        if webhook_info.url == full_webhook_url:
            logger.info(f"Webhook successfully set to: {webhook_info.url}")
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
def graceful_signal_handler(signum, frame):
    logger.info(f"Signal {signal.Signals(signum).name} received. Initiating graceful shutdown...")
    shutdown_event.set()

async def main() -> None:
    """Run the bot."""
    mode_text = "Polling Mode" if USE_POLLING else "Webhook Mode"
    logger.info(f"Starting Z1-Gray Bot ({mode_text})...")

    # 设置持久化
    try:
        # Render.com 默认情况下文件系统是短暂的，除非配置了持久磁盘。
        # 如果没有持久磁盘，PicklePersistence 的数据会在重启/重新部署后丢失。
        persistence = PicklePersistence(filepath=PERSISTENCE_FILEPATH)
        logger.info(f"PicklePersistence will use file: {PERSISTENCE_FILEPATH}")
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
        logger.info("Main conversation handler (start_handler) added.")
    else:
        # 如果 start_handler 未正确导入或不是 ConversationHandler，Bot 的核心逻辑会缺失
        logger.error("CRITICAL: `start_handler` is not a valid handler or not imported. Bot may not function as expected.")
        # 作为备用，可以添加一个简单的 /start
        async def basic_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("Basic start. Conversation flow not loaded.")
        application.add_handler(CommandHandler("start", basic_start))
        logger.info("Fallback basic /start handler added.")

    # --- 注册其他全局 Handlers (如果需要且未被 ConversationHandler 覆盖) ---
    # 全局 /cancel 通常应由 ConversationHandler 的 fallbacks 处理
    application.add_handler(CommandHandler("cancel", global_cancel))
    logger.info("Global /cancel handler added.")

    # 处理所有其他未匹配的命令
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command_handler))
    logger.info("Unknown command handler added.")

    # --- 初始化和启动应用组件 ---
    try:
        await application.initialize() # 初始化 handlers, etc.
        await application.start()      # 启动 JobQueue 等后台任务
                                   # post_init (set_webhook) 会在这里之后执行

        # 根据模式启动 polling 或 webhook
        if USE_POLLING:
            logger.info("Using polling mode for local development")
            try:
                # 使用明确的 drop_pending_updates 和 allowed_updates 参数
                await application.updater.start_polling(drop_pending_updates=True)
                logger.info("Bot started polling successfully. Press Ctrl+C to stop.")
            except Exception as e:
                logger.error(f"Error starting polling: {e}", exc_info=True)
                await application.stop()
                await application.shutdown()
                return
        else:
            # --- 启动内置 Webhook 服务器 ---
            # url_path 传递给 start_webhook 时不应包含前导 '/'
            clean_webhook_path = WEBHOOK_PATH.lstrip('/')
            logger.info(f"Starting local webhook HTTP server to listen on 0.0.0.0:{PORT} for path '/{clean_webhook_path}'")
            
            await application.updater.start_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=clean_webhook_path,
                # secret_token=BOT_TOKEN[:16] # 如果在 set_webhook 中使用了 secret_token，这里也要匹配
            )
            logger.info(f"Webhook HTTP server started. Bot should be ready to receive updates at {WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}")

    except Exception as e:
        logger.critical(f"CRITICAL error during application startup: {e}", exc_info=True)
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
    logger.info("Shutting down bot gracefully...")
    try:
        if application.updater and application.updater.running: # 检查 updater 是否存在且在运行
            await application.updater.stop() # 停止 webhook 服务器或 polling
        await application.stop()         # 停止 JobQueue 等
        await application.shutdown()     # 清理 PTB 资源
    except Exception as e:
        logger.error(f"Error during bot shutdown: {e}", exc_info=True)
    finally:
        logger.info("Bot shutdown sequence complete.")


if __name__ == '__main__':
    # 设置信号处理器
    try:
        signal.signal(signal.SIGINT, graceful_signal_handler)
        signal.signal(signal.SIGTERM, graceful_signal_handler)
    except ValueError:
        logger.warning("Could not set signal handlers. Graceful shutdown via signals might not work.")

    print("Starting bot...")
    try:
        print("Running main function...")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Process terminated by user or system.")
        logger.info("Process terminated by user or system.")
    except Exception as e:
        import traceback
        print(f"Unhandled exception: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        error_traceback = traceback.format_exc()
        logger.critical(f"Unhandled exception in main asyncio loop: {e}")
        logger.critical(f"Error traceback: {error_traceback}")
    finally:
        logger.info("Application exiting.")