"""Industry Template Creation Wizard - guided industry setup."""
import copy
import re
from typing import Dict, List, Optional
from logger import logger

# Pre-built dimension templates by industry category
INDUSTRY_DIMENSION_TEMPLATES = {
    "manufacturing": [
        {"key": "product_match", "name": "产品匹配度", "max_score": 25,
         "description": "是否生产相关产品", "rules": {"strong": {"score": 25, "keywords": []}, "medium": {"score": 15, "keywords": []}, "weak": {"score": 5, "keywords": []}}},
        {"key": "process_match", "name": "工艺需求", "max_score": 25,
         "description": "是否需要相关工艺", "rules": {"explicit": {"score": 25, "keywords": ["machining", "fabrication", "assembly", "production line", "automation"]}, "related": {"score": 15, "keywords": ["processing", "manufacturing process", "equipment", "workshop"]}}},
        {"key": "intent_signal", "name": "采购意图", "max_score": 35,
         "description": "是否有采购信号", "rules": {"strong": {"score_range": [30, 35], "keywords": ["RFQ", "request for quotation", "tender", "procurement", "seeking supplier"]}, "medium": {"score_range": [20, 30], "keywords": ["new project", "new factory", "expansion", "equipment upgrade"]}, "weak": {"score_range": [15, 20], "keywords": ["hiring", "capacity increase", "investment"]}}},
        {"key": "scale_match", "name": "规模匹配", "max_score": 10,
         "description": "企业规模是否合适", "rules": {"large": {"score": 10, "keywords": ["global", "group", "500+ employees", "multiple plants"]}, "medium": {"score": 6, "keywords": ["100+ employees", "growing manufacturer", "regional supplier"]}}},
        {"key": "info_completeness", "name": "信息完整度", "max_score": 5,
         "description": "联系方式完整度", "rules": {}},
    ],
    "technology": [
        {"key": "tech_stack", "name": "技术栈匹配", "max_score": 30,
         "description": "技术栈是否匹配", "rules": {"strong": {"score": 30, "keywords": []}, "medium": {"score": 18, "keywords": ["integration", "API", "cloud", "software", "platform", "digital system"]}}},
        {"key": "intent_signal", "name": "采购意图", "max_score": 30,
         "description": "是否有采购信号", "rules": {"strong": {"score_range": [25, 30], "keywords": ["RFP", "request for proposal", "procurement", "vendor evaluation", "seeking solution"]}, "medium": {"score_range": [15, 25], "keywords": ["digital transformation", "new project", "migration", "hiring", "funding", "expansion"]}}},
        {"key": "company_size", "name": "公司规模", "max_score": 15,
         "description": "团队/营收规模", "rules": {"large": {"score": 15, "keywords": ["enterprise", "global", "1000+ employees", "multinational"]}, "medium": {"score": 10, "keywords": ["100+ employees", "scale-up", "growing team", "mid-market"]}}},
        {"key": "market_presence", "name": "市场影响力", "max_score": 15,
         "description": "行业知名度", "rules": {"high": {"score": 15, "keywords": ["market leader", "global customers", "industry award", "public company"]}, "medium": {"score": 8, "keywords": ["case study", "regional leader", "established", "partner network"]}}},
        {"key": "info_completeness", "name": "信息完整度", "max_score": 10,
         "description": "联系方式完整度", "rules": {}},
    ],
    "trade": [
        {"key": "product_match", "name": "产品匹配", "max_score": 30,
         "description": "产品线匹配度", "rules": {"strong": {"score": 30, "keywords": []}, "medium": {"score": 18, "keywords": ["importer", "distributor", "wholesaler", "dealer", "product range"]}}},
        {"key": "volume_potential", "name": "采购量潜力", "max_score": 25,
         "description": "预估采购量", "rules": {"large": {"score": 25, "keywords": ["bulk order", "container load", "high volume", "national distribution"]}, "medium": {"score": 15, "keywords": ["wholesale", "annual demand", "stockist", "regional distribution"]}}},
        {"key": "intent_signal", "name": "采购意图", "max_score": 25,
         "description": "是否有采购信号", "rules": {"strong": {"score_range": [20, 25], "keywords": ["buying request", "RFQ", "sourcing", "seeking supplier", "procurement"]}, "medium": {"score_range": [12, 20], "keywords": ["new product line", "new market", "expansion", "trade show"]}}},
        {"key": "reliability", "name": "企业信誉", "max_score": 10,
         "description": "信誉/认证", "rules": {"high": {"score": 10, "keywords": ["ISO certified", "authorized distributor", "audited", "30 years"]}, "medium": {"score": 5, "keywords": ["established", "member of", "certified", "10 years"]}}},
        {"key": "info_completeness", "name": "信息完整度", "max_score": 10,
         "description": "联系方式完整度", "rules": {}},
    ],
    "services": [
        {"key": "service_match", "name": "服务场景匹配", "max_score": 30,
         "description": "客户业务场景是否需要目标服务", "rules": {"strong": {"score": 30, "keywords": []}, "medium": {"score": 18, "keywords": []}}},
        {"key": "pain_signal", "name": "业务痛点", "max_score": 25,
         "description": "是否存在效率、成本、增长或合规痛点", "rules": {"strong": {"score": 25, "keywords": ["cost reduction", "efficiency", "compliance", "outsourcing", "transformation"]}, "medium": {"score": 15, "keywords": ["growth", "optimization", "consulting"]}}},
        {"key": "intent_signal", "name": "采购意图", "max_score": 25,
         "description": "是否出现项目、招标、招聘或扩张信号", "rules": {"strong": {"score_range": [20, 25], "keywords": ["request for proposal", "RFP", "tender", "seeking partner", "new project"]}, "medium": {"score_range": [12, 20], "keywords": ["hiring", "expansion", "digital transformation"]}}},
        {"key": "company_value", "name": "客户价值", "max_score": 10,
         "description": "企业规模和持续采购能力", "rules": {"high": {"score": 10, "keywords": ["enterprise", "global", "group", "500+ employees"]}, "medium": {"score": 6, "keywords": ["growing company", "100+ employees"]}}},
        {"key": "info_completeness", "name": "信息完整度", "max_score": 10,
         "description": "联系方式完整度", "rules": {}},
    ],
    "healthcare": [
        {"key": "solution_match", "name": "医疗场景匹配", "max_score": 30,
         "description": "机构业务与产品适配度", "rules": {"strong": {"score": 30, "keywords": ["hospital", "clinic", "medical", "healthcare", "laboratory", "pharma"]}, "medium": {"score": 18, "keywords": ["care provider", "diagnostic", "biotech"]}}},
        {"key": "compliance_match", "name": "资质与合规", "max_score": 20,
         "description": "医疗资质及合规需求", "rules": {"high": {"score": 20, "keywords": ["FDA", "CE MDR", "ISO 13485", "HIPAA", "GMP"]}, "medium": {"score": 12, "keywords": ["certified", "accredited", "compliance"]}}},
        {"key": "intent_signal", "name": "采购意图", "max_score": 25,
         "description": "采购、扩建、设备更新或科研项目", "rules": {"strong": {"score_range": [20, 25], "keywords": ["procurement", "tender", "new facility", "equipment upgrade", "clinical project"]}, "medium": {"score_range": [12, 20], "keywords": ["expansion", "funding", "hiring"]}}},
        {"key": "organization_scale", "name": "机构规模", "max_score": 15,
         "description": "床位、员工或网络规模", "rules": {"large": {"score": 15, "keywords": ["hospital group", "health network", "500+ employees"]}, "medium": {"score": 9, "keywords": ["regional hospital", "100+ employees"]}}},
        {"key": "info_completeness", "name": "信息完整度", "max_score": 10,
         "description": "联系方式完整度", "rules": {}},
    ],
    "general": [
        {"key": "business_fit", "name": "业务匹配度", "max_score": 30,
         "description": "企业业务是否匹配目标产品或服务", "rules": {"strong": {"score": 30, "keywords": []}, "medium": {"score": 18, "keywords": []}}},
        {"key": "need_match", "name": "需求匹配度", "max_score": 25,
         "description": "是否存在明确问题或应用场景", "rules": {"strong": {"score": 25, "keywords": ["solution", "upgrade", "optimization", "replacement"]}, "medium": {"score": 15, "keywords": ["improvement", "efficiency", "growth"]}}},
        {"key": "intent_signal", "name": "采购意图", "max_score": 25,
         "description": "是否出现近期商业行动信号", "rules": {"strong": {"score_range": [20, 25], "keywords": ["procurement", "tender", "RFQ", "request for proposal", "seeking supplier", "new project"]}, "medium": {"score_range": [12, 20], "keywords": ["expansion", "hiring", "funding", "new office", "new facility"]}}},
        {"key": "company_value", "name": "客户价值", "max_score": 10,
         "description": "规模、成长性与持续合作潜力", "rules": {"high": {"score": 10, "keywords": ["global", "group", "enterprise", "500+ employees"]}, "medium": {"score": 6, "keywords": ["growing", "100+ employees"]}}},
        {"key": "info_completeness", "name": "信息完整度", "max_score": 10,
         "description": "联系方式完整度", "rules": {}},
    ],
}

# Default search query templates by category
SEARCH_QUERY_TEMPLATES = {
    "manufacturing": [
        "{country} {industry} manufacturer supplier",
        "{country} {industry} factory production",
        "{country} {industry} OEM contract manufacturing",
        "{country} {industry} trade show exhibitor",
        "{country} {industry} expansion new factory hiring",
    ],
    "technology": [
        "{country} {industry} company solutions",
        "{country} {industry} software provider",
        "{country} {industry} SaaS platform",
        "{country} {industry} hiring expansion funding",
        "{country} {industry} enterprise clients case study",
    ],
    "trade": [
        "{country} {industry} importer distributor",
        "{country} {industry} wholesale supplier",
        "{country} {industry} buyer procurement",
        "{country} {industry} trade show exhibitor",
        "{country} {industry} sourcing agent",
    ],
    "services": [
        "{country} {industry} company services",
        "{country} {industry} request for proposal RFP",
        "{country} {industry} outsourcing partner",
        "{country} {industry} digital transformation project",
        "{country} {industry} hiring expansion funding",
    ],
    "healthcare": [
        "{country} {industry} hospital clinic provider",
        "{country} {industry} medical procurement tender",
        "{country} {industry} new facility expansion",
        "{country} {industry} equipment upgrade project",
        "{country} {industry} distributor healthcare",
    ],
    "general": [
        "{country} {industry} company provider",
        "{country} {industry} buyer procurement",
        "{country} {industry} tender RFQ RFP",
        "{country} {industry} expansion new project",
        "{country} {industry} distributor partner",
    ],
}


def suggest_category(industry_name: str, description: str = "") -> str:
    """Suggest industry category based on name/description."""
    text = (industry_name + " " + description).lower()
    tech_keywords = ["software", "saas", "tech", "it", "digital", "ai", "cloud", "app", "platform", "data"]
    trade_keywords = ["trading", "wholesale", "retail", "import", "export", "distributor", "supply"]
    health_keywords = ["health", "medical", "hospital", "clinic", "pharma", "biotech"]
    service_keywords = ["service", "consulting", "agency", "outsourcing", "professional"]
    mfg_keywords = ["manufacturing", "factory", "production", "fabrication", "machining", "assembly", "foundry", "casting", "forging"]

    tech_score = sum(1 for kw in tech_keywords if kw in text)
    trade_score = sum(1 for kw in trade_keywords if kw in text)
    mfg_score = sum(1 for kw in mfg_keywords if kw in text)
    health_score = sum(1 for kw in health_keywords if kw in text)
    service_score = sum(1 for kw in service_keywords if kw in text)

    scores = {
        "manufacturing": mfg_score,
        "technology": tech_score,
        "trade": trade_score,
        "healthcare": health_score,
        "services": service_score,
    }
    category, category_score = max(scores.items(), key=lambda item: item[1])
    if category_score == 0:
        return "general"
    if category == "manufacturing":
        return "manufacturing"
    return category


def _seed_match_keywords(dimensions: list, *values: str):
    """Make newly generated templates usable before manual keyword tuning."""
    phrases = []
    for value in values:
        value = (value or "").strip()
        if not value:
            continue
        phrases.append(value)
        phrases.extend(
            token for token in re.findall(r"[\w+-]+", value.lower())
            if len(token) >= 3
        )
    unique = list(dict.fromkeys(phrases))[:20]
    if not unique:
        return
    for dimension in dimensions:
        if dimension.get("key") in ("intent_signal", "info_completeness"):
            continue
        rules = dimension.get("rules", {})
        if not rules:
            continue
        first_rule = next(iter(rules.values()))
        existing = first_rule.setdefault("keywords", [])
        first_rule["keywords"] = list(dict.fromkeys(unique + existing))[:30]
        break


def generate_industry_template(
    name: str,
    description: str = "",
    target_product: str = "",
    target_industry: str = "",
    category: Optional[str] = None,
    company_name: str = "",
    company_advantages: List[str] = None,
) -> dict:
    """Generate a complete industry template with sensible defaults.

    Args:
        name: Display name for the industry
        description: Brief description
        target_product: The product being sold
        target_industry: Target industry sector
        category: One of 'manufacturing', 'technology', 'trade'. Auto-detected if None.
        company_name: Your company name
        company_advantages: List of competitive advantages

    Returns:
        Complete industry template dict ready to save.
    """
    if category is None:
        category = suggest_category(name, description)

    dims = copy.deepcopy(
        INDUSTRY_DIMENSION_TEMPLATES.get(
            category, INDUSTRY_DIMENSION_TEMPLATES["general"]
        )
    )
    queries = copy.deepcopy(
        SEARCH_QUERY_TEMPLATES.get(category, SEARCH_QUERY_TEMPLATES["general"])
    )
    _seed_match_keywords(dims, target_product, target_industry, name)

    template = {
        "schema_version": 1,
        "name": name,
        "description": description or f"{name}行业获客模板",
        "company_product": target_product or "Your Product",
        "target_industry": target_industry or name.lower().replace(" ", "_"),
        "category": category,
        "search_queries": queries,
        "dimensions": dims,
        "grade_thresholds": {"S": 85, "A+": 70, "A": 55, "B": 40, "C": 25},
        "veto_conditions": {},
        "company_info": {
            "name": company_name or "",
            "product": target_product or "",
            "advantages": company_advantages or [],
            "product_details": "",
        },
        "prompts": {
            "analyze": (
                "你是一个行业专家, 专门为{company_name}寻找{target_product}的潜在客户。\n\n"
                "根据以下企业信息, 判断是否为潜在客户:\n\n"
                "{company_info}\n\n"
                "请分析以下维度:\n{dimensions_desc}\n\n"
                "请返回JSON格式:\n{json_format}"
            ),
            "email": (
                "你是{company_name}的销售专家。根据以下客户背调报告, 撰写一封专业的开发信。\n\n"
                "客户信息:\n{customer_report}\n\n"
                "要求:\n"
                "1. 针对客户的具体痛点和需求\n"
                "2. 突出{target_product}的核心优势: {advantages}\n"
                "3. 语言专业、简洁、有说服力\n"
                "4. 包含明确的行动号召\n\n"
                "请生成:\n"
                "1. 邮件主题 (subject)\n"
                "2. 邮件正文 (body, 200-250词)\n"
            ),
        },
    }

    logger.info(f"Generated industry template: {name} (category={category}, {len(dims)} dims, {len(queries)} queries)")
    return template


def llm_enrich_template(template: dict, name: str = "", product: str = "",
                         industry: str = "", country: str = "",
                         provider=None) -> dict:
    """P1-B: 用 LLM 补全模板关键词 / 买家画像 / veto / 搜索词。

    失败或 LLM 不可用时安全回落原模板（seed 关键词仍可用）。
    """
    try:
        from providers.llm.factory import create_llm_provider
        provider = provider or create_llm_provider()
        if provider is None:
            return template

        dims_desc = []
        for d in template.get("dimensions", []):
            rules_desc = "; ".join(
                f"{k}:{v.get('score', v.get('score_range', ''))}"
                for k, v in d.get("rules", {}).items()
            )
            dims_desc.append(f"- {d.get('key')}({d.get('name')}): {rules_desc}")

        prompt = (
            f"Create an industry lead-scoring configuration.\n"
            f"Industry: {industry or name}\nOur product/service: {product}\n"
            f"Target market: {country or 'global'}\n\n"
            "Existing dimensions:\n" + "\n".join(dims_desc[:20]) + "\n\n"
            "Return JSON only with this shape:\n"
            "{\n"
            '  "keywords": {"<dim_key>": {"<rule_level>": ["keyword1", "keyword2 (中文+English)"]}},\n'
            '  "target_profile": {"description": "...", "keywords": "space separated keywords 中英混合", "exclude": "..."},\n'
            '  "veto_conditions": {"<exclude_name>": {"enabled": true, "keywords": ["..."]}},\n'
            '  "search_queries": ["{industry} <query> {country}", ...]\n'
            "}\n"
            "Rules: keywords must be bilingual (Chinese + English). "
            "Only include dimensions that exist in the input. "
            "veto_conditions should exclude non-target customer types."
        )
        result = provider.analyze_json(
            prompt,
            system_prompt="You are a B2B industry analyst. Return JSON only.",
        )
        if not isinstance(result, dict):
            return template

        enriched = copy.deepcopy(template)

        # 1) 关键词合并（LLM 词 + 已有 seed 词，去重）
        kw_map = result.get("keywords", {}) or {}
        if isinstance(kw_map, dict):
            for dim in enriched.get("dimensions", []):
                key = dim.get("key")
                if key not in kw_map:
                    continue
                for level, words in (kw_map.get(key) or {}).items():
                    rules = dim.get("rules", {})
                    if level in rules and isinstance(words, list):
                        existing = rules[level].get("keywords", [])
                        if isinstance(existing, str):
                            existing = existing.split()
                        merged = list(dict.fromkeys(
                            [str(w) for w in words] + [str(x) for x in existing]
                        ))[:40]
                        rules[level]["keywords"] = merged

        # 2) target_profile
        if isinstance(result.get("target_profile"), dict):
            tp = {k: str(v) for k, v in result["target_profile"].items() if v}
            if tp:
                enriched["target_profile"] = tp

        # 3) veto 合并
        if isinstance(result.get("veto_conditions"), dict):
            veto = enriched.setdefault("veto_conditions", {})
            for vk, vv in result["veto_conditions"].items():
                if isinstance(vv, dict):
                    veto[str(vk)] = vv

        # 4) 搜索词扩展（仅保留含 {country} 的，通过 validate_template 校验）
        if isinstance(result.get("search_queries"), list):
            queries = enriched.get("search_queries", [])
            for q in result["search_queries"]:
                qs = str(q)
                if "{country}" in qs and qs not in queries:
                    queries.append(qs)

        logger.info(f"llm_enrich_template: {name} enriched ({len(enriched.get('dimensions', []))} dims)")
        return enriched
    except Exception as e:
        logger.warning(f"llm_enrich_template fallback: {e}")
        return template


def get_available_categories() -> Dict[str, str]:
    """Return available industry categories with descriptions."""
    return {
        "manufacturing": "制造业 — 工厂、生产、加工、铸造、组装",
        "technology": "科技 — 软件、SaaS、IT服务、数字化",
        "trade": "贸易 — 进出口、批发、零售、分销",
        "services": "专业服务 — 咨询、外包、代理、企业服务",
        "healthcare": "医疗健康 — 医院、器械、医药、生物科技",
        "general": "通用行业 — 适用于其他B2B产品与服务",
    }
