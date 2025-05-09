import asyncio
import os
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
from dotenv import load_dotenv
from utils.logger_config import logger

# 加载环境变量
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

# 简单的命令处理函数
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Hello, World!')

async def main():
    # 创建应用程序
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # 注册处理程序
    application.add_handler(CommandHandler('start', start))
    
    # 启动 Bot
    await application.initialize()
    await application.start()
    
    # 仅用于测试，不启动 webhook
    logger.info("Bot initialized without webhook. Press Ctrl+C to exit.")
    
    # 保持 Bot 运行，直到接收到中断信号
    try:
        await asyncio.Event().wait()  # 无限等待
    except asyncio.CancelledError:
        pass
    finally:
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process terminated by user.")
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.critical(f"Error: {e}")
        logger.critical(f"Error traceback: {error_traceback}") 