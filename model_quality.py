"""Model Quality Evaluator — evaluate LLM scoring accuracy and email quality.

v8.0 P1-2: Measures how well AI ranks leads and generates emails.
Metrics: Precision, Recall, NDCG for ranking; Relevance/Personalization/Professionalism for emails.
"""
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LeadRankingMetrics:
    """Metrics for lead ranking quality."""
    precision: float = 0.0
    recall: float = 0.0
    ndcg: float = 0.0
    top_k_accuracy: float = 0.0
    human_annotated: int = 0
    ai_annotated: int = 0
    matches: int = 0


@dataclass
class EmailQualityMetrics:
    """Metrics for email generation quality."""
    relevance: float = 0.0
    personalization: float = 0.0
    professionalism: float = 0.0
    conversion_potential: float = 0.0
    samples_evaluated: int = 0


class ModelQualityEvaluator:
    """Evaluate AI model quality across lead ranking and email generation."""

    def __init__(self, output_dir: str = "evaluations"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._lead_metrics: List[LeadRankingMetrics] = []
        self._email_metrics: List[EmailQualityMetrics] = []

    def evaluate_lead_ranking(
        self, ai_ranked: List[dict], human_ranked: List[dict], top_k: int = 10
    ) -> LeadRankingMetrics:
        """Compare AI lead ranking against human-annotated ranking.

        Args:
            ai_ranked: AI-scored companies sorted by score desc
            human_ranked: Human-annotated companies with 'relevant' boolean
            top_k: Top K for precision/recall calculation

        Returns:
            LeadRankingMetrics with precision, recall, NDCG
        """
        ai_names = [c.get("name", c.get("company_name", "")) for c in ai_ranked[:top_k]]
        human_relevant = {
            c.get("name", c.get("company_name", "")): c.get("relevant", False)
            for c in human_ranked
        }

        # Precision: of AI top-K, how many are actually relevant
        relevant_in_top_k = sum(1 for name in ai_names if human_relevant.get(name, False))
        precision = relevant_in_top_k / max(len(ai_names), 1)

        # Recall: of all relevant, how many in AI top-K
        total_relevant = sum(1 for v in human_relevant.values() if v)
        recall = relevant_in_top_k / max(total_relevant, 1) if total_relevant > 0 else 0

        # NDCG approximation (simplified)
        ideal_dcg = sum(1.0 / (i + 2) for i in range(min(total_relevant, top_k)))
        actual_dcg = 0.0
        for i, name in enumerate(ai_names):
            if human_relevant.get(name, False):
                actual_dcg += 1.0 / (i + 2)
        ndcg = actual_dcg / max(ideal_dcg, 0.001)

        metrics = LeadRankingMetrics(
            precision=round(precision, 3),
            recall=round(recall, 3),
            ndcg=round(ndcg, 3),
            top_k_accuracy=round(precision, 3),
            human_annotated=len(human_ranked),
            ai_annotated=len(ai_ranked),
            matches=relevant_in_top_k,
        )
        self._lead_metrics.append(metrics)
        return metrics

    def evaluate_email_quality(
        self, emails: List[dict], ratings: List[dict]
    ) -> EmailQualityMetrics:
        """Evaluate email quality against human ratings.

        Args:
            emails: Generated emails with keys: company, subject, body
            ratings: Human ratings with keys: relevance, personalization, professionalism (0-10 each)

        Returns:
            EmailQualityMetrics
        """
        if not emails or not ratings:
            return EmailQualityMetrics()

        relevance_sum = 0.0
        personalization_sum = 0.0
        professionalism_sum = 0.0

        for i, rating in enumerate(ratings[:len(emails)]):
            relevance_sum += rating.get("relevance", 5) / 10.0
            personalization_sum += rating.get("personalization", 5) / 10.0
            professionalism_sum += rating.get("professionalism", 5) / 10.0

        n = min(len(emails), len(ratings))
        metrics = EmailQualityMetrics(
            relevance=round(relevance_sum / n, 3),
            personalization=round(personalization_sum / n, 3),
            professionalism=round(professionalism_sum / n, 3),
            conversion_potential=round((relevance_sum * 0.4 + personalization_sum * 0.4 + professionalism_sum * 0.2) / n, 3),
            samples_evaluated=n,
        )
        self._email_metrics.append(metrics)
        return metrics

    def get_lead_ranking_summary(self) -> dict:
        if not self._lead_metrics:
            return {"status": "no data", "samples": 0}
        avg_p = sum(m.precision for m in self._lead_metrics) / len(self._lead_metrics)
        avg_r = sum(m.recall for m in self._lead_metrics) / len(self._lead_metrics)
        avg_n = sum(m.ndcg for m in self._lead_metrics) / len(self._lead_metrics)
        return {
            "samples": len(self._lead_metrics),
            "avg_precision": round(avg_p, 3),
            "avg_recall": round(avg_r, 3),
            "avg_ndcg": round(avg_n, 3),
            "grade": self._grade_ranking(avg_p, avg_r, avg_n),
        }

    def get_email_quality_summary(self) -> dict:
        if not self._email_metrics:
            return {"status": "no data", "samples": 0}
        avg_rel = sum(m.relevance for m in self._email_metrics) / len(self._email_metrics)
        avg_per = sum(m.personalization for m in self._email_metrics) / len(self._email_metrics)
        avg_pro = sum(m.professionalism for m in self._email_metrics) / len(self._email_metrics)
        return {
            "samples": len(self._email_metrics),
            "avg_relevance": round(avg_rel, 3),
            "avg_personalization": round(avg_per, 3),
            "avg_professionalism": round(avg_pro, 3),
            "grade": self._grade_email(avg_rel, avg_per, avg_pro),
        }

    def _grade_ranking(self, p: float, r: float, n: float) -> str:
        avg = (p + r + n) / 3
        if avg >= 0.85: return "A - Excellent ranking"
        elif avg >= 0.70: return "B - Good ranking"
        elif avg >= 0.50: return "C - Needs improvement"
        else: return "D - Poor, review scoring"

    def _grade_email(self, r: float, p: float, prof: float) -> str:
        avg = (r + p + prof) / 3
        if avg >= 0.85: return "A - Excellent emails"
        elif avg >= 0.70: return "B - Good emails"
        elif avg >= 0.50: return "C - Needs improvement"
        else: return "D - Poor, review templates"

    def save_report(self, filename: str = "model_quality_report.json"):
        report = {
            "lead_ranking": self.get_lead_ranking_summary(),
            "email_quality": self.get_email_quality_summary(),
            "detail": {
                "lead_metrics": [m.__dict__ for m in self._lead_metrics],
                "email_metrics": [m.__dict__ for m in self._email_metrics],
            },
        }
        path = self.output_dir / filename
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)


model_evaluator = ModelQualityEvaluator()