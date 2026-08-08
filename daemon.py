"""SDR Daemon - unified scheduler entry (Phase 3-P3).

Legacy CLI entry point that now delegates all scheduling to
AutoOutreachScheduler (settings.auto_outreach). Keeps the
``--once``/``--schedule`` flags and maintains the ``.health``
heartbeat file consumed by health.py.

One-time migration of daemon_config.json -> settings.auto_outreach
happens on construction (idempotent), eliminating the dual-scheduler
conflict between the old daemon and the UI-driven auto scheduler.
"""
import json
import os
import signal
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

CONFIG_PATH = Path(__file__).parent / "daemon_config.json"
HEALTH_PATH = Path(__file__).parent / ".health"


def _map_cron_to_schedule(cron: str) -> dict:
    """Map a legacy 5-field cron string to {frequency, run_at, day_of_week}."""
    try:
        minute, hour, _, _, dow = str(cron or "").split()
        run_at = f"{int(hour):02d}:{int(minute):02d}"
    except (ValueError, TypeError):
        return {"frequency": "daily", "run_at": "09:00", "day_of_week": 1}
    if str(dow).isdigit() and 0 <= int(dow) <= 6:
        return {"frequency": "weekly", "run_at": run_at, "day_of_week": int(dow)}
    return {"frequency": "daily", "run_at": run_at, "day_of_week": 1}


def migrate_legacy_config(legacy_path=None) -> int:
    """One-time migration of daemon_config.json into settings.auto_outreach.

    Idempotent: skips when auto_outreach already has tasks. Returns the
    number of tasks migrated (0 when nothing to do / already migrated).
    """
    legacy = Path(legacy_path) if legacy_path else CONFIG_PATH
    if not legacy.exists():
        return 0
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
        tasks = data.get("tasks") or []
    except Exception:
        return 0
    if not tasks:
        return 0
    import config as config_module
    cfg = config_module.config.get("auto_outreach", {}) or {}
    if not isinstance(cfg, dict):
        cfg = {}
    if cfg.get("tasks"):
        return 0
    migrated = []
    for t in tasks:
        name = str(t.get("name", "") or "").strip()
        if not name:
            continue
        sched = _map_cron_to_schedule(str(t.get("cron", "") or ""))
        migrated.append({
            "name": name,
            "country": str(t.get("country", "") or ""),
            "industry": str(t.get("industry", "") or ""),
            "product": str(t.get("product", "") or ""),
            "target_count": int(t.get("count", 20) or 20),
            "mode": str(t.get("mode", "free") or "free"),
            "frequency": sched["frequency"],
            "run_at": sched["run_at"],
            "day_of_week": sched["day_of_week"],
            "send_emails": False,
            "enabled": bool(t.get("enabled", True)),
        })
    if not migrated:
        return 0
    cfg["tasks"] = migrated
    config_module.config.settings["auto_outreach"] = cfg
    config_module.config.save()
    backup = legacy.with_suffix(legacy.suffix + ".migrated.bak")
    try:
        if not backup.exists():
            os.replace(str(legacy), str(backup))
    except OSError:
        pass
    return len(migrated)


class SdrDaemon:
    """Legacy-compatible daemon wrapper around AutoOutreachScheduler."""

    def __init__(self, config_path: str = None, migrate: bool = True):
        self.config_path = Path(config_path) if config_path else CONFIG_PATH
        self.HEALTH_PATH = HEALTH_PATH
        self._running = True
        self._error_count = 0
        # One-time migration only for the real default config path (CLI/GUI-free entry).
        if migrate and config_path is None:
            migrate_legacy_config()
        signal.signal(signal.SIGINT, self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)

    def _handle_stop(self, signum, frame):
        print("\nShutting down daemon...")
        self._running = False

    def _write_health(self, status: str, message: str = ""):
        self.HEALTH_PATH.write_text(json.dumps({
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "error_count": self._error_count,
        }), encoding="utf-8")

    @staticmethod
    def _scheduler():
        from tools.outreach.auto_scheduler import auto_outreach_scheduler
        return auto_outreach_scheduler

    def run_once(self) -> list:
        """Run all enabled tasks once and exit (delegated to auto scheduler)."""
        results = self._scheduler().run_all(dry_run=False)
        ok = sum(1 for r in results if r.get("status") == "ok")
        print(f"SDR run complete: {ok}/{len(results)} tasks ok")
        return results

    def run_forever(self):
        """Start the auto scheduler thread and maintain the .health heartbeat."""
        print("SDR Daemon started (unified scheduler). Press Ctrl+C to stop.")
        sched = self._scheduler()
        sched.start()
        self._write_health("starting")
        try:
            while self._running:
                self._write_health(
                    "healthy" if sched.running else "idle",
                    f"auto_scheduler_running={sched.running}",
                )
                for _ in range(30):
                    if not self._running:
                        break
                    time.sleep(1)
        finally:
            self._write_health("stopped")
            print("Daemon stopped.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SDR Daemon (unified scheduler)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--schedule", action="store_true", help="Print schedule")
    args = parser.parse_args()

    daemon = SdrDaemon()

    if args.schedule:
        print("Scheduled Tasks (settings.auto_outreach):")
        for t in daemon._scheduler().tasks():
            status = "ENABLED" if t.get("enabled", False) else "DISABLED"
            freq = "daily" if t.get("frequency") == "daily" else "weekly"
            print(f"  [{status}] {t['name']}: {t.get('country', '')} {t.get('industry', '')} "
                  f"({freq} {t.get('run_at', '09:00')} x{t.get('target_count', 20)})")
        return

    if args.once:
        daemon.run_once()
    else:
        daemon.run_forever()


if __name__ == "__main__":
    main()
