"""
One-time migration: import historical metrics from daily_metrics.json into V2 SQLite.

This gives V2 SQLite the full historical record (Dec 2025 – Mar 2026) so all
downstream consumers can read from a single source of truth.

Usage:
    python scripts/migrate_metrics_to_v2.py
    python scripts/migrate_metrics_to_v2.py --dry-run
"""

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
METRICS_FILE = PROJECT_ROOT / "data" / "daily_metrics.json"

# Add telegram-bot to path for V2 imports
sys.path.insert(0, str(PROJECT_ROOT / "telegram-bot"))


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_str(value) -> str | None:
    """Convert a JSON value to the string format V2 SQLite expects."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def load_json_metrics() -> list[dict]:
    if not METRICS_FILE.exists():
        print(f"No metrics file at {METRICS_FILE}")
        return []
    data = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    return data.get("entries", [])


def migrate(dry_run: bool = False):
    from v2.infra.sqlite_state_store import SQLiteStateStore, DEFAULT_DB_PATH

    entries = load_json_metrics()
    if not entries:
        print("No entries to migrate.")
        return

    chat_id = int(os.environ.get("OWNER_CHAT_ID", "0"))
    if not chat_id:
        print("OWNER_CHAT_ID not set, using 0 for migration")

    store = SQLiteStateStore()
    conn = store._connect()

    # Field mapping: JSON schema → V2 day_metric field names
    FIELD_MAP = {
        # (json_path, v2_field)
        "sleep.hours": "Sleep",
        "sleep.quality": "Sleep_Quality",
        "weight_lbs": "Weight",
        "mood.morning": "Mood_AM",
        "mood.bedtime": "Mood_PM",
        "energy": "Energy",
        "focus": "Focus",
    }

    migrated = 0
    skipped = 0

    try:
        conn.execute("BEGIN IMMEDIATE")

        for entry in entries:
            date_str = entry.get("date")
            if not date_str:
                continue

            # Check if day already exists
            existing = conn.execute(
                "SELECT day_id FROM day_context WHERE chat_id = ? AND local_date = ?",
                (chat_id, date_str),
            ).fetchone()

            if existing:
                skipped += 1
                continue

            if dry_run:
                migrated += 1
                continue

            # Create day_context row
            day_id = _new_id("day")
            tz = "America/New_York"  # Historical data was all ET
            conn.execute(
                """
                INSERT INTO day_context (day_id, chat_id, local_date, timezone, status, opened_at_utc)
                VALUES (?, ?, ?, ?, 'closed', ?)
                """,
                (day_id, chat_id, date_str, tz, _utc_now_iso()),
            )

            # Insert metrics
            for json_path, v2_field in FIELD_MAP.items():
                parts = json_path.split(".")
                value = entry
                for part in parts:
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        value = None
                        break

                str_val = _safe_str(value)
                if str_val is not None:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO day_metric (day_id, field, value)
                        VALUES (?, ?, ?)
                        """,
                        (day_id, v2_field, str_val),
                    )

            migrated += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    action = "Would migrate" if dry_run else "Migrated"
    print(f"{action} {migrated} entries, skipped {skipped} existing")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    migrate(dry_run=dry_run)
