import random
from typing import List, Dict

class ABTestEngine:
    def __init__(self):
        self._tests = {}
        self._results = {}
        self._last_test = None

    def create_test(self, name: str, variants: List[Dict]):
        self._tests[name] = variants
        self._last_test = name

    def select_variant(self, test_name: str = None):
        name = test_name or self._last_test or list(self._tests.keys())[0]
        test = self._tests.get(name, [])
        if not test:
            return "A"
        weights = [v.get("weight", 50) for v in test]
        variants = [v["name"] for v in test]
        return random.choices(variants, weights=weights, k=1)[0]

    def record_result(self, variant: str, event_type: str, test_name: str = None):
        name = test_name or self._last_test or list(self._tests.keys())[0]
        if name not in self._results:
            self._results[name] = {}
        if variant not in self._results[name]:
            self._results[name][variant] = {"sent": 0, "replied": 0}
        self._results[name][variant][event_type] = (
            self._results[name][variant].get(event_type, 0) + 1
        )

    def get_report(self, test_name: str = None):
        name = test_name or self._last_test or list(self._tests.keys())[0]
        results = self._results.get(name, {})
        best = "A"
        best_rate = 0.0
        for var, counts in results.items():
            rate = counts.get("replied", 0) / max(counts.get("sent", 1), 1)
            if rate > best_rate:
                best = var
                best_rate = rate
        return {
            "test": name,
            "winner": best,
            "winner_rate": best_rate,
            "variants": results,
        }


ab_engine = ABTestEngine()


# === Email Template A/B Variants ===

EMAIL_TEMPLATE_VARIANTS = [
    {
        "name": "short_direct",
        "weight": 30,
        "style": "short and direct",
        "description": "Brief intro + value prop + CTA in 3 sentences",
        "prompt_modifier": "Keep the email very short (max 3 sentences). Get straight to the point.",
    },
    {
        "name": "detailed_value",
        "weight": 30,
        "style": "detailed value proposition",
        "description": "Company intro + specific value + case-like proof",
        "prompt_modifier": "Include specific details about our capabilities and how they solve the customer problem.",
    },
    {
        "name": "problem_solution",
        "weight": 25,
        "style": "problem-first approach",
        "description": "Identify a pain point + propose solution + call to action",
        "prompt_modifier": "Start by identifying a likely pain point in their industry, then propose how we solve it.",
    },
    {
        "name": "question_hook",
        "weight": 15,
        "style": "question-based hook",
        "description": "Open with a relevant question + brief intro + soft CTA",
        "prompt_modifier": "Open with a question relevant to their business challenges. Keep it conversational.",
    },
]


def init_email_ab_test():
    """Initialize the email template A/B test suite."""
    ab_engine.create_test("email_template", EMAIL_TEMPLATE_VARIANTS)
    ab_engine.create_test("email_subject", [
        {"name": "direct", "weight": 40, "description": "Direct value prop"},
        {"name": "question", "weight": 30, "description": "Question-based"},
        {"name": "personalized", "weight": 30, "description": "Personalized"},
    ])
    ab_engine.create_test("send_time", SEND_TIME_VARIANTS)
    ab_engine.create_test("channel", CHANNEL_VARIANTS)


_current_variant = ""


# === 触达矩阵 A/B 维度: 发送时间 / 渠道 ===

SEND_TIME_VARIANTS = [
    {"name": "morning", "weight": 40, "description": "本地上午时段发送"},
    {"name": "afternoon", "weight": 35, "description": "本地下午时段发送"},
    {"name": "evening", "weight": 25, "description": "本地晚间时段发送"},
]

CHANNEL_VARIANTS = [
    {"name": "email", "weight": 70, "description": "邮件渠道"},
    {"name": "linkedin", "weight": 30, "description": "LinkedIn渠道"},
]


def get_channel_preferences(industry_config=None) -> dict:
    """从行业配置读取渠道偏好 (主渠道/次渠道), 未配置时回退 email/linkedin."""
    try:
        if industry_config is None:
            import config as project_config
            industry_config = project_config.config.get_active_industry()
        cfg = industry_config or {}
        prefs = cfg.get("channel_preferences") or {}
        return {
            "primary": prefs.get("primary") or "email",
            "secondary": prefs.get("secondary") or "linkedin",
        }
    except Exception:
        return {"primary": "email", "secondary": "linkedin"}


def record_dimension_result(test_name: str, variant: str, event_type: str):
    """按维度记录 A/B 结果 (send_time / channel / email_subject ...)."""
    ab_engine.record_result(variant, event_type, test_name)


def get_dimension_report(test_name: str) -> dict:
    """获取指定维度的 A/B 报告."""
    return ab_engine.get_report(test_name)


def get_template_prompt_modifier() -> str:
    """Get a prompt modifier based on the selected A/B variant."""
    global _current_variant
    variant = ab_engine.select_variant("email_template")
    _current_variant = variant
    for v in EMAIL_TEMPLATE_VARIANTS:
        if v["name"] == variant:
            return v["prompt_modifier"]
    return ""


def get_current_variant() -> str:
    """Return the name of the last selected template variant."""
    return _current_variant


def get_template_report_from_db() -> dict:
    """Aggregate A/B template report from email_log (persistent)."""
    from memory.store import memory_store
    stats = memory_store.get_template_stats()
    best = ""
    best_rate = 0.0
    for v, entry in stats.items():
        rate = entry.get("replied_rate", 0)
        if rate > best_rate:
            best, best_rate = v, rate
    return {"test": "email_template", "winner": best, "winner_rate": best_rate,
            "variants": stats}


def record_template_result(variant: str, event_type: str):
    """Record a template test result (sent, opened, replied)."""
    ab_engine.record_result(variant, event_type, "email_template")


def get_template_report() -> dict:
    """Get the email template A/B test report."""
    return ab_engine.get_report("email_template")


# Auto-initialize on import
init_email_ab_test()


# === P0-4: 统计显著性判定 + 胜出变体权重自适应 ===

def get_ab_verdict_report(store=None, min_n: int = None) -> dict:
    """从 email_log 持久化统计生成 A/B 显著性报告.

    比较回复率最高的两个变体 (样本足够时), 返回:
      {test, variants, verdict: {winner, significant, lift, p_value, message},
       recommended_winner}
    """
    try:
        if store is None:
            from memory.store import memory_store as store
        stats = store.get_template_stats()
        if not stats:
            return {"test": "email_template", "variants": {}, "verdict": None,
                    "recommended_winner": None}
        threshold = int(min_n or 30)
        eligible = sorted(
            stats.items(),
            key=lambda kv: (kv[1].get("replied_rate", 0), kv[1].get("sent", 0)),
            reverse=True,
        )
        if len(eligible) < 2:
            return {"test": "email_template", "variants": stats, "verdict": None,
                    "recommended_winner": None}
        top, second = eligible[0], eligible[1]
        verdict = ab_verdict_from_provider(top[1], second[1], min_n=threshold)
        winner_name = None
        if verdict.get("significant") and verdict.get("winner"):
            winner_name = top[0] if verdict["winner"] == "A" else second[0]
        return {
            "test": "email_template",
            "variants": stats,
            "verdict": verdict,
            "recommended_winner": winner_name,
        }
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.warning("A/B verdict report failed: %s", e)
        return {"test": "email_template", "variants": {}, "verdict": None,
                "recommended_winner": None}


def ab_verdict_from_provider(stats_a: dict, stats_b: dict, min_n: int = 30) -> dict:
    """薄封装: providers.ab_test.ab_verdict (保持单一实现来源)."""
    from providers.ab_test import ab_verdict
    return ab_verdict(stats_a, stats_b, min_n=min_n)


def apply_ab_winner(winner_variant: str, boost: float = 2.0) -> dict:
    """将显著胜出的变体权重上调并归一化, 返回新权重摘要.

    None 表示变体不存在 (无操作).
    """
    target = None
    for v in EMAIL_TEMPLATE_VARIANTS:
        if v["name"] == winner_variant:
            target = v
            break
    if target is None:
        return None
    target["weight"] = max(1, int(round(target.get("weight", 10) * boost)))
    total = sum(v.get("weight", 1) for v in EMAIL_TEMPLATE_VARIANTS) or 1
    for v in EMAIL_TEMPLATE_VARIANTS:
        v["weight"] = round(v.get("weight", 1) * 100.0 / total, 2)
    return {"winner": winner_variant,
            "weights": {v["name"]: v.get("weight", 0) for v in EMAIL_TEMPLATE_VARIANTS},
            "total_weight": sum(v.get("weight", 0) for v in EMAIL_TEMPLATE_VARIANTS)}
