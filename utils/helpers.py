import hashlib
from datetime import datetime

def generate_secure_id(user_id: int) -> str:
    """
    基于 user_id 和当前时间生成稳定 Secure ID（SHA256 前12位）
    """
    current_time = datetime.utcnow().isoformat()
    raw_string = f"{user_id}-{current_time}"
    secure_id = hashlib.sha256(raw_string.encode()).hexdigest()[:12]
    return secure_id

def get_formatted_utc_time() -> str:
    """
    返回当前 UTC 时间，格式化为 YYYY-MM-DD HH:MM:SS UTC
    """
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
