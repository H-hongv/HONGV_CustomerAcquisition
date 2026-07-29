"""
龙砺获客自动化系统 - 日志管理
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

# 日志目录
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str = "longli", level: str = "INFO") -> logging.Logger:
    """设置日志器"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 文件输出
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{today}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger


# 默认日志器
logger = setup_logger()


class UILogHandler:
    """UI日志处理器（用于PyQt实时显示）"""
    
    def __init__(self):
        self.logs = []
        self.max_logs = 100
    
    def add(self, message: str, level: str = "INFO"):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        emoji = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "SEARCH": "🔍",
            "CRAWL": "📄",
            "ANALYZE": "🤖",
            "VERIFY": "✉️"
        }.get(level, "📋")
        
        log_entry = f"[{timestamp}] {emoji} {message}"
        self.logs.append(log_entry)
        
        # 保持日志数量
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
        
        # 同时写入标准日志
        logger.info(message)
    
    def get_logs(self) -> list:
        """获取所有日志"""
        return self.logs
    
    def clear(self):
        """清空日志"""
        self.logs = []


# 全局UI日志处理器
ui_log = UILogHandler()
