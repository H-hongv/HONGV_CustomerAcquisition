"""
获客自动化系统 - 通用配置管理

通用化设计:
- 支持多行业模板 (预置金属铸造, 用户可自定义任意行业)
- 评分维度完全可配置 (名称、权重、规则均可通过 UI 修改)
- LLM 全参数可自定义 (base_url、model、temperature 等)
- 支持 MCP Client 连接外部数据源
"""
import os
import json
import copy
import re
from pathlib import Path
from dotenv import load_dotenv, set_key

load_dotenv()

BASE_DIR = Path(__file__).parent
EXPORT_DIR = BASE_DIR / "exports"
MASTER_CSV = EXPORT_DIR / "已处理公司清单.csv"
SETTINGS_FILE = BASE_DIR / "settings.json"
INDUSTRIES_DIR = BASE_DIR / "industries"
ENV_FILE = BASE_DIR / ".env"
SECRET_REFERENCE_RE = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)\}$")

API_ENV_KEYS = {
    "apify": "APIFY_API_TOKEN",
    "google_cse_id": "GOOGLE_CSE_ID",
}

# ============================================================
# 默认设置
# ============================================================
DEFAULT_SETTINGS = {
    "mode": "free",
    "active_industry": "",

    "llm": {
        "provider": "deepseek",
        "providers": {
            "deepseek": {
                "name": "DeepSeek",
                "api_key": "",
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-v4-flash",
                "temperature": 0.3,
                "max_tokens": 2000,
                "response_format": "json"
            },
            "mimo": {
                "name": "Mimo AI",
                "api_key": "",
                "base_url": "https://api.mimo.ai/v1",
                "model": "mimo-latest",
                "temperature": 0.3,
                "max_tokens": 2000,
                "response_format": "json"
            }
        }
    },
    "api_keys": {
        "tavily": "",
        "firecrawl": "",
        "serpapi": "",
        "apify": "",
        "hunterio": "",
        "groq": "",
        "google_cse": "",
        "google_cse_id": "",
        "zerobounce": ""
    },

    "mcp_clients": [],
    "mcp_servers": [],

    "customs": {
        "enabled": False,
        "file_path": "",
        "max_records": 50,
        "column_map": {},
    },
    "linkedin_enrich": {
        "enabled": True,
        "max_profiles": 20,
    },
    "rfq": {
        "enabled": False,
        "source": "ted",
        "file_path": "",
    },

    "tracking": {
        "enabled": False,
        "base_url": "",
    },

    "whatsapp": {
        "enabled": False,
        "api_token": "",
        "phone_number_id": "",
        "webhook_secret": "",
    },

    "outreach_matrix": {
        "daily_per_lead_limit": 3,
        "channel_cooldown_hours": {
            "email": 24,
            "whatsapp": 48,
            "phone": 168,
            "linkedin": 168
        },
        "channel_priority": ["email", "whatsapp", "phone", "linkedin"]
    },

    "email_verify": {
        "disposable_check": True,
        "smtp_handshake": False,
    },

    "localization": {
        "enabled": True,
        "default_language": "en",
    },

    "phone": {
        "enabled": True,
        "max_profiles": 30,
        "sources": {
            "web_extract": True,
            "customs_csv": True,
            "mcp_lookup": True,
        },
        "verify_api": "",
        "require_mobile": True,
        "min_confidence": 0.4,
    },

    "prompts": {
        "analyze": "你是一个行业专家, 专门为{company_name}寻找{target_product}的潜在客户。\n\n根据以下企业信息, 判断是否为潜在客户:\n\n{company_info}\n\n请分析以下维度:\n{dimensions_desc}\n\n请返回JSON格式:\n{json_format}",
        "email": "你是{company_name}的销售专家。根据以下客户背调报告, 撰写一封专业的开发信。\n\n客户信息:\n{customer_report}\n\n要求:\n1. 针对客户的具体痛点和需求\n2. 突出{target_product}的核心优势: {advantages}\n3. 语言专业、简洁、有说服力\n4. 包含明确的行动号召\n\n请生成:\n1. 邮件主题 (subject)\n2. 邮件正文 (body, 200-250词)\n"
    },

    "company_info": {
        "name": "我的公司",
        "product": "Your Product",
        "industry_expert": "B2B 外贸",
        "advantages": ["Advantage 1", "Advantage 2", "Advantage 3", "Advantage 4"]
    },

    "search": {
        "max_results_per_query": 10,
        "max_api_calls_per_company": 4,
        "concurrency": 3,
        "queries_per_round": 6
    },

    "crawl": {
        "timeout": 30,
        "max_pages_per_site": 3,
        "max_content_length": 5000,
        "concurrency": 3
    },

    "scoring": {
        "llm_semantic_enabled": True,
        "llm_semantic_ratio": 0.5,
        "description": "P1: LLM 语义评分(need_match)与规则评分的融合比例, 0=禁用"
    },
    "mode_profiles": {
        "free": {
            "search_rounds": 6,
            "max_per_round": 10,
            "deep_crawl": False,
            "max_pages": 2,
            "llm_refine": True,
            "llm_as_primary": False,
            "concurrency": 2,
            "description": "免费模式: DDG+SerpAPI搜索, Firecrawl/Trafilatura爬取, 规则引擎+LLM精排"
        },
        "paid": {
            "search_rounds": 10,
            "max_per_round": 20,
            "deep_crawl": True,
            "max_pages": 5,
            "llm_refine": True,
            "llm_as_primary": True,
            "concurrency": 4,
            "description": "收费模式: DDG+Tavily+SerpAPI搜索, Firecrawl+Apify多源爬取, LLM主导评分+多源交叉验证"
        }
    }
}


# ============================================================
# 预置行业模板: 金属铸造
# ============================================================
# ============================================================
# 国家 -> 语言映射 (泛化多语言支持)



METAL_CASTING_TEMPLATE = {
    "name": "金属铸造 - 打磨抛光机器人",
    "description": "金属铸造行业获客, 寻找需要打磨抛光去毛刺的潜在客户",
    "company_product": "Your Product",
    "target_industry": "metal casting",
    "search_queries": [
        "{industry} company {country} manufacturer",
        "{industry} foundry {country} OEM supplier",
        "{country} {industry} casting factory",
        "{country} metal casting company hiring expansion",
        "{country} {industry} trade association member",
        "{country} {industry} trade show exhibitor",
        "{country} {industry} hiring grinding robot automation 2024 2025",
        "{country} {industry} new investment expansion funding",
        "{country} {industry} looking for supplier RFQ tender",
        "{country} {industry} automation upgrade modernization new line"
    ],
    "dimensions": [
        {"key": "product_match", "name": "材质适配性", "max_score": 20, "description": "是否生产金属制品", "rules": {"strong": {"score": 20, "keywords": ["铝合金", "锌合金", "镁合金", "铜合金", "铸铁", "钢铁", "铝铸", "锌铸", "镁铸", "黄铜", "不锈钢", "aluminum", "zinc", "magnesium", "die casting"]}, "medium": {"score": 12, "keywords": ["模具钢", "压铸模具", "tool steel"]}, "weak": {"score": 5, "keywords": ["设备", "贸易", "equipment"]}}},
        {"key": "process_match", "name": "工艺需求", "max_score": 25, "description": "是否需要打磨抛光去毛刺工艺", "rules": {"explicit": {"score": 25, "keywords": ["打磨", "抛光", "去毛刺", "deburring", "grinding", "polishing", "研磨", "sanding"]}, "related": {"score": 15, "keywords": ["表面处理", "涂装", "阳极氧化", "粉末涂装", "热处理", "surface treatment", "coating"]}, "implicit": {"score": 10, "keywords": ["HPDC", "LPDC", "压铸", "铸造", "铸件", "砂铸", "重力铸造", "investment casting"]}}},
        {"key": "intent_signal", "name": "意图信号", "max_score": 40, "description": "采购意图强弱", "rules": {"strong": {"score_range": [30, 40], "keywords": ["招聘打磨", "招聘抛光", "新工厂", "新产线", "扩产", "环保整改", "粉尘治理", "hiring grinding", "new factory", "expansion", "ordered new robot", "bestellten Roboter", "installing automation", "new production line", "neue Produktionslinie", "capital expenditure", "Sonderinvestition", "additional shift", "zusätzliche Schicht", "capacity expansion", "Kapazitätserweiterung", "second plant", "zweites Werk", "greenfield", "night shift", "Nachtschicht", "invested", "investition"]}, "medium": {"score_range": [20, 30], "keywords": ["IATF16949", "汽车OEM", "BMW", "VW", "Audi", "展会参展", "新品发布", "trade show", "new product", "IATF 16949 certification", "ISO 14001", "quality management upgrade", "new CEO", "neuer Geschäftsführer", "new plant manager", "neuer Werksleiter", "hiring 50+ employees", "50+ Mitarbeiter", "apprenticeship program", "Ausbildungsprogramm", "new OEM customer", "neuer OEM-Kunde", "entering new market", "export growth", "Exportwachstum", "supplying to BMW", "supplying to VW", "supplying to Mercedes", "GIFA", "METEC", "EUROGUSS", "exhibitor", "Aussteller"]}, "weak": {"score_range": [15, 20], "keywords": ["ISO9001", "多年经验", "出口", "家族企业", "ISO certified", "export", "exhibiting at", "ausstellend auf", "presenting at conference", "member of VDG", "VDG Mitglied", "case study", "Fallstudie", "white paper", "technical article", "Fachartikel", "partner of", "Partner von", "collaboration", "Zusammenarbeit"]}}},
        {"key": "scale_match", "name": "规模匹配度", "max_score": 20, "description": "企业规模是否适合采购设备", "rules": {"large": {"score": 20, "keywords": ["500员工", "1000员工", "500+ employees", "global", "集团", "group"]}, "medium": {"score": 10, "keywords": ["100员工", "200员工", "100-500", "medium"]}, "small": {"score": 5, "keywords": ["50员工", "small", "11-50"]}}},
        {"key": "bonus", "name": "环保加分", "max_score": 10, "description": "欧洲企业环保要求更严格", "rules": {"high": {"score": 10, "keywords": ["环保", "可持续", "sustainability", "green", "environmental"]}, "medium": {"score": 5, "keywords": ["ISO14001", "碳中和", "carbon neutral"]}}},
        {"key": "info_completeness", "name": "信息完整度", "max_score": 5, "description": "联系方式完整度", "rules": {}},
        {"key": "conversion_potential", "name": "转化潜力", "max_score": 15, "description": "综合转化可能性", "rules": {"high": {"score": 15, "keywords": []}, "medium": {"score": 10, "keywords": []}, "low": {"score": 5, "keywords": []}}}
    ],
    "veto_conditions": {
        "已有机器人磨抛设备": {"enabled": True, "keywords": ["已有机器人", "robot polishing", "自动化打磨"]},
        "提供磨抛外协服务": {"enabled": True, "keywords": ["外协", "代工打磨", "subcontract"]},
        "只做机加工": {"enabled": True, "keywords": ["CNC加工", "机加工", "machining only"]},
        "代工厂/合同制造商": {"enabled": False, "keywords": ["代工", "contract manufacturer", "OEM/ODM"]},
        "设备供应商": {"enabled": True, "keywords": ["设备供应商", "equipment supplier", "机器制造商"]}
    },
    "grade_thresholds": {"S": 100, "A+": 85, "A": 70, "B": 55}
}


# ============================================================
# 通用维度层 (行业无关) - P0 维度分层通用化
# ============================================================
# 通用层 6 维: need_match / intent_signal / accessibility / fit / value / data_quality
# 合并策略: 行业维度通过别名组覆盖对应通用维度，仅补充行业缺失项。
# 现有行业配置(dimensions 非空)时，若全部别名命中 -> 输出与输入完全一致。

SYSTEM_DIMENSION_ALIASES = {
    "need_match": ["product_match", "process_match", "service_match"],
    "intent_signal": ["intent_signal", "intent", "buying_signal"],
    "accessibility": ["info_completeness", "contact_quality", "reachability"],
    "fit": ["scale_match", "region_match", "segment_match"],
    "value": ["bonus", "conversion_potential", "account_value"],
    "data_quality": ["info_completeness", "quality_score", "freshness"],
}

SYSTEM_DIMENSIONS = [
    {
        "key": "need_match",
        "name": "需求匹配",
        "max_score": 25,
        "description": "目标客户与产品/服务的相关性（行业 target_profile 关键词派生，未配置时宽松匹配）",
        "rules": {
            "strong": {"score": 25, "keywords": ["sourcing", "looking for", "need", "require", "rfq", "tender", "采购", "需求", "询价", "招标", "supplier"]},
            "medium": {"score": 15, "keywords": ["supplier", "partner", "vendor", "cooperate", "import", "合作", "供应商", "进口"]},
            "weak": {"score": 8, "keywords": ["company", "enterprise", "business", "公司", "企业", "行业"]},
        },
    },
    {
        "key": "intent_signal",
        "name": "采购意图",
        "max_score": 30,
        "description": "跨行业采购信号（招聘/扩产/招标/投资/合规升级）",
        "rules": {
            "strong": {"score_range": [20, 30], "keywords": ["tender", "bidding", "rfq", "procurement plan", "expansion", "new factory", "hiring", "investment", "equipment purchase", "招标", "询价", "扩产", "新工厂", "招聘", "投资", "采购计划", "设备采购"]},
            "medium": {"score_range": [10, 20], "keywords": ["supplier development", "certification upgrade", "new line", "capacity", "trade show", "供应商开发", "认证升级", "新产线", "产能", "展会"]},
            "weak": {"score_range": [5, 10], "keywords": ["iso", "export", "growth", "development", "认证", "出口", "增长", "发展"]},
        },
    },
    {
        "key": "accessibility",
        "name": "可达性",
        "max_score": 15,
        "description": "决策人与联系方式可得性（由 reachability 计算）",
        "rules": {},
    },
    {
        "key": "fit",
        "name": "匹配度",
        "max_score": 15,
        "description": "公司规模/区域/类型是否在目标画像内",
        "rules": {
            "large": {"score": 15, "keywords": ["500+ employees", "global", "group", "集团", "500员工", "1000员工"]},
            "medium": {"score": 10, "keywords": ["100-500", "medium", "100员工", "200员工"]},
            "small": {"score": 5, "keywords": ["11-50", "small", "50员工"]},
        },
    },
    {
        "key": "value",
        "name": "客户价值",
        "max_score": 10,
        "description": "潜在订单体量信号（营收/规模/出口导向）",
        "rules": {
            "high": {"score": 10, "keywords": ["revenue", "turnover", "million", "export", "global", "营收", "销售额", "出口", "百万"]},
            "medium": {"score": 5, "keywords": ["employees", "established", "多年", "员工", "成立"]},
        },
    },
    {
        "key": "data_quality",
        "name": "数据质量",
        "max_score": 5,
        "description": "信息完整度（联系方式）",
        "rules": {},
    },
]

SYSTEM_VETO = {
    "无效联系方式页": {"enabled": True, "keywords": ["captcha", "verification required", "403 forbidden", "页面不存在", "not found"]},
    "招聘信息页": {"enabled": False, "keywords": ["careers page", "job listing", "招聘信息", "职位列表"]},
}


# ============================================================
# 行业模板管理器
# ============================================================
class IndustryManager:
    def __init__(self):
        INDUSTRIES_DIR.mkdir(exist_ok=True)
        self._builtin = {"__builtin_metal_casting__": METAL_CASTING_TEMPLATE}
    # Schema for industry template validation (P2-3)
    INDUSTRY_SCHEMA = {
        "required": ["name", "description", "search_queries", "dimensions"],
        "dimension_fields": ["key", "name", "max_score", "description"],
        "search_query_min": 3,
        # P0 通用化: target_profile(目标客户画像) 可选，供通用 need_match 与 LLM 向导使用
        "optional_fields": ["target_profile", "layers", "company_info"],
    }

    def validate_template(self, data: dict, path: str) -> list:
        errors = []
        if not isinstance(data, dict):
            return [f"template must be an object: {path}"]
        for field in self.INDUSTRY_SCHEMA["required"]:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        dimensions = data.get("dimensions", [])
        dimension_keys = set()
        total_max_score = 0
        if not isinstance(dimensions, list):
            errors.append("dimensions must be a list")
        else:
            for i, dim in enumerate(dimensions):
                if not isinstance(dim, dict):
                    errors.append(f"dimensions[{i}] must be an object")
                    continue
                for df in self.INDUSTRY_SCHEMA["dimension_fields"]:
                    if df not in dim:
                        errors.append(f"dimensions[{i}] missing: {df}")
                key = dim.get("key", "")
                if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", key):
                    errors.append(f"dimensions[{i}] invalid key: {key!r}")
                elif key in dimension_keys:
                    errors.append(f"duplicate dimension key: {key}")
                else:
                    dimension_keys.add(key)
                ms = dim.get("max_score", 0)
                if not isinstance(ms, (int, float)) or ms <= 0:
                    errors.append(f"dimensions[{i}] invalid max_score: {ms}")
                    ms = 0
                else:
                    total_max_score += ms
                # Validate rules structure (optional enhancement)
                rules = dim.get("rules", {})
                if not isinstance(rules, dict):
                    errors.append(f"dimensions[{i}].rules must be an object")
                else:
                    for rn, rd in rules.items():
                        if not isinstance(rd, dict):
                            errors.append(f"dimensions[{i}].rules.{rn} must be an object")
                            continue
                        if "score" not in rd and "score_range" not in rd:
                            errors.append(f"dimensions[{i}].rules.{rn}: missing score or score_range")
                        if "score" in rd:
                            score = rd["score"]
                            if not isinstance(score, (int, float)) or score < 0 or score > ms:
                                errors.append(
                                    f"dimensions[{i}].rules.{rn}.score out of range"
                                )
                        if "score_range" in rd:
                            score_range = rd["score_range"]
                            if (
                                not isinstance(score_range, list)
                                or len(score_range) != 2
                                or not all(isinstance(v, (int, float)) for v in score_range)
                                or score_range[0] < 0
                                or score_range[0] > score_range[1]
                                or score_range[1] > ms
                            ):
                                errors.append(
                                    f"dimensions[{i}].rules.{rn}.score_range invalid"
                                )
                        keywords = rd.get("keywords", [])
                        if not isinstance(keywords, list) or not all(
                            isinstance(keyword, str) for keyword in keywords
                        ):
                            errors.append(
                                f"dimensions[{i}].rules.{rn}.keywords must be strings"
                            )
        queries = data.get("search_queries", [])
        if not isinstance(queries, list) or not all(isinstance(q, str) for q in queries):
            errors.append("search_queries must be a list of strings")
            queries = []
        if len(queries) < self.INDUSTRY_SCHEMA["search_query_min"]:
            errors.append(
                f"search_queries need at least "
                f"{self.INDUSTRY_SCHEMA['search_query_min']}, got {len(queries)}"
            )
        for index, query in enumerate(queries):
            if "{country}" not in query:
                errors.append(f"search_queries[{index}] missing {{country}}")
        thresholds = data.get("grade_thresholds", {})
        if thresholds:
            if not isinstance(thresholds, dict):
                errors.append("grade_thresholds must be an object")
                thresholds = {}
            prev = float("inf")
            for g in ["S", "A+", "A", "B", "C"]:
                if g not in thresholds:
                    continue
                val = thresholds[g]
                if not isinstance(val, (int, float)) or val < 0:
                    errors.append(f"grade_thresholds invalid: {g}={val}")
                    continue
                if val >= prev:
                    errors.append(f"grade_thresholds not descending: {g}={val}")
                if total_max_score and val > total_max_score:
                    errors.append(
                        f"grade_thresholds exceeds max score {total_max_score}: {g}={val}"
                    )
                prev = val
        elif total_max_score:
            errors.append("grade_thresholds is required")
        # Empty company info is allowed while drafting a reusable template.
        ci = data.get("company_info", {})
        if ci and not isinstance(ci, dict):
            errors.append("company_info must be an object")
        # Validate prompts if present
        prompts = data.get("prompts", {})
        if prompts:
            for pk in ["analyze", "email"]:
                if pk not in prompts:
                    errors.append(f"prompts missing: {pk}")
        return errors

    @staticmethod
    def _safe_key(key: str) -> str:
        key = (key or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,79}", key):
            raise ValueError(
                "行业标识只能包含字母、数字、下划线和连字符，长度不超过80"
            )
        return key
    def list_industries(self):
        result = {}
        for key, tmpl in self._builtin.items():
            result[key] = {"name": tmpl["name"], "builtin": True}
        for f in INDUSTRIES_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8-sig"))
                result[f.stem] = {"name": data.get("name", f.stem), "builtin": False}
            except Exception:
                pass
        return result

    def first_template(self):
        """返回第一个可用模板（非内置优先），无任何模板时回退内置第一个。"""
        for key, info in self.list_industries().items():
            if not info.get("builtin"):
                return self.get_industry(key)
        for key in self._builtin:
            return self.get_industry(key)
        return None

    def _upgrade_legacy_template(self, tmpl: dict) -> dict:
        """旧格式模板(content_keywords)自动升级为 rules 格式, 使规则引擎可评分。

        旧 schema 把关键词放在 content_keywords.product/intent_signal/certification
        _keywords, 维度没有 rules, 规则引擎全部得 0 分。此处自动转换为新 schema。
        """
        ck = tmpl.get("content_keywords") or {}
        if not ck:
            return tmpl
        product_kws = [str(k) for k in ck.get("product_keywords", []) if k]
        intent_kws = [str(k) for k in ck.get("intent_signal_keywords", []) if k]
        cert_kws = [str(k) for k in ck.get("certification_keywords", []) if k]
        if not (product_kws or intent_kws or cert_kws):
            return tmpl
        for dim in tmpl.get("dimensions", []):
            if not isinstance(dim, dict) or dim.get("rules"):
                continue
            key = dim.get("key", "")
            ms = max(0, int(dim.get("max_score", 0)))
            if key == "product_match" and product_kws:
                dim["rules"] = {
                    "strong": {"score": ms, "keywords": product_kws[:8]},
                    "medium": {"score": max(1, int(ms * 0.6)), "keywords": product_kws[8:14]},
                }
            elif key == "process_match" and product_kws:
                rest = product_kws[14:]
                if rest:
                    dim["rules"] = {"strong": {"score": ms, "keywords": rest}}
            elif key == "intent_signal" and intent_kws:
                dim["rules"] = {
                    "strong": {"score_range": [25, ms], "keywords": intent_kws[:10]},
                    "medium": {"score_range": [15, 25], "keywords": intent_kws[10:]},
                }
            elif key == "bonus" and cert_kws:
                dim["rules"] = {"strong": {"score": ms, "keywords": cert_kws}}
        tmpl.pop("content_keywords", None)
        return tmpl

    def get_industry(self, key):
        if key in self._builtin:
            override = INDUSTRIES_DIR / f"{key}.json"
            if override.exists():
                try:
                    data = json.loads(override.read_text(encoding="utf-8-sig"))
                    self._upgrade_legacy_template(data)
                    errors = self.validate_template(data, str(override))
                    if not errors:
                        return data
                except Exception as exc:
                    from logger import logger
                    logger.warning(f"Failed to load builtin override {override}: {exc}")
            tmpl = copy.deepcopy(self._builtin[key])
            self._upgrade_legacy_template(tmpl)
            errors = self.validate_template(tmpl, "builtin:" + key)
            if errors:
                from logger import logger
                logger.warning(f"Builtin template {key}: {errors[:3]}")
            return tmpl
        try:
            key = self._safe_key(key)
        except ValueError:
            return None
        f = INDUSTRIES_DIR / f"{key}.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8-sig"))
            self._upgrade_legacy_template(data)
            errors = self.validate_template(data, str(f))
            if errors:
                from logger import logger
                logger.warning(f"Template {f.name}: {len(errors)} issues: {errors[:3]}")
            return data
        return None

    def save_industry(self, key, data):
        key = self._safe_key(key)
        errors = self.validate_template(data, key)
        if errors:
            raise ValueError("行业模板校验失败: " + "; ".join(errors[:5]))
        f = INDUSTRIES_DIR / f"{key}.json"
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig"
        )
        os.replace(tmp, f)

    def delete_industry(self, key):
        try:
            key = self._safe_key(key)
        except ValueError:
            return False
        f = INDUSTRIES_DIR / f"{key}.json"
        if f.exists():
            f.unlink()
            return True
        return False


class Config:
    def __init__(self):
        self.settings = copy.deepcopy(DEFAULT_SETTINGS)
        self.industry_manager = IndustryManager()
        self._load()

    def _load(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8-sig") as f:
                    saved = json.load(f)
                self._deep_update(self.settings, saved)
            except Exception as e:
                print(f"加载配置文件失败: {e}")

    def save(self):
        try:
            tmp = SETTINGS_FILE.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            os.replace(tmp, SETTINGS_FILE)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False

    def _deep_update(self, base, update):
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def get(self, key, default=None):
        keys = key.split(".")
        value = self.settings
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def set(self, key, value):
        keys = key.split(".")
        target = self.settings
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    def get_active_industry(self):
        key = self.settings.get("active_industry", "")
        tmpl = self.industry_manager.get_industry(key) if key else None
        if tmpl is None:
            tmpl = self.industry_manager.first_template()
        return tmpl

    def set_active_industry(self, key):
        self.settings["active_industry"] = key

    @staticmethod
    def _secret_reference(env_key):
        return f"${{{env_key}}}"

    @staticmethod
    def _resolve_secret(configured_value, *env_keys):
        """Resolve an env-backed secret while retaining legacy inline compatibility."""
        for env_key in env_keys:
            value = os.getenv(env_key, "").strip()
            if value:
                return value
        configured = str(configured_value or "").strip()
        match = SECRET_REFERENCE_RE.fullmatch(configured)
        if match:
            return os.getenv(match.group(1), "").strip()
        return configured

    @staticmethod
    def _api_env_key(service):
        service = str(service or "").strip().lower()
        return API_ENV_KEYS.get(service, f"{service.upper()}_API_KEY")

    def set_secret(self, env_key, value):
        """Persist a secret in the ignored local .env file, never in settings.json."""
        env_key = str(env_key or "").strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", env_key):
            raise ValueError("invalid environment variable name")
        value = str(value or "").strip()
        if not value or SECRET_REFERENCE_RE.fullmatch(value):
            return False
        ENV_FILE.touch(exist_ok=True)
        set_key(str(ENV_FILE), env_key, value, quote_mode="always")
        os.environ[env_key] = value
        return True

    def has_secret(self, env_key, configured_value=""):
        return bool(self._resolve_secret(configured_value, env_key))

    def get_llm_config(self):
        provider = self.settings["llm"]["provider"]
        providers = self.settings["llm"]["providers"]
        cfg = copy.deepcopy(providers.get(provider, {}))
        env_key = f"{provider.upper()}_API_KEY"
        cfg["api_key"] = self._resolve_secret(cfg.get("api_key"), env_key)
        return cfg

    def get_llm_provider_name(self):
        return self.settings["llm"]["provider"]

    def set_llm_provider(self, provider):
        self.settings["llm"]["provider"] = provider

    def get_llm_providers(self):
        return self.settings["llm"]["providers"]

    def update_llm_provider(self, provider, cfg):
        provider = str(provider or "").strip().lower()
        if not provider:
            raise ValueError("provider is required")
        incoming = copy.deepcopy(cfg or {})
        env_key = f"{provider.upper()}_API_KEY"
        if "api_key" in incoming:
            secret = str(incoming.pop("api_key") or "").strip()
            if secret and not SECRET_REFERENCE_RE.fullmatch(secret):
                self.set_secret(env_key, secret)
            current = self.settings.get("llm", {}).get("providers", {}).get(provider, {})
            current_value = current.get("api_key", "") if isinstance(current, dict) else ""
            incoming["api_key"] = (
                self._secret_reference(env_key)
                if self.has_secret(env_key, current_value)
                else ""
            )
        providers = self.settings.setdefault("llm", {}).setdefault("providers", {})
        providers.setdefault(provider, {}).update(incoming)

    def get_mode(self):
        return self.settings.get("mode", "free")

    def get_mode_profile(self, mode: str = None) -> dict:
        if mode is None:
            mode = self.get_mode()
        base = dict(DEFAULT_SETTINGS.get("mode_profiles", {}).get(mode, {}))
        saved = self.settings.get("mode_profiles", {}).get(mode, {})
        if isinstance(saved, dict):
            base.update(saved)
        return base

    def set_mode(self, mode):
        if mode not in ("free", "paid"):
            raise ValueError("mode must be 'free' or 'paid'")
        self.settings["mode"] = mode

    def get_api_key(self, service):
        service = str(service or "").strip().lower()
        env_key = self._api_env_key(service)
        configured = self.settings.get("api_keys", {}).get(service, "")
        return self._resolve_secret(configured, env_key)

    def update_api_key(self, service, value):
        service = str(service or "").strip().lower()
        if not service:
            raise ValueError("service is required")
        env_key = self._api_env_key(service)
        value = str(value or "").strip()
        current = self.settings.setdefault("api_keys", {}).get(service, "")
        if value and not SECRET_REFERENCE_RE.fullmatch(value):
            self.set_secret(env_key, value)
        self.settings["api_keys"][service] = (
            self._secret_reference(env_key)
            if self.has_secret(env_key, current)
            else ""
        )

    # ---------- Provider 注册表 (P3-4) ----------
    def get_provider_registry(self):
        """返回 provider 注册表持久化存储 (惰性初始化)."""
        return self.settings.setdefault(
            "provider_registry", {"providers": {}, "updated_at": ""}
        )

    def save_provider_registry(self, data):
        """保存 provider 注册表并落盘 settings.json."""
        self.settings["provider_registry"] = data
        return self.save()

    @staticmethod
    def _provider_env_key(provider_id, field):
        pid = str(provider_id or "").strip().upper()
        fld = str(field or "").strip().upper()
        return f"PROVIDER_{pid}_{fld}"

    def provider_secret_ref(self, provider_id, field, value):
        """把敏感配置写入 .env, 返回 ${ENV} 引用 (Provider 注册表用).

        空值表示显式清空该密钥; 非空明文写入 .env;
        ${ENV} 引用原样保留。
        """
        env_key = self._provider_env_key(provider_id, field)
        value = str(value or "").strip()
        if not value:
            return ""
        if not SECRET_REFERENCE_RE.fullmatch(value):
            self.set_secret(env_key, value)
        return self._secret_reference(env_key)

    def provider_secret_value(self, stored):
        """解析 Provider 注册表里的 ${ENV} 引用为明文 (未配置返回空串)."""
        return self._resolve_secret(stored)
    def get_gmail_config(self, resolve_secrets=True):
        gmail = copy.deepcopy(self.settings.get("gmail", {}))
        if resolve_secrets:
            gmail["email"] = os.getenv("GMAIL_EMAIL", "").strip() or gmail.get("email", "")
            gmail["app_password"] = self._resolve_secret(
                gmail.get("app_password"), "GMAIL_APP_PASSWORD"
            )
        return gmail

    def update_gmail_config(self, values):
        incoming = copy.deepcopy(values or {})
        if "app_password" in incoming:
            secret = str(incoming.pop("app_password") or "").replace(" ", "").strip()
            if secret and not SECRET_REFERENCE_RE.fullmatch(secret):
                self.set_secret("GMAIL_APP_PASSWORD", secret)
            current = self.settings.get("gmail", {}).get("app_password", "")
            incoming["app_password"] = (
                self._secret_reference("GMAIL_APP_PASSWORD")
                if self.has_secret("GMAIL_APP_PASSWORD", current)
                else ""
            )
        self.settings.setdefault("gmail", {}).update(incoming)

    def save_gmail_accounts(self, accounts):
        """Persist a list of sender accounts; secrets go to .env as ${ENV} refs."""
        stored = []
        try:
            existing = self.settings.get("gmail", {}).get("accounts") or []
        except Exception:
            existing = []
        for i, acct in enumerate(accounts or []):
            if not isinstance(acct, dict):
                continue
            email = str(acct.get("email", "") or "").strip()
            if not email:
                continue
            env_key = f"GMAIL_APP_PASSWORD_{i + 1}"
            item = {
                "email": email,
                "sender_name": str(acct.get("sender_name", "") or ""),
                "daily_limit": int(acct.get("daily_limit", 50) or 50),
                "hourly_limit": int(acct.get("hourly_limit", 10) or 10),
                "enabled": bool(acct.get("enabled", True)),
            }
            pwd = str(acct.get("app_password", "") or "").replace(" ", "").strip()
            prev = ""
            if i < len(existing) and isinstance(existing[i], dict):
                prev = str(existing[i].get("app_password", "") or "")
            if pwd and not SECRET_REFERENCE_RE.fullmatch(pwd):
                self.set_secret(env_key, pwd)
                item["app_password"] = self._secret_reference(env_key)
            else:
                item["app_password"] = pwd or prev
            stored.append(item)
        self.settings.setdefault("gmail", {})["accounts"] = stored
        return self.settings["gmail"]["accounts"]

    def get_gmail_accounts(self):
        """Return the raw account list (passwords may be ${ENV} refs)."""
        return list(self.settings.get("gmail", {}).get("accounts") or [])

    def get_prompt(self, prompt_type, **kwargs):
        try:
            ind = self.get_active_industry()
            if ind and ind.get("prompts", {}).get(prompt_type):
                template = ind["prompts"][prompt_type]
            else:
                template = self.settings.get("prompts", {}).get(prompt_type, "")
        except Exception:
            template = self.settings.get("prompts", {}).get(prompt_type, "")
        if kwargs:
            try:
                return template.format(**kwargs)
            except KeyError:
                return template
        return template

    
    # Product info completeness dimensions
    PRODUCT_COMPLETENESS_FIELDS = ["products", "certifications", "capabilities", "use_cases"]

    def get_dimensions(self):
        industry = self.get_active_industry()
        return self.merge_dimensions(industry.get("dimensions", []))

    def merge_dimensions(self, industry_dims):
        """P0: 通用层 + 行业层合并（行业维度按别名覆盖通用维度，仅补缺）。"""
        dims = [d for d in (industry_dims or []) if isinstance(d, dict)]
        covered = set()
        for dim in dims:
            key = dim.get("key")
            if not key:
                continue
            covered.add(key)
            for sys_key, aliases in SYSTEM_DIMENSION_ALIASES.items():
                if key in aliases:
                    covered.add(sys_key)
        for sys_dim in SYSTEM_DIMENSIONS:
            key = sys_dim.get("key")
            if key and key not in covered:
                dims.append(copy.deepcopy(sys_dim))
        return dims

    def merge_veto(self, industry_veto):
        """P0: 通用 veto + 行业 veto 合并（行业优先，同 key 覆盖）。"""
        merged = copy.deepcopy(SYSTEM_VETO)
        for key, value in (industry_veto or {}).items():
            merged[key] = copy.deepcopy(value)
        return merged

    def get_veto_conditions(self):
        industry = self.get_active_industry()
        return self.merge_veto(industry.get("veto_conditions", {}))

    def get_grade_thresholds(self):
        industry = self.get_active_industry()
        return industry.get("grade_thresholds", {"S": 100, "A+": 85, "A": 70, "B": 55})

    def get_scoring_config(self):
        """P1: LLM 语义评分配置（开关 + 融合比例）。"""
        cfg = dict(self.settings.get("scoring", DEFAULT_SETTINGS.get("scoring", {})))
        try:
            ratio = float(cfg.get("llm_semantic_ratio", 0.5))
            cfg["llm_semantic_ratio"] = max(0.0, min(1.0, ratio))
        except (TypeError, ValueError):
            cfg["llm_semantic_ratio"] = 0.5
        env_flag = os.getenv("SDR_LLM_SEMANTIC", "").strip().lower()
        if env_flag in ("0", "false", "off", "disabled"):
            cfg["llm_semantic_enabled"] = False
        elif env_flag in ("1", "true", "on", "enabled"):
            cfg["llm_semantic_enabled"] = True
        else:
            cfg["llm_semantic_enabled"] = bool(cfg.get("llm_semantic_enabled", True))
        return cfg

    def get_search_queries(self):
        industry = self.get_active_industry()
        return industry.get("search_queries", [
            "{industry} company {country}",
            "{industry} supplier {country}",
            "{country} {industry} manufacturer"
        ])

    def get_company_info(self):
        try:
            ind = self.get_active_industry()
            if ind and ind.get("company_info"):
                return ind["company_info"]
        except Exception:
            pass
        return self.settings.get("company_info", {})

    def get_search_config(self):
        return self.settings.get("search", DEFAULT_SETTINGS["search"])

    def get_crawl_config(self):
        return self.settings.get("crawl", DEFAULT_SETTINGS["crawl"])

    def get_mcp_clients(self):
        return self.settings.get("mcp_clients", [])

    def add_mcp_client(self, client_config):
        clients = self.settings.setdefault("mcp_clients", [])
        clients.append(client_config)

    def remove_mcp_client(self, index):
        clients = self.settings.get("mcp_clients", [])
        if 0 <= index < len(clients):
            clients.pop(index)

    def get_weights(self):
        dimensions = self.get_dimensions()
        return {dim["key"]: dim["max_score"] for dim in dimensions}

    def is_paid_mode(self):
        return self.get_mode() == "paid"

    def get_cost_estimate(self) -> str:
        """Return human-readable cost estimate based on current mode."""
        if self.is_free_mode():
            return FREE_MODE_COST_ESTIMATE.format(0.0009)
        return PAID_MODE_COST_ESTIMATE.format(0.05)

    def is_free_mode(self):
        return self.get_mode() == "free"



# Free mode cost estimate (visible to user)
FREE_MODE_COST_ESTIMATE = "Free mode: ~${0:.4f}/lead (DDG + Trafilatura + DeepSeek)"
PAID_MODE_COST_ESTIMATE = "Paid mode: ~${0:.4f}/lead (Tavily + Firecrawl + Hunter + Gemini)"


config = Config()

if __name__ == "__main__":
    print(f"当前模式: {config.get_mode()}")
    print(f"当前LLM: {config.get_llm_provider_name()}")
    print(f"当前行业: {config.get_active_industry()['name']}")
    print(f"评分维度: {[d['name'] for d in config.get_dimensions()]}")



