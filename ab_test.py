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


def get_template_prompt_modifier() -> str:
    """Get a prompt modifier based on the selected A/B variant."""
    variant = ab_engine.select_variant("email_template")
    for v in EMAIL_TEMPLATE_VARIANTS:
        if v["name"] == variant:
            return v["prompt_modifier"]
    return ""


def record_template_result(variant: str, event_type: str):
    """Record a template test result (sent, opened, replied)."""
    ab_engine.record_result(variant, event_type, "email_template")


def get_template_report() -> dict:
    """Get the email template A/B test report."""
    return ab_engine.get_report("email_template")


# Auto-initialize on import
init_email_ab_test()
