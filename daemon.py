"""SDR Daemon — 7x24 scheduler for automated lead generation.

Usage:
    python daemon.py              # Start daemon
    python daemon.py --once       # Run one cycle and exit
    python daemon.py --schedule   # Print schedule

The daemon reads daemon_config.json for task schedules and
runs the SDR pipeline on a cron-like interval.
"""
import sys
import time
import json
import signal
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent))

CONFIG_PATH = Path(__file__).parent / "daemon_config.json"
HEALTH_PATH = Path(__file__).parent / ".health"

DEFAULT_CONFIG = {
    "tasks": [
        {
            "name": "daily_germany_automotive",
            "country": "Germany",
            "industry": "automotive",
            "product": "die casting",
            "count": 50,
            "mode": "free",
            "cron": "0 8 * * *",  # 8 AM daily
            "enabled": True,
        },
        {
            "name": "weekly_japan_electronics",
            "country": "Japan",
            "industry": "electronics",
            "product": "pcb assembly",
            "count": 30,
            "mode": "free",
            "cron": "0 9 * * 1",  # 9 AM Monday
            "enabled": False,
        },
    ],
    "settings": {
        "max_daily_cost_usd": 5.0,
        "pause_on_error": True,
        "error_cooldown_minutes": 30,
        "health_check_interval_seconds": 60,
    },
}


class SdrDaemon:
    """7x24 SDR Pipeline Daemon."""

    def __init__(self, config_path: str = None):
        self.config_path = Path(config_path) if config_path else CONFIG_PATH
        self.config = self._load_config()
        self._running = True
        self._last_run: Dict[str, datetime] = {}
        self._error_count = 0
        self._paused_until: datetime = None

        signal.signal(signal.SIGINT, self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)

    def _load_config(self) -> dict:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        # Create default
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        return DEFAULT_CONFIG

    def _handle_stop(self, signum, frame):
        print("\nShutting down daemon...")
        self._running = False

    def _write_health(self, status: str, message: str = ""):
        HEALTH_PATH.write_text(json.dumps({
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "error_count": self._error_count,
        }), encoding="utf-8")

    def _should_run(self, task: dict) -> bool:
        if not task.get("enabled", True):
            return False

        if self._paused_until and datetime.now() < self._paused_until:
            return False

        # Check daily cost budget
        from core.events.agent_context import default_context
        daily_cost = default_context.get_daily_cost()
        max_cost = self.config.get("settings", {}).get("max_daily_cost_usd", 5.0)
        if daily_cost >= max_cost:
            print(f"Daily cost limit reached (${daily_cost:.2f} >= ${max_cost})")
            return False

        # Simple cron-like: run if never run or enough time passed
        name = task["name"]
        if name not in self._last_run:
            return True

        hours_since = (datetime.now() - self._last_run[name]).total_seconds() / 3600
        return hours_since >= 23  # Run at most once per 23 hours

    def run_task(self, task: dict):
        """Execute a single SDR task."""
        from workflow import run_sdr_workflow
        from logger import logger

        name = task["name"]
        print(f"\n[{datetime.now():%H:%M:%S}] Running: {name}")

        try:
            state = run_sdr_workflow(
                country=task["country"],
                industry=task.get("industry", ""),
                product=task.get("product", ""),
                target_count=task.get("count", 50),
                mode=task.get("mode", "free"),
            )

            self._last_run[name] = datetime.now()
            self._error_count = 0
            self._write_health("healthy", f"Task {name}: {state.get_company_count()} leads")

            print(f"  Complete: {state.get_company_count()} companies, "
                  f"{state.get_contact_count()} contacts, "
                  f"{state.elapsed_seconds}s")

        except Exception as e:
            self._error_count += 1
            self._write_health("error", str(e)[:200])
            logger.error(f"Daemon task {name} failed: {e}")
            print(f"  FAILED: {e}")

            if self.config.get("settings", {}).get("pause_on_error", True):
                cooldown = self.config["settings"].get("error_cooldown_minutes", 30)
                self._paused_until = datetime.now() + timedelta(minutes=cooldown)
                print(f"  Paused for {cooldown} minutes")

    def run_once(self):
        """Run all enabled tasks once and exit."""
        for task in self.config.get("tasks", []):
            if self._should_run(task):
                self.run_task(task)

    def run_forever(self):
        """Run daemon loop indefinitely."""
        print("SDR Daemon started. Press Ctrl+C to stop.")
        print(f"Tasks: {len(self.config.get('tasks', []))}")
        print(f"Max daily cost: ${self.config.get('settings', {}).get('max_daily_cost_usd', 5.0)}")
        print("-" * 50)

        self._write_health("starting")

        check_interval = self.config.get("settings", {}).get("health_check_interval_seconds", 60)

        while self._running:
            try:
                ran_any = False
                for task in self.config.get("tasks", []):
                    if self._should_run(task):
                        self.run_task(task)
                        ran_any = True

                if not ran_any:
                    self._write_health("idle")

                # Sleep in small intervals to stay responsive
                for _ in range(check_interval):
                    if not self._running:
                        break
                    time.sleep(1)

            except Exception as e:
                print(f"Daemon loop error: {e}")
                self._error_count += 1
                time.sleep(60)

        self._write_health("stopped")
        print("Daemon stopped.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SDR Daemon")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--schedule", action="store_true", help="Print schedule")
    args = parser.parse_args()

    daemon = SdrDaemon()

    if args.schedule:
        print("Scheduled Tasks:")
        for t in daemon.config.get("tasks", []):
            status = "ENABLED" if t.get("enabled", True) else "DISABLED"
            print(f"  [{status}] {t['name']}: {t['country']} {t.get('industry','')} (x{t.get('count',50)})")
        return

    if args.once:
        daemon.run_once()
    else:
        daemon.run_forever()


if __name__ == "__main__":
    main()
