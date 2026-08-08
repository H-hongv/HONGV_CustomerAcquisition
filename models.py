"""
获客自动化系统 - 通用数据模型
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


# Company re-exported from core (Sprint 3 unification)
from core.models.company import Company

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
    rank: int = 0
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawlResult:
    url: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str = ""
    source: str = ""


@dataclass
class VerifyResult:
    email: str
    is_valid: bool
    confidence: str
    method: str
    details: str = ""


@dataclass
class AnalysisResult:
    company_name: str
    is_potential: bool = False
    dimension_scores: Dict[str, int] = field(default_factory=dict)
    total_score: int = 0
    grade: str = ""
    analysis: str = ""
    veto: bool = False
    veto_reason: str = ""
    raw_response: str = ""
    llm_model: str = ""
    product: str = ""
    process: str = ""
    material: str = ""
    application: str = ""
    scale: str = ""
    contact_name: str = ""
    phone: str = ""

    # 兼容旧接口
    @property
    def material_score(self):
        return self.dimension_scores.get("product_match", 0)

    @property
    def process_score(self):
        return self.dimension_scores.get("process_match", 0)

    @property
    def demand_score(self):
        return self.dimension_scores.get("intent_signal", 0)

    @property
    def scale_score(self):
        return self.dimension_scores.get("scale_match", 0)

    @property
    def env_score(self):
        return self.dimension_scores.get("bonus", 0)

@dataclass
class EmailContent:
    company_name: str
    subject: str
    body: str
    whatsapp: str = ""


@dataclass
class TaskProgress:
    total: int = 0
    completed: int = 0
    failed: int = 0
    current_step: str = ""
    current_company: str = ""
    start_time: datetime = field(default_factory=datetime.now)

    @property
    def percentage(self) -> float:
        if self.total == 0:
            return 0
        return (self.completed / self.total) * 100

    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()


@dataclass
class APIUsage:
    tavily_calls: int = 0
    firecrawl_calls: int = 0
    serpapi_calls: int = 0
    prospector_calls: int = 0
    llm_calls: int = 0
    total_cost: float = 0.0

    def add_call(self, service: str, cost: float = 0):
        attr = f"{service}_calls"
        if hasattr(self, attr):
            setattr(self, attr, getattr(self, attr) + 1)
        self.total_cost += cost

    def to_dict(self) -> Dict:
        return {
            "tavily": self.tavily_calls,
            "firecrawl": self.firecrawl_calls,
            "serpapi": self.serpapi_calls,
            "prospector": self.prospector_calls,
            "llm": self.llm_calls,
            "total_cost": f"${self.total_cost:.2f}"
        }
