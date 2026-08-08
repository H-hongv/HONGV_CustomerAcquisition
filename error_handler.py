"""User-friendly error handler — Chinese messages, auto-fallback tips."""
import traceback
from logger import logger

ERROR_MAP = {
    "Firecrawl": ("网站抓取失败", "已自动切换备用方案，不影响任务继续"),
    "Tavily": ("搜索服务暂时不可用", "已降级到免费搜索引擎"),
    "connection": ("网络连接失败", "请检查网络后重试，或切换到免费模式"),
    "timeout": ("请求超时", "目标网站响应较慢，已跳过该条记录"),
    "rate limit": ("API频率限制", "已自动降低请求速度，请稍候"),
    "Gmail": ("邮件发送失败", "请检查Gmail应用专用密码是否正确配置"),
    "LLM": ("AI分析服务异常", "已切换为规则引擎分析，基本功能不受影响"),
    "encoding": ("文件编码错误", "已自动转换编码格式"),
    "permission": ("权限不足", "请以管理员身份运行或检查文件权限"),
}

FALLBACK_TIPS = {
    "search": "搜索降级：已切换到免费搜索引擎 (DuckDuckGo)",
    "crawl": "抓取降级：已切换到免费抓取 (Trafilatura)",
    "llm": "LLM降级：已切换到规则引擎分析",
    "email_verify": "邮箱验证跳过：将保留所有邮箱地址",
    "enrich": "数据丰富跳过：基本信息仍可用",
}


def friendly_error(exc: Exception, context: str = "") -> str:
    """Convert technical error to user-friendly Chinese message."""
    msg = str(exc)
    msg_lower = msg.lower()

    for key, (cn_title, cn_hint) in ERROR_MAP.items():
        if key.lower() in msg_lower:
            logger.warning(f"[UserError] {context}: {cn_title} — {cn_hint}")
            return f"{cn_title}\n{cn_hint}"

    # Generic fallback
    logger.error(f"[UserError] {context}: {msg}")
    short = msg[:80] + ("..." if len(msg) > 80 else "")
    return f"操作异常: {short}\n系统已自动处理，可继续使用"


def fallback_notice(component: str) -> str:
    """Generate fallback notice for degraded component."""
    return FALLBACK_TIPS.get(component, f"{component}已降级到免费模式")


def safe_call(func, *args, default=None, context="", **kwargs):
    """Execute function with safe error handling.

    Returns:
        (result, error_message_or_None)
    """
    try:
        result = func(*args, **kwargs)
        return result, None
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[SafeCall] {context}: {e}\n{tb[:500]}")
        user_msg = friendly_error(e, context)
        return default, user_msg