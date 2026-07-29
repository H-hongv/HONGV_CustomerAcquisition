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
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
EXPORT_DIR = BASE_DIR / "exports"
MASTER_CSV = EXPORT_DIR / "已处理公司清单.csv"
SETTINGS_FILE = BASE_DIR / "settings.json"
INDUSTRIES_DIR = BASE_DIR / "industries"

# ============================================================
# 默认设置
# ============================================================
DEFAULT_SETTINGS = {
    "mode": "free",
    "active_industry": "__builtin_metal_casting__",

    "llm": {
        "provider": "deepseek",
        "providers": {
            "deepseek": {
                "name": "DeepSeek",
                "api_key": "",
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat-v4-flash",
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

    "prompts": {
        "analyze": "你是一个行业专家, 专门为{company_name}寻找{target_product}的潜在客户。\n\n根据以下企业信息, 判断是否为潜在客户:\n\n{company_info}\n\n请分析以下维度:\n{dimensions_desc}\n\n请返回JSON格式:\n{json_format}",
        "email": "你是{company_name}的销售专家。根据以下客户背调报告, 撰写一封专业的开发信。\n\n客户信息:\n{customer_report}\n\n要求:\n1. 针对客户的具体痛点和需求\n2. 突出{target_product}的核心优势: {advantages}\n3. 语言专业、简洁、有说服力\n4. 包含明确的行动号召\n\n请生成:\n1. 邮件主题 (subject)\n2. 邮件正文 (body, 200-250词)\n"
    },

    "company_info": {
        "name": "龙砺智能科技",
        "product": "打磨抛光机器人工作站",
        "industry_expert": "金属铸造",
        "advantages": ["高精度打磨", "自动化抛光", "智能去毛刺", "环保低噪音"]
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
# ============================================================
COUNTRY_LANGUAGE_MAP = {
    # 欧洲
    "germany": {"code": "de", "local": "Deutschland", "lang": "German",
        "words": {"company": "Unternehmen", "manufacturer": "Hersteller",
                  "supplier": "Lieferant", "factory": "Fabrik",
                  "foundry": "Giesserei", "castings": "Gussteile",
                  "metal": "Metall", "industry": "Industrie"}},
    "france": {"code": "fr", "local": "France", "lang": "French",
        "words": {"company": "entreprise", "manufacturer": "fabricant",
                  "supplier": "fournisseur", "factory": "usine",
                  "foundry": "fonderie", "castings": "pieces moulees",
                  "metal": "metal", "industry": "industrie"}},
    "italy": {"code": "it", "local": "Italia", "lang": "Italian",
        "words": {"company": "azienda", "manufacturer": "produttore",
                  "supplier": "fornitore", "factory": "fabbrica",
                  "foundry": "fonderia", "castings": "getti",
                  "metal": "metallo", "industry": "industria"}},
    "spain": {"code": "es", "local": "Espana", "lang": "Spanish",
        "words": {"company": "empresa", "manufacturer": "fabricante",
                  "supplier": "proveedor", "factory": "fabrica",
                  "foundry": "fundicion", "castings": "piezas fundidas",
                  "metal": "metal", "industry": "industria"}},
    "poland": {"code": "pl", "local": "Polska", "lang": "Polish",
        "words": {"company": "firma", "manufacturer": "producent",
                  "supplier": "dostawca", "factory": "fabryka",
                  "foundry": "odlewnia", "castings": "odlewy",
                  "metal": "metal", "industry": "przemysl"}},
    "czech": {"code": "cs", "local": "Cesko", "lang": "Czech",
        "words": {"company": "firma", "manufacturer": "vyrobce",
                  "supplier": "dodavatel", "factory": "tovarna",
                  "foundry": "slevarna", "castings": "odlitky",
                  "metal": "kov", "industry": "prumysl"}},
    "netherlands": {"code": "nl", "local": "Nederland", "lang": "Dutch",
        "words": {"company": "bedrijf", "manufacturer": "fabrikant",
                  "supplier": "leverancier", "factory": "fabriek",
                  "foundry": "gieterij", "castings": "gietstukken",
                  "metal": "metaal", "industry": "industrie"}},
    "sweden": {"code": "sv", "local": "Sverige", "lang": "Swedish",
        "words": {"company": "foretag", "manufacturer": "tillverkare",
                  "supplier": "leverantor", "factory": "fabrik",
                  "foundry": "gjuteri", "castings": "gjutgods",
                  "metal": "metall", "industry": "industri"}},
    "turkey": {"code": "tr", "local": "Turkiye", "lang": "Turkish",
        "words": {"company": "sirket", "manufacturer": "uretici",
                  "supplier": "tedarikci", "factory": "fabrika",
                  "foundry": "dokumhane", "castings": "dokumler",
                  "metal": "metal", "industry": "sanayi"}},
    "switzerland": {"code": "de", "local": "Schweiz", "lang": "German",
        "words": {"company": "Unternehmen", "manufacturer": "Hersteller",
                  "supplier": "Lieferant", "factory": "Fabrik",
                  "foundry": "Giesserei", "castings": "Gussteile",
                  "metal": "Metall", "industry": "Industrie"}},
    "austria": {"code": "de", "local": "Osterreich", "lang": "German",
        "words": {"company": "Unternehmen", "manufacturer": "Hersteller",
                  "supplier": "Lieferant", "factory": "Fabrik",
                  "foundry": "Giesserei", "castings": "Gussteile",
                  "metal": "Metall", "industry": "Industrie"}},
    # 亚洲
    "japan": {"code": "ja", "local": "Japan", "lang": "Japanese",
        "words": {"company": "kaisha", "manufacturer": "seizou",
                  "supplier": "sapuraiya", "factory": "koujou",
                  "foundry": "chuuzousho", "castings": "imonogat",
                  "metal": "kinzoku", "industry": "sangyou"}},
    "korea": {"code": "ko", "local": "Korea", "lang": "Korean",
        "words": {"company": "hoesa", "manufacturer": "jejoep",
                  "supplier": "gonggeub", "factory": "gongjang",
                  "foundry": "juejoso", "castings": "jumul",
                  "metal": "geumssok", "industry": "saneop"}},
    "india": {"code": "hi", "local": "Bharat", "lang": "Hindi",
        "words": {"company": "company", "manufacturer": "nirmata",
                  "supplier": "aapoortikarta", "factory": "karkhana",
                  "foundry": "dhalai", "castings": "dhalai utpad",
                  "metal": "dhatu", "industry": "udyog"}},
    # 美洲
    "brazil": {"code": "pt-BR", "local": "Brasil", "lang": "Portuguese",
        "words": {"company": "empresa", "manufacturer": "fabricante",
                  "supplier": "fornecedor", "factory": "fabrica",
                  "foundry": "fundicao", "castings": "pecas fundidas",
                  "metal": "metal", "industry": "industria"}},
    "mexico": {"code": "es-MX", "local": "Mexico", "lang": "Spanish",
        "words": {"company": "empresa", "manufacturer": "fabricante",
                  "supplier": "proveedor", "factory": "fabrica",
                  "foundry": "fundicion", "castings": "piezas fundidas",
                  "metal": "metal", "industry": "industria"}},
    "usa": {"code": "en", "local": "United States", "lang": "English", "words": {}},
    "uk": {"code": "en", "local": "United Kingdom", "lang": "English", "words": {}},
    "china": {"code": "zh", "local": "China", "lang": "Chinese", "words": {}},
    "taiwan": {"code": "zh-TW", "local": "Taiwan", "lang": "Chinese", "words": {}},
}


METAL_CASTING_TEMPLATE = {
    "name": "金属铸造 - 打磨抛光机器人",
    "description": "金属铸造行业获客, 寻找需要打磨抛光去毛刺的潜在客户",
    "company_product": "打磨抛光机器人工作站",
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
    }

    def validate_template(self, data: dict, path: str) -> list:
        errors = []
        for field in self.INDUSTRY_SCHEMA["required"]:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        dimensions = data.get("dimensions", [])
        if isinstance(dimensions, list):
            for i, dim in enumerate(dimensions):
                for df in self.INDUSTRY_SCHEMA["dimension_fields"]:
                    if df not in dim:
                        errors.append(f"dimensions[{i}] missing: {df}")
                ms = dim.get("max_score", 0)
                if not isinstance(ms, (int, float)) or ms <= 0:
                    errors.append(f"dimensions[{i}] invalid max_score: {ms}")
        queries = data.get("search_queries", [])
        if len(queries) < self.INDUSTRY_SCHEMA["search_query_min"]:
            errors.append(
                f"search_queries need at least "
                f"{self.INDUSTRY_SCHEMA['search_query_min']}, got {len(queries)}"
            )
        thresholds = data.get("grade_thresholds", {})
        if thresholds:
            prev = 101
            for g in ["S", "A", "B", "C"]:
                val = thresholds.get(g, 0)
                if val >= prev:
                    errors.append(f"grade_thresholds not descending: {g}={val}")
                prev = val
        return errors

    def list_industries(self):
        result = {}
        for key, tmpl in self._builtin.items():
            result[key] = {"name": tmpl["name"], "builtin": True}
        for f in INDUSTRIES_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                result[f.stem] = {"name": data.get("name", f.stem), "builtin": False}
            except Exception:
                pass
        return result

    def get_industry(self, key):
        if key in self._builtin:
            tmpl = copy.deepcopy(self._builtin[key])
            errors = self.validate_template(tmpl, "builtin:" + key)
            if errors:
                from logger import logger
                logger.warning(f"Builtin template {key}: {errors[:3]}")
            return tmpl
        f = INDUSTRIES_DIR / f"{key}.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            errors = self.validate_template(data, str(f))
            if errors:
                from logger import logger
                logger.warning(f"Template {f.name}: {len(errors)} issues: {errors[:3]}")
            return data
        return None

    def save_industry(self, key, data):
        f = INDUSTRIES_DIR / f"{key}.json"
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def delete_industry(self, key):
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
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._deep_update(self.settings, saved)
            except Exception as e:
                print(f"加载配置文件失败: {e}")

    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
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
        key = self.settings.get("active_industry", "__builtin_metal_casting__")
        tmpl = self.industry_manager.get_industry(key)
        if tmpl is None:
            tmpl = copy.deepcopy(METAL_CASTING_TEMPLATE)
        return tmpl

    def set_active_industry(self, key):
        self.settings["active_industry"] = key

    def get_llm_config(self):
        provider = self.settings["llm"]["provider"]
        providers = self.settings["llm"]["providers"]
        cfg = providers.get(provider, {})
        env_key = f"{provider.upper()}_API_KEY"
        env_val = os.getenv(env_key)
        if env_val and not cfg.get("api_key"):
            cfg["api_key"] = env_val
        return cfg

    def get_llm_provider_name(self):
        return self.settings["llm"]["provider"]

    def set_llm_provider(self, provider):
        self.settings["llm"]["provider"] = provider

    def get_llm_providers(self):
        return self.settings["llm"]["providers"]

    def update_llm_provider(self, provider, cfg):
        self.settings["llm"]["providers"][provider] = cfg

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
        self.settings["mode"] = mode

    def get_api_key(self, service):
        env_key = f"{service.upper()}_API_KEY"
        env_val = os.getenv(env_key)
        if env_val:
            return env_val
        return self.settings.get("api_keys", {}).get(service, "")

    def get_prompt(self, prompt_type, **kwargs):
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
        return industry.get("dimensions", [])

    def get_veto_conditions(self):
        industry = self.get_active_industry()
        return industry.get("veto_conditions", {})

    def get_grade_thresholds(self):
        industry = self.get_active_industry()
        return industry.get("grade_thresholds", {"S": 100, "A+": 85, "A": 70, "B": 55})

    def get_search_queries(self):
        industry = self.get_active_industry()
        return industry.get("search_queries", [
            "{industry} company {country}",
            "{industry} supplier {country}",
            "{country} {industry} manufacturer"
        ])

    def get_company_info(self):
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



