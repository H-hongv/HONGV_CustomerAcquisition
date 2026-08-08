"""Offline startup and commercial-readiness validation.

The checks in this module never connect to an external service.  They validate
configuration shape, required capabilities, secret handling and the selected
free/paid operating profile before a workflow is started.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


VALID_MODES = {"free", "paid"}
VALID_MCP_TRANSPORTS = {"stdio", "sse", "http", "streamable_http"}
VALID_MCP_CATEGORIES = {"search", "crawl", "enrich", "custom"}
ENV_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


@dataclass(frozen=True)
class ReadinessIssue:
    """One actionable readiness finding."""

    severity: str
    code: str
    component: str
    message: str
    remediation: str = ""

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class ReadinessReport:
    """Structured result used by CLI, GUI, health checks and tests."""

    mode: str = "unknown"
    profile: str = "startup"
    issues: List[ReadinessIssue] = field(default_factory=list)
    checks: Dict[str, str] = field(default_factory=dict)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def fatal_issues(self) -> List[ReadinessIssue]:
        return [issue for issue in self.issues if issue.severity == "fatal"]

    @property
    def warnings(self) -> List[ReadinessIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def can_start(self) -> bool:
        return not self.fatal_issues

    @property
    def production_ready(self) -> bool:
        return not self.issues

    @property
    def status(self) -> str:
        if self.fatal_issues:
            return "fatal"
        if self.warnings:
            return "warning"
        return "ready"

    def add(
        self,
        severity: str,
        code: str,
        component: str,
        message: str,
        remediation: str = "",
    ) -> None:
        self.issues.append(
            ReadinessIssue(
                severity=severity,
                code=code,
                component=component,
                message=message,
                remediation=remediation,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "can_start": self.can_start,
            "production_ready": self.production_ready,
            "mode": self.mode,
            "profile": self.profile,
            "generated_at": self.generated_at,
            "checks": dict(self.checks),
            "counts": {
                "fatal": len(self.fatal_issues),
                "warning": len(self.warnings),
            },
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _secret_is_reference(value: Any) -> bool:
    text = _text(value)
    return bool(text) and ENV_REFERENCE.fullmatch(text) is not None


def _is_local_endpoint(url: str) -> bool:
    if not url:
        return False
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url if "://" in url else f"http://{url}")
        return (parsed.hostname or "").lower() in LOCAL_HOSTS
    except Exception:
        return False


def _resolved_secret(
    inline_value: Any,
    env_names: Sequence[str],
    environment: Mapping[str, str],
) -> str:
    for name in env_names:
        value = _text(environment.get(name, ""))
        if value:
            return value
    value = _text(inline_value)
    if value and not _secret_is_reference(value):
        return value
    if _secret_is_reference(value):
        match = ENV_REFERENCE.fullmatch(value)
        if match:
            return _text(environment.get(match.group(1), ""))
    return ""


def _strict_severity(commercial: bool) -> str:
    return "fatal" if commercial else "warning"


def _get_active_industry(config_obj: Any, settings: Mapping[str, Any]) -> Any:
    active_key = _text(settings.get("active_industry"))
    manager = getattr(config_obj, "industry_manager", None)
    if active_key and manager is not None and hasattr(manager, "get_industry"):
        return manager.get_industry(active_key)
    getter = getattr(config_obj, "get_active_industry", None)
    if callable(getter):
        return getter()
    return settings.get("industry")


def _validate_industry(
    report: ReadinessReport,
    config_obj: Any,
    settings: Mapping[str, Any],
    commercial: bool,
) -> Mapping[str, Any]:
    active_key = _text(settings.get("active_industry"))
    try:
        industry = _get_active_industry(config_obj, settings)
    except Exception as exc:
        report.add(
            "fatal",
            "industry.load_failed",
            "industry",
            f"行业模板加载失败：{type(exc).__name__}",
            "修复 active_industry 指向的 JSON 模板并重新运行检查。",
        )
        report.checks["industry"] = "fatal"
        return {}

    if not isinstance(industry, Mapping):
        report.add(
            "fatal",
            "industry.not_found",
            "industry",
            f"当前行业模板不存在：{active_key or '<empty>'}",
            "在行业向导中选择或创建一个有效模板。",
        )
        report.checks["industry"] = "fatal"
        return {}

    name = _text(industry.get("name"))
    if not name:
        report.add(
            "warning",
            "industry.name_missing",
            "industry",
            "行业模板缺少显示名称。",
            "补充 name 字段，便于审计和导出追踪。",
        )

    queries = industry.get("search_queries")
    if not isinstance(queries, list) or not any(_text(query) for query in queries):
        report.add(
            "fatal",
            "industry.search_queries_missing",
            "industry",
            "行业模板没有可执行的搜索语句。",
            "至少配置 3 条包含 {country} 的 search_queries。",
        )
    else:
        usable_queries = [query for query in queries if _text(query)]
        if len(usable_queries) < 3:
            report.add(
                "warning",
                "industry.search_queries_sparse",
                "industry",
                f"行业模板只有 {len(usable_queries)} 条有效搜索语句，覆盖率可能不足。",
                "为采购、扩产、招聘、认证和展会等信号分别配置查询。",
            )
        missing_country = [
            index
            for index, query in enumerate(usable_queries)
            if "{country}" not in query
        ]
        if missing_country:
            report.add(
                "warning",
                "industry.country_placeholder_missing",
                "industry",
                f"{len(missing_country)} 条搜索语句缺少 {{country}} 占位符。",
                "加入 {country}，避免跨国家结果污染。",
            )

    dimensions = industry.get("dimensions")
    total_score = 0.0
    dimension_keys = set()
    dimensions_valid = True
    if not isinstance(dimensions, list) or not dimensions:
        report.add(
            "fatal",
            "scoring.dimensions_missing",
            "scoring",
            "行业模板没有评分维度。",
            "至少配置一个带 key、name、max_score 的评分维度。",
        )
        dimensions_valid = False
    else:
        for index, dimension in enumerate(dimensions):
            if not isinstance(dimension, Mapping):
                dimensions_valid = False
                continue
            key = _text(dimension.get("key"))
            maximum = dimension.get("max_score")
            if not key or key in dimension_keys:
                dimensions_valid = False
            dimension_keys.add(key)
            if (
                isinstance(maximum, bool)
                or not isinstance(maximum, (int, float))
                or maximum <= 0
            ):
                dimensions_valid = False
            else:
                total_score += float(maximum)
        if not dimensions_valid:
            report.add(
                "fatal",
                "scoring.dimensions_invalid",
                "scoring",
                "评分维度含重复/空 key，或 max_score 不是正数。",
                "通过行业向导修复评分维度后再启动。",
            )

    thresholds = industry.get("grade_thresholds")
    if not isinstance(thresholds, Mapping) or not thresholds:
        report.add(
            "fatal",
            "scoring.thresholds_missing",
            "scoring",
            "行业模板缺少评级阈值。",
            "配置 S、A+、A、B 等降序阈值。",
        )
    else:
        previous = float("inf")
        invalid_threshold = False
        for grade in ("S", "A+", "A", "B", "C"):
            if grade not in thresholds:
                continue
            value = thresholds[grade]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
                or value >= previous
                or (total_score > 0 and value > total_score)
            ):
                invalid_threshold = True
            else:
                previous = float(value)
        if invalid_threshold:
            report.add(
                "fatal",
                "scoring.thresholds_invalid",
                "scoring",
                "评级阈值必须为非负数、按 S→C 严格降序且不超过总分。",
                "修复 grade_thresholds 后再启动。",
            )

    company_info = {}
    getter = getattr(config_obj, "get_company_info", None)
    try:
        company_info = (
            getter() if callable(getter) else settings.get("company_info", {})
        )
    except Exception:
        company_info = {}
    company_info = _mapping(company_info)
    missing_company_fields = [
        field_name
        for field_name in ("name", "product")
        if not _text(company_info.get(field_name))
    ]
    if missing_company_fields:
        report.add(
            _strict_severity(commercial),
            "company.identity_incomplete",
            "company",
            "发件企业资料不完整：" + ", ".join(missing_company_fields),
            "补齐企业名称和产品信息，避免生成通用或错误的开发信。",
        )

    report.checks["industry"] = (
        "fatal"
        if any(
            issue.severity == "fatal" and issue.component in {"industry", "scoring"}
            for issue in report.issues
        )
        else "ok"
    )
    return industry


def _validate_llm(
    report: ReadinessReport,
    settings: Mapping[str, Any],
    environment: Mapping[str, str],
    commercial: bool,
) -> None:
    llm = settings.get("llm")
    if not isinstance(llm, Mapping):
        report.add(
            "fatal",
            "llm.config_missing",
            "llm",
            "LLM 配置不是对象或不存在。",
            "配置 llm.provider 和 llm.providers。",
        )
        report.checks["llm"] = "fatal"
        return

    provider_name = _text(llm.get("provider"))
    providers = llm.get("providers")
    if not provider_name or not isinstance(providers, Mapping):
        report.add(
            "fatal",
            "llm.provider_missing",
            "llm",
            "未选择有效的 LLM Provider。",
            "在设置页选择 Provider 并保存。",
        )
        report.checks["llm"] = "fatal"
        return

    provider = providers.get(provider_name)
    if not isinstance(provider, Mapping):
        report.add(
            "fatal",
            "llm.provider_unknown",
            "llm",
            f"选中的 LLM Provider 未定义：{provider_name}",
            "补充对应 Provider 配置或切换到已定义项。",
        )
        report.checks["llm"] = "fatal"
        return

    model = _text(provider.get("model"))
    base_url = _text(provider.get("base_url"))
    if not model:
        report.add(
            "fatal",
            "llm.model_missing",
            "llm",
            f"LLM Provider {provider_name} 未配置 model。",
            "填写服务实际支持的模型名。",
        )
    if not base_url:
        report.add(
            _strict_severity(commercial),
            "llm.base_url_missing",
            "llm",
            f"LLM Provider {provider_name} 未配置 base_url。",
            "填写 OpenAI-compatible 或对应厂商 API 地址。",
        )

    api_key = _resolved_secret(
        provider.get("api_key"),
        (f"{provider_name.upper()}_API_KEY",),
        environment,
    )
    if not api_key and not _is_local_endpoint(base_url):
        report.add(
            _strict_severity(commercial),
            "llm.credential_missing",
            "llm",
            f"LLM Provider {provider_name} 没有可用凭据。",
            f"通过 {provider_name.upper()}_API_KEY 注入，不要提交到 settings.json。",
        )

    report.checks["llm"] = (
        "fatal"
        if any(
            issue.severity == "fatal" and issue.component == "llm"
            for issue in report.issues
        )
        else "ok"
    )


def _validate_mode_profile(
    report: ReadinessReport,
    settings: Mapping[str, Any],
) -> None:
    profiles = settings.get("mode_profiles")
    profile = _mapping(_mapping(profiles).get(report.mode))
    if not profile:
        report.add(
            "warning",
            "mode.profile_missing",
            "mode",
            f"{report.mode} 模式没有独立参数，将使用程序默认值。",
            "显式配置 search_rounds、max_per_round、max_pages 和 concurrency。",
        )
        return

    for field_name in ("search_rounds", "max_per_round", "max_pages", "concurrency"):
        value = profile.get(field_name)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0
        ):
            report.add(
                "fatal",
                "mode.profile_invalid",
                "mode",
                f"{report.mode} 模式参数 {field_name} 必须是正数。",
                "修复 mode_profiles 后再启动。",
            )


def _configured_mcp_servers(
    report: ReadinessReport,
    settings: Mapping[str, Any],
    environment: Mapping[str, str],
    commercial: bool,
) -> Dict[str, int]:
    raw_servers = settings.get("mcp_servers", settings.get("mcp_clients", []))
    if raw_servers is None:
        raw_servers = []
    if not isinstance(raw_servers, list):
        report.add(
            "fatal",
            "mcp.config_invalid",
            "mcp",
            "mcp_servers 必须是数组。",
            "在设置页重新保存 MCP 配置。",
        )
        return {"search": 0, "crawl": 0}

    active_counts = {"search": 0, "crawl": 0}
    seen_names = set()
    for index, server in enumerate(raw_servers):
        if not isinstance(server, Mapping):
            report.add(
                "warning",
                "mcp.entry_invalid",
                "mcp",
                f"第 {index + 1} 个 MCP 配置不是对象，已无法使用。",
                "删除并重新创建该 MCP 配置。",
            )
            continue
        if not server.get("enabled", True):
            continue

        name = _text(server.get("name"))
        transport = _text(server.get("transport")) or "stdio"
        category = _text(server.get("category")) or "custom"
        modes = server.get("modes", ["free", "paid"])

        invalid = False
        if not name:
            invalid = True
            report.add(
                "warning",
                "mcp.name_missing",
                "mcp",
                f"第 {index + 1} 个 MCP 缺少唯一名称。",
                "填写 name 后重新保存。",
            )
        elif name in seen_names:
            invalid = True
            report.add(
                "warning",
                "mcp.name_duplicate",
                "mcp",
                f"MCP 名称重复：{name}",
                "保证每个服务器 name 唯一。",
            )
        seen_names.add(name)

        if transport not in VALID_MCP_TRANSPORTS:
            invalid = True
            report.add(
                "warning",
                "mcp.transport_invalid",
                "mcp",
                f"MCP {name or index + 1} 的 transport 无效：{transport}",
                "使用 stdio、streamable_http、http 或 sse。",
            )
        if category not in VALID_MCP_CATEGORIES:
            invalid = True
            report.add(
                "warning",
                "mcp.category_invalid",
                "mcp",
                f"MCP {name or index + 1} 的 category 无效：{category}",
                "主流程数据源使用 search 或 crawl。",
            )
        if (
            not isinstance(modes, list)
            or not modes
            or any(mode not in VALID_MODES for mode in modes)
        ):
            invalid = True
            report.add(
                "warning",
                "mcp.modes_invalid",
                "mcp",
                f"MCP {name or index + 1} 的 modes 配置无效。",
                "modes 只能包含 free、paid。",
            )
            modes = []

        if transport == "stdio" and not _text(server.get("command")):
            invalid = True
            report.add(
                "warning",
                "mcp.command_missing",
                "mcp",
                f"stdio MCP {name or index + 1} 缺少 command。",
                "填写可执行命令及 args。",
            )
        if transport in {"sse", "http", "streamable_http"} and not _text(
            server.get("url")
        ):
            invalid = True
            report.add(
                "warning",
                "mcp.url_missing",
                "mcp",
                f"远程 MCP {name or index + 1} 缺少 URL。",
                "填写完整的 HTTP/SSE 地址。",
            )

        missing_env = set()
        for container_name in ("env", "headers"):
            container = server.get(container_name, {})
            if container and not isinstance(container, Mapping):
                invalid = True
                report.add(
                    "warning",
                    "mcp.secret_map_invalid",
                    "mcp",
                    f"MCP {name or index + 1} 的 {container_name} 必须是对象。",
                    "用 JSON key/value 对配置。",
                )
                continue
            for value in _mapping(container).values():
                for env_name in ENV_REFERENCE.findall(str(value)):
                    if not _text(environment.get(env_name, "")):
                        missing_env.add(env_name)
        if missing_env and report.mode in modes:
            invalid = True
            report.add(
                _strict_severity(commercial),
                "mcp.environment_missing",
                "mcp",
                f"MCP {name or index + 1} 缺少 {len(missing_env)} 个环境变量。",
                "在部署平台注入引用的变量后重启。",
            )

        if not invalid and report.mode in modes and category in active_counts:
            active_counts[category] += 1

    report.checks["mcp"] = (
        "fatal"
        if any(
            issue.severity == "fatal" and issue.component == "mcp"
            for issue in report.issues
        )
        else "ok"
    )
    return active_counts


def _validate_mode_sources(
    report: ReadinessReport,
    settings: Mapping[str, Any],
    environment: Mapping[str, str],
    active_mcp: Mapping[str, int],
    commercial: bool,
) -> None:
    if report.mode != "paid":
        report.checks["data_sources"] = "ok"
        return

    api_keys = _mapping(settings.get("api_keys"))
    paid_search = any(
        _resolved_secret(
            api_keys.get(key),
            (f"{key.upper()}_API_KEY",),
            environment,
        )
        for key in ("tavily", "serpapi")
    ) or bool(active_mcp.get("search"))
    paid_crawl = any(
        _resolved_secret(
            api_keys.get(key),
            (f"{key.upper()}_API_KEY",),
            environment,
        )
        for key in ("firecrawl", "apify")
    ) or bool(active_mcp.get("crawl"))

    missing = []
    if not paid_search:
        missing.append("付费搜索源")
    if not paid_crawl:
        missing.append("付费爬取源")
    if missing:
        report.add(
            _strict_severity(commercial),
            "paid.sources_missing",
            "data_sources",
            "付费模式未配置：" + "、".join(missing),
            "配置对应 API Key，或为 paid 模式启用 search/crawl MCP。",
        )
        report.checks["data_sources"] = "fatal" if commercial else "warning"
    else:
        report.checks["data_sources"] = "ok"


def _validate_email(
    report: ReadinessReport,
    settings: Mapping[str, Any],
    environment: Mapping[str, str],
    require_email: bool,
) -> None:
    gmail = _mapping(settings.get("gmail"))
    address = _resolved_secret(gmail.get("email"), ("GMAIL_EMAIL",), environment)
    password = _resolved_secret(
        gmail.get("app_password"), ("GMAIL_APP_PASSWORD",), environment
    )
    severity = "fatal" if require_email else "warning"

    if not address and not password:
        report.add(
            severity,
            "email.credentials_missing",
            "email",
            "Gmail 发信凭据未配置，获客与 CSV 导出可用，但邮件发送不可用。",
            "通过 GMAIL_EMAIL 和 GMAIL_APP_PASSWORD 注入凭据。",
        )
    elif not address or not password:
        report.add(
            severity,
            "email.credentials_partial",
            "email",
            "Gmail 凭据只配置了一部分。",
            "同时配置 GMAIL_EMAIL 和 GMAIL_APP_PASSWORD。",
        )
    elif not EMAIL_PATTERN.fullmatch(address):
        report.add(
            severity,
            "email.address_invalid",
            "email",
            "Gmail 发件地址格式无效。",
            "检查 GMAIL_EMAIL。",
        )

    daily_limit = gmail.get("daily_limit", 50)
    delay_seconds = gmail.get("delay_seconds", 30)
    if (
        isinstance(daily_limit, bool)
        or not isinstance(daily_limit, int)
        or daily_limit <= 0
    ):
        report.add(
            "fatal",
            "email.daily_limit_invalid",
            "email",
            "gmail.daily_limit 必须是正整数。",
            "设置保守的每日发送上限。",
        )
    elif daily_limit > 100:
        report.add(
            "warning",
            "email.daily_limit_high",
            "email",
            f"每日发送上限为 {daily_limit}，新域名或新邮箱应先小批量验证。",
            "根据域名信誉、退信率和供应商限制逐步放量。",
        )
    if (
        isinstance(delay_seconds, bool)
        or not isinstance(delay_seconds, (int, float))
        or delay_seconds < 1
    ):
        report.add(
            "fatal",
            "email.delay_invalid",
            "email",
            "gmail.delay_seconds 必须至少为 1 秒。",
            "设置合理发送间隔并保留人工审核。",
        )

    report.checks["email"] = (
        "fatal"
        if any(
            issue.severity == "fatal" and issue.component == "email"
            for issue in report.issues
        )
        else (
            "warning"
            if any(issue.component == "email" for issue in report.issues)
            else "ok"
        )
    )


def _inline_secret_locations(settings: Mapping[str, Any]) -> List[str]:
    locations: List[str] = []
    for key, value in _mapping(settings.get("api_keys")).items():
        if _text(value) and not _secret_is_reference(value):
            locations.append(f"api_keys.{key}")

    llm = _mapping(settings.get("llm"))
    for provider_name, provider in _mapping(llm.get("providers")).items():
        value = _mapping(provider).get("api_key")
        if _text(value) and not _secret_is_reference(value):
            locations.append(f"llm.providers.{provider_name}.api_key")

    gmail = _mapping(settings.get("gmail"))
    if _text(gmail.get("app_password")) and not _secret_is_reference(
        gmail.get("app_password")
    ):
        locations.append("gmail.app_password")

    servers = settings.get("mcp_servers", settings.get("mcp_clients", []))
    if isinstance(servers, list):
        for index, server in enumerate(servers):
            if not isinstance(server, Mapping):
                continue
            for container_name in ("env", "headers"):
                for key, value in _mapping(server.get(container_name)).items():
                    secret_key = re.search(
                        r"(?i)(authorization|api.?key|token|secret|password|credential)",
                        str(key),
                    )
                    if (
                        secret_key
                        and _text(value)
                        and not ENV_REFERENCE.search(str(value))
                    ):
                        locations.append(f"mcp_servers[{index}].{container_name}.{key}")
    return locations


def _validate_secret_storage(
    report: ReadinessReport,
    settings: Mapping[str, Any],
    commercial: bool,
) -> None:
    locations = _inline_secret_locations(settings)
    if locations:
        report.add(
            _strict_severity(commercial),
            "secrets.inline_credentials",
            "security",
            f"配置文件中发现 {len(locations)} 处明文凭据。",
            "撤销并轮换已暴露凭据，改用环境变量或部署平台 Secret；不要提交 settings.json。",
        )
        report.checks["security"] = "fatal" if commercial else "warning"
    else:
        report.checks["security"] = "ok"


def _validate_directories(
    report: ReadinessReport,
    project_root: Optional[Path],
) -> None:
    if project_root is None:
        return
    root = Path(project_root)
    if not root.exists() or not root.is_dir():
        report.add(
            "fatal",
            "storage.root_invalid",
            "storage",
            "项目根目录不存在或不是目录。",
            "检查工作目录和挂载路径。",
        )
        report.checks["storage"] = "fatal"
        return
    for name in ("industries", "exports", "logs", "memory"):
        path = root / name
        if path.exists() and not path.is_dir():
            report.add(
                "fatal",
                "storage.path_invalid",
                "storage",
                f"{name} 路径存在但不是目录。",
                f"修复 {path} 后再启动。",
            )
        elif path.exists() and name != "industries" and not os.access(path, os.W_OK):
            report.add(
                "fatal",
                "storage.path_not_writable",
                "storage",
                f"{name} 目录不可写。",
                "为应用运行身份授予该持久化目录写权限。",
            )
        elif not path.exists():
            report.add(
                "warning",
                "storage.path_missing",
                "storage",
                f"{name} 目录不存在，首次写入时需要创建。",
                "在部署阶段创建持久化目录并授予应用写权限。",
            )
    report.checks["storage"] = (
        "fatal"
        if any(
            issue.severity == "fatal" and issue.component == "storage"
            for issue in report.issues
        )
        else "ok"
    )


def assess_readiness(
    config_obj: Any = None,
    *,
    commercial: bool = False,
    require_email: bool = False,
    environment: Optional[Mapping[str, str]] = None,
    project_root: Optional[Path] = None,
) -> ReadinessReport:
    """Assess startup readiness without network access.

    ``commercial=True`` upgrades missing paid capabilities, LLM credentials,
    company identity and unsafe secret storage from warning to fatal.
    ``require_email=True`` makes Gmail readiness a release gate.  Keeping these
    switches separate allows search/CSV-only deployments to operate safely.
    """

    report = ReadinessReport(profile="commercial" if commercial else "startup")
    environment = os.environ if environment is None else environment

    if config_obj is None:
        try:
            import config as config_module

            config_obj = config_module.config
            if project_root is None:
                project_root = Path(config_module.__file__).resolve().parent
        except Exception as exc:
            report.add(
                "fatal",
                "config.import_failed",
                "config",
                f"配置模块加载失败：{type(exc).__name__}",
                "检查 settings.json 编码、JSON 语法和 Python 依赖。",
            )
            report.checks["config"] = "fatal"
            return report

    settings = getattr(config_obj, "settings", None)
    if not isinstance(settings, Mapping):
        report.add(
            "fatal",
            "config.settings_invalid",
            "config",
            "config.settings 不存在或不是对象。",
            "恢复有效的 settings.json。",
        )
        report.checks["config"] = "fatal"
        return report

    getter = getattr(config_obj, "get_mode", None)
    try:
        mode = getter() if callable(getter) else settings.get("mode", "free")
    except Exception:
        mode = settings.get("mode", "unknown")
    report.mode = _text(mode) or "unknown"
    if report.mode not in VALID_MODES:
        report.add(
            "fatal",
            "mode.invalid",
            "mode",
            f"运行模式无效：{report.mode}",
            "mode 只能是 free 或 paid。",
        )
    report.checks["config"] = "ok"

    _validate_mode_profile(report, settings)
    report.checks["mode"] = (
        "fatal"
        if any(
            issue.severity == "fatal" and issue.component == "mode"
            for issue in report.issues
        )
        else "ok"
    )
    _validate_industry(report, config_obj, settings, commercial)
    _validate_llm(report, settings, environment, commercial)
    active_mcp = _configured_mcp_servers(report, settings, environment, commercial)
    _validate_mode_sources(report, settings, environment, active_mcp, commercial)
    _validate_email(report, settings, environment, require_email)
    _validate_secret_storage(report, settings, commercial)
    _validate_directories(report, project_root)
    return report


def validate_config(
    config_obj: Any = None,
    *,
    commercial: bool = False,
    require_email: bool = False,
    environment: Optional[Mapping[str, str]] = None,
) -> List[str]:
    """Backward-compatible startup API returning formatted issue strings."""

    report = assess_readiness(
        config_obj,
        commercial=commercial,
        require_email=require_email,
        environment=environment,
    )
    return [
        f"[{issue.severity.upper()}][{issue.code}] {issue.message}"
        for issue in report.issues
    ]


def print_startup_banner(warnings: Iterable[str] | ReadinessReport) -> None:
    """Print a concise, secret-safe startup report."""

    if isinstance(warnings, ReadinessReport):
        report = warnings
        lines = [
            f"[{issue.severity.upper()}][{issue.code}] {issue.message}"
            for issue in report.issues
        ]
        status = report.status.upper()
    else:
        lines = list(warnings)
        status = "WARNING"
    if not lines:
        return

    border = "=" * 72
    print(f"\n{border}")
    print(f"  启动前检查：{status}")
    print(border)
    for line in lines:
        print(f"  - {line}")
    print(border)

    try:
        from logger import logger

        for line in lines:
            logger.warning("[StartupCheck] %s", line)
    except Exception:
        pass


def _main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="SDR 离线发布就绪检查")
    parser.add_argument(
        "--commercial",
        action="store_true",
        help="启用商业发布严格检查",
    )
    parser.add_argument(
        "--require-email",
        action="store_true",
        help="把 Gmail 发信能力作为 fatal 发布门槛",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    report = assess_readiness(
        commercial=args.commercial,
        require_email=args.require_email,
    )
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    elif report.issues:
        print_startup_banner(report)
    else:
        print("启动前检查：READY")
    return 2 if report.fatal_issues else 0


if __name__ == "__main__":
    raise SystemExit(_main())
