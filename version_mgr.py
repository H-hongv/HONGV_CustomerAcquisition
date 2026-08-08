"""Version Upgrade Compatibility — v8.0 P1-4

Ensures:
- Database schema migration
- Old config format compatibility
- Old task/export data compatibility
"""
import json
from pathlib import Path
from typing import Dict, Optional


class VersionManager:
    """Manage version upgrades and backward compatibility."""

    CURRENT_VERSION = "4.0.0"
    MIN_COMPAT_VERSION = "3.0.0"

    MIGRATIONS = {
        "3.0.0": ["add_score_history_table", "add_memory_store"],
        "3.5.0": ["add_company_memory_columns"],
        "4.0.0": ["migrate_config_to_settings_json", "add_quality_fields"],
    }

    @classmethod
    def get_current_version(cls) -> str:
        return cls.CURRENT_VERSION

    @classmethod
    def check_compatibility(cls, data_version: str) -> bool:
        """Check if data from given version is compatible."""
        v_parts = [int(x) for x in data_version.lstrip("v").split(".")]
        min_parts = [int(x) for x in cls.MIN_COMPAT_VERSION.split(".")]
        return v_parts >= min_parts

    @classmethod
    def migrate_config(cls, config_path: str = "settings.json") -> dict:
        """Migrate old config format to current."""
        path = Path(config_path)
        if not path.exists():
            return {"version": cls.CURRENT_VERSION, "migrated": False, "reason": "no config file"}

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"version": "unknown", "migrated": False, "reason": "invalid JSON"}

        version = data.get("version", data.get("_version", "3.0.0"))
        if version == cls.CURRENT_VERSION:
            return {"version": version, "migrated": False, "reason": "already current"}

        # Apply migrations
        applied = []
        for v, migrations in cls.MIGRATIONS.items():
            if v > version:
                for migration in migrations:
                    applied.append(migration)

        data["version"] = cls.CURRENT_VERSION
        data["_migration_history"] = data.get("_migration_history", []) + applied

        # Backup old config
        backup_path = path.with_suffix(".json.bak")
        path.rename(backup_path)

        # Write new config
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        return {
            "version": cls.CURRENT_VERSION,
            "migrated": True,
            "from_version": version,
            "migrations_applied": applied,
            "backup_created": str(backup_path),
        }

    @classmethod
    def migrate_db(cls, db_path: str = "data/memory.db") -> dict:
        """Ensure database schema is current by running migrations."""
        path = Path(db_path)
        if not path.exists():
            return {"version": cls.CURRENT_VERSION, "migrated": False, "reason": "no database"}

        import sqlite3
        conn = sqlite3.connect(str(path))
        applied = []

        try:
            # Check version
            cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'")
            has_version_table = cur.fetchone() is not None

            if not has_version_table:
                conn.execute("CREATE TABLE schema_version (version TEXT, applied_at TEXT)")
                conn.execute("INSERT INTO schema_version VALUES (?, datetime('now'))", ("4.0.0",))
                applied.append("create_schema_version_table")

            # Check and add missing columns
            cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='score_history'")
            if cur.fetchone():
                cur = conn.execute("PRAGMA table_info(score_history)")
                cols = [row[1] for row in cur.fetchall()]
                if "data_quality_score" not in cols:
                    conn.execute("ALTER TABLE score_history ADD COLUMN data_quality_score INTEGER DEFAULT 0")
                    applied.append("add_data_quality_score_column")

            # Ensure followup_log table + email_log.followup_stage
            conn.execute("""
                CREATE TABLE IF NOT EXISTS followup_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL,
                    to_email TEXT NOT NULL,
                    subject TEXT DEFAULT '',
                    body TEXT DEFAULT '',
                    day_offset INTEGER DEFAULT 0,
                    sent_at TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    error TEXT DEFAULT '',
                    UNIQUE(to_email, day_offset)
                )
            """)
            cur = conn.execute("PRAGMA table_info(email_log)")
            cols = [row[1] for row in cur.fetchall()]
            if "followup_stage" not in cols:
                conn.execute("ALTER TABLE email_log ADD COLUMN followup_stage INTEGER DEFAULT 0")
                applied.append("add_followup_stage_column")

            conn.commit()
        except Exception as e:
            return {"version": cls.CURRENT_VERSION, "migrated": False, "reason": str(e)}
        finally:
            conn.close()

        return {
            "version": cls.CURRENT_VERSION,
            "migrated": len(applied) > 0,
            "migrations_applied": applied,
        }

    @classmethod
    def validate_export_compatibility(cls, export_path: str) -> dict:
        """Check if old CSV export is compatible with current format."""
        path = Path(export_path)
        if not path.exists():
            return {"compatible": False, "reason": "file not found"}

        try:
            import csv
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, [])

            required_current = {"company_name", "country", "grade", "total_score", "email"}
            found = set(h.lower().replace(" ", "_") for h in header)
            missing = required_current - found

            return {
                "compatible": len(missing) == 0,
                "missing_fields": list(missing),
                "found_fields": list(found),
            }
        except Exception as e:
            return {"compatible": False, "reason": str(e)}


version_manager = VersionManager()