"""Cost Analysis Module - Per-lead cost breakdown (v8.0 P0-3)

Enhanced cost tracking beyond AgentContext:
- Search cost per round
- Crawl cost per page
- LLM cost per analysis
- Email cost per send
- Total per-lead cost
- ROI projection
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field


COST_RATES = {
    "search_tavily": 0.005,
    "search_serpapi": 0.01,
    "search_google_cse": 0.005,
    "search_ddg": 0.0,
    "crawl_firecrawl": 0.002,
    "crawl_apify": 0.005,
    "crawl_trafilatura": 0.0,
    "llm_deepseek": 0.0001,
    "llm_mimo": 0.0001,
    "llm_openai_gpt4": 0.03,
    "email_verify_hunter": 0.01,
    "email_verify_zerobounce": 0.008,
    "email_smtp": 0.0,
    "email_send_gmail": 0.0,
}


@dataclass
class LeadCost:
    company_name: str = ""
    search_calls: int = 0
    crawl_calls: int = 0
    llm_calls: int = 0
    email_verify_calls: int = 0
    search_cost: float = 0.0
    crawl_cost: float = 0.0
    llm_cost: float = 0.0
    email_cost: float = 0.0
    total_cost: float = 0.0

    def to_dict(self) -> dict:
        return {
            "company_name": self.company_name,
            "search_calls": self.search_calls,
            "crawl_calls": self.crawl_calls,
            "llm_calls": self.llm_calls,
            "email_verify_calls": self.email_verify_calls,
            "search_cost": round(self.search_cost, 4),
            "crawl_cost": round(self.crawl_cost, 4),
            "llm_cost": round(self.llm_cost, 4),
            "email_cost": round(self.email_cost, 4),
            "total_cost": round(self.total_cost, 4),
        }


class CostAnalyzer:
    def __init__(self):
        self._lead_costs: List[LeadCost] = []
        self._total_search = 0
        self._total_crawl = 0
        self._total_llm = 0
        self._total_email = 0

    def track_lead(self, company_name: str,
                   search_calls: int = 1, crawl_calls: int = 1,
                   llm_calls: int = 1, email_verify_calls: int = 1,
                   search_provider: str = "ddg",
                   crawl_provider: str = "trafilatura",
                   llm_provider: str = "deepseek"):
        lc = LeadCost(company_name=company_name)
        lc.search_calls = search_calls
        lc.crawl_calls = crawl_calls
        lc.llm_calls = llm_calls
        lc.email_verify_calls = email_verify_calls

        sr_key = f"search_{search_provider}"
        cr_key = f"crawl_{crawl_provider}"
        ll_key = f"llm_{llm_provider}"

        lc.search_cost = COST_RATES.get(sr_key, 0.005) * search_calls
        lc.crawl_cost = COST_RATES.get(cr_key, 0.002) * crawl_calls
        lc.llm_cost = COST_RATES.get(ll_key, 0.0001) * llm_calls
        lc.email_cost = COST_RATES.get("email_verify_hunter", 0.01) * email_verify_calls
        lc.total_cost = lc.search_cost + lc.crawl_cost + lc.llm_cost + lc.email_cost

        self._lead_costs.append(lc)
        self._total_search += lc.search_cost
        self._total_crawl += lc.crawl_cost
        self._total_llm += lc.llm_cost
        self._total_email += lc.email_cost

    def get_summary(self) -> dict:
        total_leads = len(self._lead_costs)
        total_cost = sum(lc.total_cost for lc in self._lead_costs)
        return {
            "total_leads": total_leads,
            "cost_breakdown": {
                "search": round(self._total_search, 4),
                "crawl": round(self._total_crawl, 4),
                "llm": round(self._total_llm, 4),
                "email": round(self._total_email, 4),
            },
            "total_cost": round(total_cost, 4),
            "cost_per_lead": round(total_cost / max(total_leads, 1), 4),
            "cost_per_100_leads": round((total_cost / max(total_leads, 1)) * 100, 2),
            "roi_estimate": self._estimate_roi(total_leads),
        }

    def _estimate_roi(self, total_leads: int) -> dict:
        response_rate = 0.05
        conversion_rate = 0.02
        avg_deal_value = 50000
        responses = int(total_leads * response_rate)
        conversions = int(responses * conversion_rate)
        potential_revenue = conversions * avg_deal_value
        total_cost = sum(lc.total_cost for lc in self._lead_costs)
        return {
            "estimated_responses": responses,
            "estimated_conversions": conversions,
            "avg_deal_value": avg_deal_value,
            "potential_revenue": potential_revenue,
            "campaign_cost": round(total_cost, 2),
            "projected_roi": round(potential_revenue / max(total_cost, 0.01), 0),
        }

    def get_lead_costs(self) -> List[dict]:
        return [lc.to_dict() for lc in self._lead_costs]

    def reset(self):
        self._lead_costs = []
        self._total_search = 0
        self._total_crawl = 0
        self._total_llm = 0
        self._total_email = 0


cost_analyzer = CostAnalyzer()
