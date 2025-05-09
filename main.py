import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PicklePersistence
from aiohttp import web
from dotenv import load_dotenv
from handlers.step_1_init import start_handler
from utils.logger_config import logger

# 加载环境变量
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
WEBHOOK_PATH = os.getenv('WEBHOOK_PATH', '/')
PORT = int(os.getenv('PORT', '8443'))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Operation cancelled.')

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Sorry, I didn't understand that command.")

async def main() -> None:
    # 设置持久化
    persistence = PicklePersistence(filepath='bot_data')

    # 初始化应用程序
    application = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence).build()

    # 注册处理程序
    application.add_handler(start_handler)
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_handler(CommandHandler('unknown', unknown))

    # 启用 Webhook
    application.webhook_url = WEBHOOK_URL
    application.webhook_path = WEBHOOK_PATH
    application.webhook_listen = '0.0.0.0'
    application.webhook_port = PORT

    # 启动应用程序
    await application.start()
    await application.updater.start_webhook()

    logger.info(f"Bot successfully initialized on port {PORT}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
