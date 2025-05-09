import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "your_default_bot_token")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "123456789"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
PAYMENT_LINK_49 = os.getenv("PAYMENT_LINK_49", "https://example.com/payment")
PERSISTENCE_PATH = "bot_data"
