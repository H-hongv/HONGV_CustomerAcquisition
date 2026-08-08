"""数据质量验证系统 — Data Quality Verifier v1.0
按 v8.0 审查方案实现
"""
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlparse

FALSE_POSITIVE_PATTERNS = [
    r"\btrading\s+(?:company|co\.?|ltd|limited|llc)\b",
    r"\btrade\s+(?:company|co\.?)\b",
    r"\bimport\s*(?:/|&|and)?\s*export\b",
    r"\bwholesale\b",
    r"\bdistributor\b",
    r"\breseller\b",
    r"\bconsulting\b",
    r"\bconsultancy\b",
    r"\bconsultant\b",
    r"\brecruitment\s+agency\b",
    r"\bstaffing\b",
    r"\bheadhunt(?:er|ing)\b",
    r"\boutsourcing\s+(?:company|firm)\b",
    r"\bholding\s+(?:company|group)\b",
    r"\binvestment\s+(?:company|firm|group)\b",
    r"\bretail\s+(?:store|shop|chain|outlet)\b",
    r"\bonline\s+shop\b",
    r"\be-commerce\b",
    r"\blogistics\b",
    r"\bfreight\s+forward",
    r"\bwarehousing\b",
    r"\bshipping\s+company\b",
    r"\bsoftware\s+(?:company|development|house)\b",
    r"\bIT\s+(?:service|consulting|solution)s?\b",
    r"\bweb\s+(?:design|development|agency)\b",
    r"\bapp\s+development\b",
]

def is_false_positive(name: str = "", description: str = "", website_content: str = "") -> Tuple[bool, List[str]]:
    combined = f"{name} {description} {website_content}".lower()
    patterns = []
    for pat in FALSE_POSITIVE_PATTERNS:
        if re.search(pat, combined, re.IGNORECASE):
            patterns.append(pat)
    is_fp = len(patterns) >= 2
    return is_fp, patterns

@dataclass
class CompanyVerification:
    company_name: str = ""
    website: str = ""
    country: str = ""
    website_exists: bool = False
    name_on_website: bool = False
    country_match: bool = False
    business_match: bool = False
    is_false_positive: bool = False
    false_positive_reasons: List[str] = field(default_factory=list)
    has_products: bool = False
    has_certifications: bool = False
    has_contact_person: bool = False
    has_email: bool = False
    has_phone: bool = False
    has_address: bool = False
    authenticity_score: int = 0
    completeness_score: int = 0
    evidence_log: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "company_name": self.company_name,
            "website": self.website,
            "website_exists": self.website_exists,
            "name_on_website": self.name_on_website,
            "country_match": self.country_match,
            "business_match": self.business_match,
            "is_false_positive": self.is_false_positive,
            "false_positive_reasons": self.false_positive_reasons,
            "info_completeness": {
                "products": self.has_products,
                "certifications": self.has_certifications,
                "contact_person": self.has_contact_person,
                "email": self.has_email,
                "phone": self.has_phone,
                "address": self.has_address,
            },
            "authenticity_score": self.authenticity_score,
            "completeness_score": self.completeness_score,
            "evidence_log": self.evidence_log,
        }

class DataQualityVerifier:
    def __init__(self, target_industry: str = "", target_country: str = ""):
        self.target_industry = target_industry
        self.target_country = target_country
        self._industry_keywords: List[str] = []
        self._country_keywords: List[str] = []

    def set_target(self, industry: str = "", country: str = ""):
        self.target_industry = industry
        self.target_country = country
        self._industry_keywords = self._expand_keywords(industry)
        self._country_keywords = self._expand_keywords(country)

    def _expand_keywords(self, text: str) -> List[str]:
        if not text:
            return []
        words = []
        for segment in re.split(r'[,;.;\s]+', text):
            segment = segment.strip().lower()
            if len(segment) >= 2:
                words.append(segment)
        return words

    def verify_company(self, company: dict) -> CompanyVerification:
        name = company.get("name", company.get("company_name", ""))
        website = company.get("website", "")
        country = company.get("country", "")
        summary_data = company.get("summary_data", {})
        v = CompanyVerification(company_name=name, website=website, country=country)
        v.website_exists = bool(website) and len(website) > 5 and "." in website
        if v.website_exists:
            v.evidence_log.append(f"OK website: {website}")
        else:
            v.evidence_log.append("NO website")
        content_combined = company.get("content", "") + company.get("analysis_text", "")
        v.name_on_website = self._check_name_on_website(name, website, content_combined)
        if v.name_on_website:
            v.evidence_log.append("OK name matches")
        else:
            v.evidence_log.append("WARN name not found in content")
        v.country_match = self._check_country_match(country, content_combined, summary_data)
        if v.country_match:
            v.evidence_log.append(f"OK country: {country}")
        else:
            v.evidence_log.append(f"WARN country unconfirmed: {country}")
        v.business_match = self._check_business_match(content_combined, summary_data)
        v.is_false_positive, v.false_positive_reasons = is_false_positive(name, content_combined, company.get("structured", ""))
        if v.is_false_positive:
            v.evidence_log.append(f"FLAG false positive: {'; '.join(v.false_positive_reasons[:2])}")
        v.has_products = bool(summary_data.get("products", []))
        v.has_certifications = bool(summary_data.get("certifications", []))
        v.has_contact_person = bool(company.get("contact_name", ""))
        v.has_email = bool(company.get("contact_email", "") or company.get("generic_email", ""))
        v.has_phone = bool(company.get("phone", ""))
        v.has_address = bool(summary_data.get("address", "") or company.get("address", ""))
        completed = sum([v.has_products, v.has_certifications, v.has_contact_person, v.has_email, v.has_phone, v.has_address])
        v.completeness_score = int((completed / 6) * 100)
        auth_factors = [(v.website_exists, 30), (v.name_on_website, 20), (v.country_match, 20), (v.business_match, 15), (not v.is_false_positive, 15)]
        v.authenticity_score = sum(weight for ok, weight in auth_factors if ok)
        return v

    def _check_name_on_website(self, name: str, website: str, content: str) -> bool:
        if not name or not content:
            return False
        name_words = [w for w in name.lower().split() if len(w) > 2][:3]
        content_lower = content.lower()
        matches = sum(1 for w in name_words if w in content_lower)
        return matches >= min(2, len(name_words))

    def _check_country_match(self, country: str, content: str, summary: dict) -> bool:
        if not country:
            return False
        country_lower = country.lower()
        content_lower = content.lower()[:3000]
        if country_lower in content_lower:
            return True
        address = summary.get("address", "")
        if address and country_lower in address.lower():
            return True
        location = summary.get("location", "")
        if location and country_lower in location.lower():
            return True
        return False

    def _check_business_match(self, content: str, summary: dict) -> bool:
        if not self._industry_keywords:
            products = summary.get("products", [])
            return len(products) > 0
        content_lower = content.lower()[:5000]
        matched = [kw for kw in self._industry_keywords if kw in content_lower]
        return len(matched) >= 1

    def verify_batch(self, companies: List[dict]) -> Dict:
        results = []
        passed = []
        failed = []
        for comp in companies:
            v = self.verify_company(comp)
            comp["_quality"] = v.to_dict()
            comp["_authenticity_score"] = v.authenticity_score
            comp["_completeness_score"] = v.completeness_score
            comp["_is_false_positive"] = v.is_false_positive
            results.append(comp)
            if v.is_false_positive or v.authenticity_score < 30:
                failed.append(comp)
            else:
                passed.append(comp)
        total = len(companies)
        avg_auth = int(sum(c["_authenticity_score"] for c in results) / max(total, 1))
        avg_comp = int(sum(c["_completeness_score"] for c in results) / max(total, 1))
        summary = {
            "total": total,
            "passed": len(passed),
            "failed": len(failed),
            "false_positives": sum(1 for c in results if c["_is_false_positive"]),
            "avg_authenticity": avg_auth,
            "avg_completeness": avg_comp,
            "completeness_breakdown": {
                "has_products": sum(1 for c in results if c.get("summary_data", {}).get("products")),
                "has_certs": sum(1 for c in results if c.get("summary_data", {}).get("certifications")),
                "has_contact": sum(1 for c in results if c.get("contact_name")),
                "has_email": sum(1 for c in results if c.get("contact_email") or c.get("generic_email")),
                "has_phone": sum(1 for c in results if c.get("phone")),
            },
            "quality_grade": self._grade(avg_auth),
        }
        return {"companies": results, "summary": summary, "passed": passed, "failed": failed}

    def _grade(self, avg_score: int) -> str:
        if avg_score >= 85:
            return "A - excellent"
        elif avg_score >= 70:
            return "B - good"
        elif avg_score >= 50:
            return "C - average"
        else:
            return "D - poor"

data_quality = DataQualityVerifier()
