from loguru import logger

# 配置日志文件：每日自动切割，保留最新 5 个文件，等级为 INFO
logger.add("bot.log", rotation="1 day", retention=5, level="INFO")

# 明确导出 logger 对象
__all__ = ['logger']
