import asyncio
import os
import signal # 用于优雅停机
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    PicklePersistence,
    MessageHandler, # 导入 MessageHandler
    filters # 导入 filters
)
from dotenv import load_dotenv

# 假设您的 handlers 和 utils 模块结构如前所述
from handlers.step_1_init import start_handler # 确保这是您期望的 Handler
from utils.logger_config import logger

# --- 全局变量 ---
shutdown_event = asyncio.Event() # 用于优雅停机

# --- 加载环境变量 ---
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
# 使用环境变量来决定是使用 polling 还是 webhook 模式
USE_POLLING = os.getenv('USE_POLLING', 'false').lower() == 'true'
# Render.com 等平台会自动设置 WEBHOOK_URL，本地测试时需要自己在 .env 中设置
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
# 使用一个更独特的默认路径，并确保以 '/' 开头
WEBHOOK_PATH_ENV = os.getenv('WEBHOOK_PATH')
if WEBHOOK_PATH_ENV and not WEBHOOK_PATH_ENV.startswith('/'):
    WEBHOOK_PATH = f"/{WEBHOOK_PATH_ENV}"
elif WEBHOOK_PATH_ENV:
    WEBHOOK_PATH = WEBHOOK_PATH_ENV
else:
    # 生成一个基于部分 Token 的相对安全的默认路径 (如果 Token 总是存在)
    # 或者一个固定的独特路径
    WEBHOOK_PATH = f"/{BOT_TOKEN[:12]}" if BOT_TOKEN else "/telegram_webhook_z1g_default"

PORT = int(os.getenv('PORT', '8080')) # Render 通常希望监听 8080 或 10000
PERSISTENCE_FILEPATH = os.getenv('PERSISTENCE_PATH', 'bot_data.pkl') # 包含 .pkl 后缀

# --- 启动前检查 ---
if not BOT_TOKEN:
    logger.critical("FATAL: BOT_TOKEN not found in environment variables.")
    exit(1)
if not WEBHOOK_URL: # 在 Webhook 模式下，WEBHOOK_URL 是必需的
    logger.critical("FATAL: WEBHOOK_URL not found in environment variables. Required for Webhook mode.")
    exit(1)

logger.info(f"BOT_TOKEN from .env ends with: ...{BOT_TOKEN[-4:]}")
logger.info(f"Configured WEBHOOK_URL: {WEBHOOK_URL}")
logger.info(f"Configured WEBHOOK_PATH: {WEBHOOK_PATH}")
logger.info(f"Configured PORT: {PORT}")
logger.info(f"Persistence filepath: {PERSISTENCE_FILEPATH}")


# --- 通用 Handler 函数 ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /cancel command."""
    logger.info(f"User {update.effective_user.id} cancelled the operation.")
    await update.message.reply_text('Operation cancelled. Send /start to begin again.')
    # 如果在 ConversationHandler 中，这里应该返回 ConversationHandler.END
    # 对于全局 cancel，确保它能正确终止会话（如果适用）

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles unknown commands."""
    logger.info(f"User {update.effective_user.id} sent an unknown command: {update.message.text}")
    await update.message.reply_text("Sorry, I didn't understand that command. Try /start.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="An unexpected error occurred. Please try again later or contact support if the issue persists."
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")

# --- Webhook 设置回调 (post_init) ---
async def post_init_webhook_setup(application: Application) -> None:
    """Sets the webhook after the application has been initialized."""
    # 在 v22.0 版本中，webhook 通常在 start_webhook 中自动设置
    # 这个函数可以用于其他初始化任务
    try:
        # 获取并记录 webhook 信息
        webhook_info = await application.bot.get_webhook_info()
        logger.info(f"Current webhook info: {webhook_info.url}")
    except Exception as e:
        logger.error(f"Error checking webhook: {e}", exc_info=True)

# --- 优雅停机处理 ---
def signal_handler(signum, frame):
    logger.info(f"Signal {signal.Signals(signum).name} received. Initiating graceful shutdown...")
    shutdown_event.set()

async def main() -> None:
    """Run the bot."""
    # 设置持久化
    try:
        persistence = PicklePersistence(filepath=PERSISTENCE_FILEPATH)
        logger.info(f"PicklePersistence initialized with file: {PERSISTENCE_FILEPATH}")
    except Exception as e:
        logger.error(f"Failed to initialize PicklePersistence: {e}. Persistence will be disabled.", exc_info=True)
        persistence = None # type: ignore

    # 初始化应用程序构建器
    builder = ApplicationBuilder().token(BOT_TOKEN)
    
    # 设置 post_init 回调
    builder = builder.post_init(post_init_webhook_setup)
    
    # 添加持久化
    if persistence:
        builder = builder.persistence(persistence)
    
    # 构建应用
    application = builder.build()

    # 注册错误处理器 (非常重要)
    application.add_error_handler(error_handler)

    # 注册核心处理程序 (例如您的 ConversationHandler)
    # 假设 start_handler 是一个 ConversationHandler
    # 如果 start_handler 只是一个普通的 CommandHandler('/start', actual_start_function),
    # 那么您需要一个 ConversationHandler 来管理多步流程。
    # 例如:
    # from telegram.ext import ConversationHandler
    # from utils.state_definitions import YOUR_STATES_HERE # 导入您的状态
    # from handlers.step_1_init import actual_start_function # 假设这是 /start 的入口
    # from handlers.step_2_scan import step_2_handler_function # 举例
    # conv_handler = ConversationHandler(
    # entry_points=[CommandHandler("start", actual_start_function)],
    #     states={
    # # STATE_ONE: [MessageHandler(filters.TEXT, one_handler)],
    # # STATE_TWO: [MessageHandler(filters.TEXT, two_handler)],
    # # ... 定义您的状态和对应的处理器 ...
    #     },
    #     fallbacks=[CommandHandler("cancel", cancel)], # cancel 应该返回 ConversationHandler.END
    #     persistent=True if persistence else False,
    # name="z1_gray_conversation",
    # )
    # application.add_handler(conv_handler)
    # --- 如果 `start_handler` 已经是配置好的 ConversationHandler，则直接添加 ---
    if start_handler: # 确保 start_handler 已正确导入和定义
        application.add_handler(start_handler)
        logger.info("Main conversation handler (start_handler) added.")
    else:
        logger.warning("`start_handler` not found or not imported correctly. Main conversation flow might not work.")
        # 可以添加一个简单的 /start 作为备用
        from handlers.step_1_init import start as step_1_start_func # 假设 start 函数在 step_1_init.py
        application.add_handler(CommandHandler('start', step_1_start_func))
        logger.info("Added basic /start CommandHandler as a fallback.")


    # 注册全局的 /cancel 命令 (确保它能正确结束会话)
    # 如果您的 ConversationHandler 中已经有 cancel 作为 fallback，这里可能不需要重复添加
    # 或者确保这个全局 cancel 不会与 ConversationHandler 的 fallback 冲突
    # 通常，ConversationHandler 内部的 fallback 更佳
    # application.add_handler(CommandHandler('cancel', cancel)) # 考虑是否必要

    # 注册未知命令处理器 (应在所有特定命令处理器之后)
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    logger.info("Unknown command handler added.")

    # 初始化和启动内部组件
    await application.initialize()
    await application.start() # 启动 JobQueue 等

    # 根据环境变量决定使用 polling 还是 webhook 模式
    if USE_POLLING:
        logger.info("Using polling mode for local development")
        # 在 v22.0 中，应使用 application.updater.start_polling(drop_pending_updates=True)
        await application.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot started polling. Press Ctrl+C to stop.")
    else:
        # 启动 Webhook 服务器 (PTB 内置)
        # url_path 不应以 '/' 开头
        clean_webhook_path = WEBHOOK_PATH.lstrip('/')
        logger.info(f"Starting local webhook server on 0.0.0.0:{PORT} with path '{clean_webhook_path}'")
        try:
            # 在 v22.0 中，应使用更新的 webhook 参数
            await application.updater.start_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=clean_webhook_path,
                webhook_url=f"{WEBHOOK_URL.rstrip('/')}/{clean_webhook_path}" # 在 v22.0 中需要显式指定
            )
            logger.info(f"Webhook server started. Bot should be accessible at {WEBHOOK_URL.rstrip('/')}/{clean_webhook_path}")
        except Exception as e:
            logger.critical(f"Failed to start webhook server: {e}", exc_info=True)
            await application.stop()
            await application.shutdown()
            return # 提前退出

    # 等待停机信号
    await shutdown_event.wait()

    # 优雅停机
    logger.info("Shutting down bot...")
    await application.updater.stop() # 停止 webhook 服务器
    await application.stop()         # 停止 JobQueue 等
    await application.shutdown()     # 清理资源
    logger.info("Bot shut down gracefully.")


if __name__ == '__main__':
    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler) # kill 命令

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