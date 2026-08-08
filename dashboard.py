"""Growth Metrics Dashboard — conversion funnel, cost analytics, lead pipeline.

Standalone console dashboard OR embeddable module for GUI.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))


class GrowthDashboard:
    """Business metrics dashboard for SDR Agent."""

    def __init__(self):
        self._refresh()

    def _refresh(self):
        from memory.store import memory_store
        from workflow.checkpoint import checkpointer
        from core.events.agent_context import default_context

        self.memory = memory_store
        self.checkpointer = checkpointer
        self.ctx = default_context

    def get_funnel(self) -> Dict:
        """Get the full conversion funnel."""
        self._refresh()
        stats = self.memory.get_stats()
        conv = self.memory.get_conversion_rate()
        pipeline = self.memory.get_deal_pipeline()

        return {
            "discovered": stats["total_companies"],
            "emailed": stats["total_emails_sent"],
            "replied": stats["total_replies"],
            "reply_rate": stats["reply_rate"],
            "deals_active": conv["active"],
            "deals_won": conv["won"],
            "deals_lost": conv["lost"],
            "win_rate": conv["win_rate"],
            "total_revenue": f"${conv['total_revenue']:,.0f}",
            "avg_deal_value": f"${conv['avg_deal_value']:,.0f}",
            "pipeline_value": f"${pipeline.get('total_pipeline_value', 0):,.0f}",
        }

    def get_cost_metrics(self) -> Dict:
        """Get cost and efficiency metrics."""
        self._refresh()
        analytics = self.checkpointer.get_analytics()
        lead_count = analytics.get("total_leads_found", 0)
        cost_metrics = self.ctx.get_cost_per_lead(qualified_leads=max(lead_count, 1))

        return {
            "total_runs": analytics["total_runs"],
            "completed_runs": analytics["completed_runs"],
            "completion_rate": analytics["completion_rate"],
            "total_leads": lead_count,
            "avg_duration": f"{analytics['avg_duration_seconds']:.0f}s",
            "avg_cost_per_run": f"${analytics['avg_cost_usd']:.4f}",
            "cost_per_lead": f"${cost_metrics['cost_per_lead']:.4f}",
            "daily_cost": f"${cost_metrics['daily_cost_usd']:.4f}",
            "api_calls_today": cost_metrics["total_api_calls"],
        }

    def get_grade_distribution(self) -> Dict:
        """Get lead grade distribution."""
        self._refresh()
        stats = self.memory.get_stats()
        return stats.get("grade_distribution", {})

    def get_ab_test_results(self) -> Dict:
        """Get A/B test results."""
        try:
            from ab_test import get_template_report
            return get_template_report()
        except Exception:
            return {}

    def get_agent_costs(self) -> List[Dict]:
        """Get cost breakdown by agent."""
        try:
            from agents.tool_metadata import AGENT_METADATA
            return [
                {"agent": name, "cost": meta["cost_per_call"], "category": meta["category"]}
                for name, meta in AGENT_METADATA.items()
            ]
        except Exception:
            return []

    def print_dashboard(self):
        """Print the full dashboard to console."""
        funnel = self.get_funnel()
        cost = self.get_cost_metrics()
        grades = self.get_grade_distribution()
        ab = self.get_ab_test_results()

        print("=" * 60)
        print("  SDR GROWTH METRICS DASHBOARD")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        print("\n  CONVERSION FUNNEL")
        print("  " + "-" * 40)
        print(f"  Discovered:     {funnel['discovered']:>6}")
        print(f"  Emailed:        {funnel['emailed']:>6}")
        print(f"  Replied:        {funnel['replied']:>6}  ({funnel['reply_rate']})")
        print(f"  Active Deals:   {funnel['deals_active']:>6}")
        print(f"  Won:            {funnel['deals_won']:>6}  ({funnel['win_rate']})")
        print(f"  Lost:           {funnel['deals_lost']:>6}")
        print(f"  Pipeline Value: {funnel['pipeline_value']:>6}")
        print(f"  Total Revenue:  {funnel['total_revenue']:>6}")

        print("\n  COST METRICS")
        print("  " + "-" * 40)
        print(f"  Total Runs:     {cost['total_runs']:>6}")
        print(f"  Completion:     {cost['completion_rate']:>6}")
        print(f"  Total Leads:    {cost['total_leads']:>6}")
        print(f"  Avg Duration:   {cost['avg_duration']:>6}")
        print(f"  Cost/Run:       {cost['avg_cost_per_run']:>6}")
        print(f"  Cost/Lead:      {cost['cost_per_lead']:>6}")
        print(f"  Daily Cost:     {cost['daily_cost']:>6}")

        if grades:
            print("\n  GRADE DISTRIBUTION")
            print("  " + "-" * 40)
            total = sum(grades.values())
            for grade in ["S", "A", "B", "C", "D"]:
                count = grades.get(grade, 0)
                bar = "#" * int(count / max(total, 1) * 30)
                print(f"  {grade}: {count:>4} ({count/max(total,1)*100:5.1f}%) {bar}")

        if ab:
            print("\n  A/B TEST: Email Template")
            print("  " + "-" * 40)
            print(f"  Winner: {ab.get('winner', 'N/A')} ({ab.get('winner_rate', 0)*100:.0f}%)")

        print("\n" + "=" * 60)

    def to_dict(self) -> Dict:
        """Export all metrics as a dict for API/GUI consumption."""
        return {
            "timestamp": datetime.now().isoformat(),
            "funnel": self.get_funnel(),
            "costs": self.get_cost_metrics(),
            "grades": self.get_grade_distribution(),
            "ab_tests": self.get_ab_test_results(),
        }


# Quick CLI access
if __name__ == "__main__":
    GrowthDashboard().print_dashboard()
