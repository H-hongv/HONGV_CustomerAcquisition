"""Local health and readiness checks for production deployments.

No check in this module sends a network request.  Provider checks only inspect
local availability/configuration so Docker and process supervisors can call
them frequently without consuming quota.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional


BASE_DIR = Path(__file__).resolve().parent
HEALTH_PATH = BASE_DIR / ".health"
ALERT_LOG_PATH = BASE_DIR / "logs" / "alerts.log"

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except Exception:
    # Health checks must remain usable for diagnosing an incomplete install.
    pass

_STATUS_PRIORITY = {"healthy": 0, "degraded": 1, "unhealthy": 2}
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization|api[-_ ]?key|token|password)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_error(exc: Exception) -> str:
    """Return a bounded error string with common credential forms redacted."""

    text = f"{type(exc).__name__}: {exc}"[:500]
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            # daemon.py historically writes a local, timezone-naive timestamp.
            parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


class HealthMonitor:
    """Aggregate local runtime health into healthy/degraded/unhealthy."""

    def __init__(
        self,
        *,
        health_path: Optional[Path] = None,
        alert_log_path: Optional[Path] = None,
        alert_threshold: int = 3,
        heartbeat_stale_after: timedelta = timedelta(minutes=10),
        commercial_readiness: bool = False,
        require_email: bool = False,
    ):
        self.health_path = Path(health_path) if health_path else HEALTH_PATH
        self.alert_log_path = Path(alert_log_path) if alert_log_path else ALERT_LOG_PATH
        self._alert_threshold = max(1, int(alert_threshold))
        self._alert_cooldown = timedelta(hours=1)
        self._heartbeat_stale_after = heartbeat_stale_after
        self._commercial_readiness = commercial_readiness
        self._require_email = require_email
        self._last_alert: Optional[datetime] = None

    @staticmethod
    def _raise_status(result: Dict[str, Any], candidate: str) -> None:
        current = result.get("status", "healthy")
        if _STATUS_PRIORITY.get(candidate, 0) > _STATUS_PRIORITY.get(current, 0):
            result["status"] = candidate

    def _check_readiness(self, result: Dict[str, Any]) -> None:
        try:
            from config_validator import assess_readiness

            report = assess_readiness(
                commercial=self._commercial_readiness,
                require_email=self._require_email,
                project_root=BASE_DIR,
            )
            result["checks"]["readiness"] = {
                "status": report.status,
                "fatal": len(report.fatal_issues),
                "warnings": len(report.warnings),
                "profile": report.profile,
            }
            if report.fatal_issues:
                self._raise_status(result, "unhealthy")
            elif report.warnings:
                self._raise_status(result, "degraded")
        except Exception as exc:
            result["checks"]["readiness"] = {
                "status": "error",
                "message": _safe_error(exc),
            }
            self._raise_status(result, "degraded")

    def _check_database(self, result: Dict[str, Any]) -> None:
        try:
            from memory.store import memory_store

            stats = memory_store.get_stats()
            result["checks"]["database"] = {
                "status": "ok",
                "companies": int(_dict_value(stats, "total_companies", 0)),
            }
        except Exception as exc:
            result["checks"]["database"] = {
                "status": "error",
                "message": _safe_error(exc),
            }
            self._raise_status(result, "degraded")

    def _check_checkpoint(self, result: Dict[str, Any]) -> None:
        try:
            from workflow.checkpoint import checkpointer

            analytics = checkpointer.get_analytics()
            result["checks"]["checkpoint"] = {
                "status": "ok",
                "runs": int(_dict_value(analytics, "total_runs", 0)),
            }
        except Exception as exc:
            result["checks"]["checkpoint"] = {
                "status": "error",
                "message": _safe_error(exc),
            }
            self._raise_status(result, "degraded")

    def _check_llm(self, result: Dict[str, Any]) -> None:
        try:
            from providers.llm.factory import create_llm_provider

            provider = create_llm_provider()
            available = provider is not None and (
                provider.is_available() if hasattr(provider, "is_available") else True
            )
            result["checks"]["llm"] = {"status": "ok" if available else "unavailable"}
            if not available:
                self._raise_status(result, "degraded")
        except Exception as exc:
            result["checks"]["llm"] = {
                "status": "error",
                "message": _safe_error(exc),
            }
            self._raise_status(result, "degraded")

    def _check_disk(self, result: Dict[str, Any]) -> None:
        try:
            usage = shutil.disk_usage(str(BASE_DIR))
            free_gb = usage.free / (1024**3)
            disk_status = (
                "ok" if free_gb >= 1.0 else "warning" if free_gb >= 0.25 else "error"
            )
            result["checks"]["disk"] = {
                "status": disk_status,
                "free_gb": round(free_gb, 2),
            }
            if disk_status == "error":
                self._raise_status(result, "unhealthy")
            elif disk_status == "warning":
                self._raise_status(result, "degraded")
        except Exception as exc:
            result["checks"]["disk"] = {
                "status": "unknown",
                "message": _safe_error(exc),
            }

    def _read_heartbeat(self) -> Dict[str, Any]:
        if not self.health_path.exists():
            return {}
        raw = self.health_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _check_heartbeat_and_errors(self, result: Dict[str, Any]) -> None:
        try:
            health_data = self._read_heartbeat()
            error_count = int(health_data.get("error_count", 0) or 0)
            daemon_status = str(health_data.get("status", "not_running"))
            timestamp = _parse_timestamp(health_data.get("timestamp"))
            heartbeat = {
                "status": "unknown" if not health_data else "ok",
                "daemon_status": daemon_status,
                "error_count": error_count,
            }
            if timestamp is not None:
                age_seconds = max(0, int((_utc_now() - timestamp).total_seconds()))
                heartbeat["age_seconds"] = age_seconds
                if (
                    daemon_status not in {"stopped", "not_running"}
                    and age_seconds > self._heartbeat_stale_after.total_seconds()
                ):
                    heartbeat["status"] = "stale"
                    self._raise_status(result, "unhealthy")

            if daemon_status == "error":
                heartbeat["status"] = "error"
                self._raise_status(result, "degraded")
            if error_count >= self._alert_threshold:
                heartbeat["status"] = "alert"
                self._raise_status(result, "unhealthy")
                self._maybe_alert(error_count)

            result["checks"]["heartbeat"] = heartbeat
        except Exception as exc:
            result["checks"]["heartbeat"] = {
                "status": "invalid",
                "message": _safe_error(exc),
            }
            self._raise_status(result, "degraded")

    def check(self) -> Dict[str, Any]:
        """Run all local checks and return a JSON-serializable result."""

        result: Dict[str, Any] = {
            "status": "healthy",
            "timestamp": _utc_now().isoformat(),
            "checks": {},
        }
        self._check_readiness(result)
        self._check_database(result)
        self._check_checkpoint(result)
        self._check_llm(result)
        self._check_disk(result)
        self._check_heartbeat_and_errors(result)
        return result

    def _maybe_alert(self, error_count: int) -> None:
        now = _utc_now()
        if self._last_alert and now - self._last_alert < self._alert_cooldown:
            return

        alert = {
            "timestamp": now.isoformat(),
            "type": "error_threshold",
            "error_count": error_count,
            "message": (
                f"SDR Agent has {error_count} consecutive errors; "
                "manual intervention may be required."
            ),
        }
        self.alert_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.alert_log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(alert, ensure_ascii=False) + "\n")
        self._last_alert = now

    def is_healthy(self) -> bool:
        """Return True while the process remains operational."""

        return self.check()["status"] in {"healthy", "degraded"}

    def get_status_page(self) -> str:
        """Generate a concise human-readable status page."""

        result = self.check()
        lines = [
            "=" * 56,
            f"  SDR Agent Health: {result['status'].upper()}",
            f"  Time: {result['timestamp']}",
            "=" * 56,
        ]
        for name, check in result.get("checks", {}).items():
            check_status = str(check.get("status", "unknown")).upper()
            details = []
            for key in (
                "companies",
                "runs",
                "free_gb",
                "fatal",
                "warnings",
                "error_count",
                "age_seconds",
            ):
                if key in check:
                    details.append(f"{key}={check[key]}")
            if check.get("message"):
                details.append(str(check["message"]))
            suffix = f" ({', '.join(details)})" if details else ""
            lines.append(f"  [{check_status}] {name}{suffix}")
        return "\n".join(lines)


def _dict_value(value: Any, key: str, default: Any) -> Any:
    return value.get(key, default) if isinstance(value, dict) else default


def readiness_snapshot(
    *,
    commercial: bool = False,
    require_email: bool = False,
    config_obj: Any = None,
    environment: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Expose the offline release gate as a health-compatible dictionary."""

    from config_validator import assess_readiness

    return assess_readiness(
        config_obj,
        commercial=commercial,
        require_email=require_email,
        environment=environment,
    ).to_dict()


health_monitor = HealthMonitor(
    commercial_readiness=os.getenv("SDR_COMMERCIAL_READINESS", "") == "1",
    require_email=os.getenv("SDR_REQUIRE_EMAIL", "") == "1",
)


def quick_health_check() -> bool:
    """Docker/process-supervisor health check."""

    try:
        return health_monitor.is_healthy()
    except Exception:
        return False


if __name__ == "__main__":
    print(health_monitor.get_status_page())
