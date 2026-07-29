"""Health check + error alerting for SDR production deployment.

Provides:
- Health endpoint (file-based, Docker HEALTHCHECK compatible)
- Error threshold alerting
- System status summary
"""
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional

HEALTH_PATH = Path(__file__).parent / ".health"
ALERT_LOG_PATH = Path(__file__).parent / "logs" / "alerts.log"


class HealthMonitor:
    """Production health monitoring for SDR Agent."""

    def __init__(self):
        self._alert_threshold = 3  # consecutive errors before alert
        self._alert_cooldown = timedelta(hours=1)  # min time between alerts
        self._last_alert: Optional[datetime] = None

    def check(self) -> Dict:
        """Run full health check. Returns status dict."""
        status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {},
        }

        # 1. Database
        try:
            from memory.store import memory_store
            stats = memory_store.get_stats()
            status["checks"]["database"] = {"status": "ok", "companies": stats["total_companies"]}
        except Exception as e:
            status["checks"]["database"] = {"status": "error", "message": str(e)}
            status["status"] = "degraded"

        # 2. Checkpoint
        try:
            from workflow.checkpoint import checkpointer
            analytics = checkpointer.get_analytics()
            status["checks"]["checkpoint"] = {"status": "ok", "runs": analytics["total_runs"]}
        except Exception as e:
            status["checks"]["checkpoint"] = {"status": "error", "message": str(e)}
            status["status"] = "degraded"

        # 3. LLM provider
        try:
            from providers.llm.factory import create_llm_provider
            provider = create_llm_provider()
            available = provider.is_available() if hasattr(provider, "is_available") else True
            status["checks"]["llm"] = {"status": "ok" if available else "degraded"}
        except Exception as e:
            status["checks"]["llm"] = {"status": "error", "message": str(e)}
            status["status"] = "degraded"

        # 4. Disk space
        try:
            import shutil
            usage = shutil.disk_usage(str(Path(__file__).parent))
            free_gb = usage.free / (1024**3)
            status["checks"]["disk"] = {
                "status": "ok" if free_gb > 1 else "warning",
                "free_gb": round(free_gb, 1),
            }
        except Exception:
            status["checks"]["disk"] = {"status": "unknown"}

        # 5. Recent errors
        try:
            health_data = {}
            if HEALTH_PATH.exists():
                health_data = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
            error_count = health_data.get("error_count", 0)
            if error_count >= self._alert_threshold:
                status["status"] = "unhealthy"
                status["checks"]["errors"] = {"status": "alert", "count": error_count}
                self._maybe_alert(error_count)
            else:
                status["checks"]["errors"] = {"status": "ok", "count": error_count}
        except Exception:
            status["checks"]["errors"] = {"status": "unknown"}

        return status

    def _maybe_alert(self, error_count: int):
        """Send alert if threshold exceeded and cooldown passed."""
        now = datetime.now()
        if self._last_alert and now - self._last_alert < self._alert_cooldown:
            return

        alert = {
            "timestamp": now.isoformat(),
            "type": "error_threshold",
            "error_count": error_count,
            "message": f"SDR Agent has {error_count} consecutive errors. Manual intervention may be required.",
        }

        # Write to alert log
        os.makedirs(ALERT_LOG_PATH.parent, exist_ok=True)
        with open(ALERT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(alert, ensure_ascii=False) + "\n")

        self._last_alert = now

    def is_healthy(self) -> bool:
        """Quick health check — returns True if system is operational."""
        result = self.check()
        return result["status"] in ("healthy", "degraded")

    def get_status_page(self) -> str:
        """Generate a human-readable status page."""
        result = self.check()
        lines = [
            "=" * 50,
            f"  SDR Agent Health Status: {result['status'].upper()}",
            f"  Time: {result['timestamp']}",
            "=" * 50,
        ]
        for name, check in result.get("checks", {}).items():
            icon = "OK" if check.get("status") == "ok" else "!!"
            detail = check.get("message", check.get("companies", check.get("runs", "")))
            lines.append(f"  [{icon}] {name}: {detail}")
        return "\n".join(lines)


# Global instance
health_monitor = HealthMonitor()


def quick_health_check() -> bool:
    """One-line health check for Docker HEALTHCHECK."""
    try:
        return health_monitor.is_healthy()
    except Exception:
        return False


if __name__ == "__main__":
    print(health_monitor.get_status_page())
