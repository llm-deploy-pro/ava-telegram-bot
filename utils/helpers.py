# utils/helpers.py

import hashlib
import time
from datetime import datetime, timedelta

def generate_secure_id(user_id) -> str:
    """
    基于 user_id 和当前时间生成稳定 Secure ID（SHA256 前12位）
    
    Args:
        user_id: 用户ID，可以是整数或字符串
        
    Returns:
        str: 生成的12位安全ID
    """
    # 确保user_id是字符串类型
    user_id_str = str(user_id)
    current_time = datetime.utcnow().isoformat()
    raw_string = f"{user_id_str}-{current_time}"
    secure_id = hashlib.sha256(raw_string.encode()).hexdigest()[:12]
    return secure_id

def get_formatted_utc_time() -> str:
    """
    返回当前 UTC 时间，格式化为 YYYY-MM-DD HH:MM:SS UTC
    """
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def generate_dynamic_hash_id(user_id: int, salt: str = "z1_gray") -> str:
    """
    基于用户ID和预设salt生成唯一且稳定的短HASH，用于伪装授权ID。
    例：AUTH-ID: 7e9f42a6
    """
    base_string = f"{user_id}_{salt}"
    return hashlib.sha256(base_string.encode("utf-8")).hexdigest()[:8]  # 保留前8位

def get_dynamic_time_left(start_timestamp: float, total_seconds: int) -> str:
    """
    给定起始时间戳和总时长，计算剩余时间并返回 'MM:SS' 格式倒计时。
    如：距离结束还有 137 秒 ➝ 返回 '02:17'
    """
    now = time.time()
    remaining = int(start_timestamp + total_seconds - now)
    if remaining <= 0:
        return "00:00"
    minutes, seconds = divmod(remaining, 60)
    return f"{minutes:02}:{seconds:02}"

def format_unix_timestamp(ts: float) -> str:
    """
    将Unix时间戳格式化为用户可见的标准时间（本地化）。
    例：1683796200 ➝ '2025-05-07 20:10:00'
    """
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

def get_current_timestamp() -> float:
    """
    获取当前Unix时间戳，常用于打点或计时起点。
    """
    return time.time()

def get_future_timestamp(seconds_from_now: int) -> float:
    """
    获取一个指定秒数后的 Unix 时间戳，用于设置 future 事件触发时间。
    """
    return time.time() + seconds_from_now
