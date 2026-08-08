"""Development outreach email generator - re-exports from agents.email_agent (Sprint 3 unification).

All email generation is now handled by agents/email_agent.py EmailStrategyAgent.
This module kept for backward compatibility.
"""

from agents.email_agent import EmailStrategyAgent


class EmailGenerator:
    """Backward-compat wrapper. Delegates to EmailStrategyAgent."""

    def __init__(self):
        self._agent = EmailStrategyAgent()

    def generate_for_company(self, company, provider_name=None):
        """Generate outreach email for a single company."""
        profile = {
            "name": getattr(company, "name", ""),
            "website": getattr(company, "website", ""),
            "country": getattr(company, "country", ""),
            "summary_data": {"products": [], "certifications": []},
            "analysis_text": "",
            "_lead_grade": getattr(company, "grade", ""),
            "_lead_score": getattr(company, "total_score", 0),
            "intent_data": {"urgency": "medium", "intent_score": 50},
            "emails": [],
            "phones": [],
        }
        import config
        icp = config.config.get_active_industry()
        company_info = config.config.get_company_info()
        results = self._agent.generate_batch([profile], icp=icp, company_info=company_info)
        if results:
            email_data = results[0].get("email", {})
            return {
                "subject": email_data.get("subject", ""),
                "body": email_data.get("body", ""),
            }
        return {"subject": "", "body": "", "error": "No LLM available"}


email_generator = EmailGenerator()
