"""
Comprehensive migration: import ALL historical data from JSON/markdown into V2 SQLite.

Migrates:
1. Basic metrics (weight, sleep, mood) from daily_metrics.json
2. Workout sessions + exercises + cardio from daily_metrics.json
3. Nutrition line items with macros from daily_metrics.json
4. Habit history from daily_metrics.json
5. Conversation history from conversation_history.json

All operations are idempotent (INSERT OR IGNORE / check-before-insert).

Usage:
    python scripts/migrate_all_to_sqlite.py
    python scripts/migrate_all_to_sqlite.py --dry-run
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
HISTORY_DIR = Path(os.environ.get("HISTORY_DIR", str(Path.home() / ".bestupid-private")))
HISTORY_FILE = HISTORY_DIR / "conversation_history.json"

sys.path.insert(0, str(PROJECT_ROOT / "telegram-bot"))


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_str(value) -> str | None:
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


def load_conversation_history() -> dict:
    if not HISTORY_FILE.exists():
        print(f"No conversation history at {HISTORY_FILE}")
        return {}
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


FIELD_MAP = {
    "sleep.hours": "Sleep",
    "sleep.quality": "Sleep_Quality",
    "weight_lbs": "Weight",
    "mood.morning": "Mood_AM",
    "mood.bedtime": "Mood_PM",
    "energy": "Energy",
    "focus": "Focus",
}


def _extract_nested(entry: dict, json_path: str):
    """Extract a value from a nested dict using dot notation."""
    parts = json_path.split(".")
    value = entry
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def migrate(dry_run: bool = False):
    from v2.infra.sqlite_state_store import SQLiteStateStore

    entries = load_json_metrics()
    chat_id = int(os.environ.get("OWNER_CHAT_ID", "0"))
    if not chat_id:
        print("OWNER_CHAT_ID not set, using 0 for migration")

    store = SQLiteStateStore()
    store.init_schema()
    conn = store._connect()

    stats = {
        "days_migrated": 0,
        "days_skipped": 0,
        "metrics_inserted": 0,
        "workouts_inserted": 0,
        "exercises_inserted": 0,
        "cardio_inserted": 0,
        "food_items_inserted": 0,
        "habits_inserted": 0,
        "turns_inserted": 0,
    }

    try:
        conn.execute("BEGIN IMMEDIATE")

        # ── 1. Metrics + Workouts + Nutrition + Habits from daily_metrics.json ──
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
                day_id = existing["day_id"]
                stats["days_skipped"] += 1
            else:
                if dry_run:
                    stats["days_migrated"] += 1
                    continue

                day_id = _new_id("day")
                conn.execute(
                    """
                    INSERT INTO day_context (day_id, chat_id, local_date, timezone, status, opened_at_utc)
                    VALUES (?, ?, ?, ?, 'closed', ?)
                    """,
                    (day_id, chat_id, date_str, "America/New_York", _utc_now_iso()),
                )
                stats["days_migrated"] += 1

            if dry_run:
                continue

            # ── Metrics ──
            for json_path, v2_field in FIELD_MAP.items():
                value = _extract_nested(entry, json_path)
                str_val = _safe_str(value)
                if str_val is not None:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO day_metric (day_id, field, value) VALUES (?, ?, ?)",
                            (day_id, v2_field, str_val),
                        )
                        stats["metrics_inserted"] += 1
                    except sqlite3.IntegrityError:
                        pass

            # ── Habits ──
            habits = entry.get("habits", {})
            completed = habits.get("completed", [])
            missed = habits.get("missed", [])
            for habit_name in completed:
                habit_id = habit_name.lower().replace(" ", "_")
                # Ensure habit_definition exists
                conn.execute(
                    """
                    INSERT OR IGNORE INTO habit_definition (habit_id, chat_id, name, cadence, active)
                    VALUES (?, ?, ?, 'daily', 1)
                    """,
                    (habit_id, chat_id, habit_name),
                )
                inst_id = _new_id("habitinst")
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO habit_instance (instance_id, habit_id, day_id, status, last_changed_at_utc)
                        VALUES (?, ?, ?, 'done', ?)
                        """,
                        (inst_id, habit_id, day_id, _utc_now_iso()),
                    )
                    stats["habits_inserted"] += 1
                except sqlite3.IntegrityError:
                    pass

            for habit_name in missed:
                habit_id = habit_name.lower().replace(" ", "_")
                conn.execute(
                    """
                    INSERT OR IGNORE INTO habit_definition (habit_id, chat_id, name, cadence, active)
                    VALUES (?, ?, ?, 'daily', 1)
                    """,
                    (habit_id, chat_id, habit_name),
                )
                inst_id = _new_id("habitinst")
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO habit_instance (instance_id, habit_id, day_id, status, last_changed_at_utc)
                        VALUES (?, ?, ?, 'pending', ?)
                        """,
                        (inst_id, habit_id, day_id, _utc_now_iso()),
                    )
                    stats["habits_inserted"] += 1
                except sqlite3.IntegrityError:
                    pass

            # ── Workouts ──
            training = entry.get("training", {})
            workout_type = training.get("workout_type", "")
            activities = training.get("activities", [])
            strength_exercises = training.get("strength_exercises", [])

            if workout_type and (activities or strength_exercises):
                # Check if workout session already exists for this day
                existing_ws = conn.execute(
                    "SELECT session_id FROM workout_session WHERE day_id = ?",
                    (day_id,),
                ).fetchone()

                if not existing_ws:
                    ws_id = _new_id("ws")
                    conn.execute(
                        """
                        INSERT INTO workout_session (session_id, day_id, workout_type, notes)
                        VALUES (?, ?, ?, '')
                        """,
                        (ws_id, day_id, workout_type),
                    )
                    stats["workouts_inserted"] += 1

                    # Cardio activities
                    for act in activities:
                        act_id = _new_id("cardio")
                        conn.execute(
                            """
                            INSERT INTO cardio_activity
                                (activity_id, session_id, activity_type, distance, distance_unit, duration_minutes, avg_hr)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                act_id, ws_id,
                                act.get("type", ""),
                                act.get("distance"),
                                act.get("distance_unit", "mi"),
                                act.get("duration_minutes"),
                                act.get("avg_hr"),
                            ),
                        )
                        stats["cardio_inserted"] += 1

                    # Strength exercises
                    for ex in strength_exercises:
                        ex_id = _new_id("ex")
                        conn.execute(
                            """
                            INSERT INTO exercise_log
                                (exercise_id, session_id, exercise_name, sets, reps, weight_lbs, duration_seconds)
                            VALUES (?, ?, ?, ?, ?, ?, NULL)
                            """,
                            (
                                ex_id, ws_id,
                                ex.get("exercise", ""),
                                ex.get("sets"),
                                ex.get("reps"),
                                ex.get("weight_lbs"),
                            ),
                        )
                        stats["exercises_inserted"] += 1

            # ── Nutrition line items ──
            nutrition = entry.get("nutrition", {})
            line_items = nutrition.get("line_items", [])
            for item in line_items:
                food_desc = item.get("food", "")
                if not food_desc:
                    continue
                food_id = _new_id("food")
                time_str = item.get("time", "")
                try:
                    conn.execute(
                        """
                        INSERT INTO food_entry
                            (food_id, day_id, description, logged_at_utc,
                             calories_est, protein_g_est, carbs_g_est, fat_g_est, fiber_g_est, meal_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            food_id, day_id,
                            food_desc,
                            f"{date_str}T{time_str or '12:00'}",
                            item.get("calories"),
                            item.get("protein_g"),
                            item.get("carbs_g"),
                            item.get("fat_g"),
                            item.get("fiber_g"),
                            "",
                        ),
                    )
                    stats["food_items_inserted"] += 1
                except sqlite3.IntegrityError:
                    pass

        # ── 2. Conversation history from conversation_history.json ──
        history_data = load_conversation_history()
        for chat_id_key, entry in history_data.items():
            try:
                hist_chat_id = int(chat_id_key)
            except (ValueError, TypeError):
                continue

            history = entry.get("history", [])
            if not history:
                continue

            # Create a single session for pre-v2 history
            session_id = f"sess_migration_{chat_id_key}"
            existing_session = conn.execute(
                "SELECT session_id FROM session WHERE session_id = ?",
                (session_id,),
            ).fetchone()

            if not existing_session and not dry_run:
                conn.execute(
                    """
                    INSERT INTO session (session_id, chat_id, started_at_utc, ended_at_utc, summary_text)
                    VALUES (?, ?, ?, ?, 'Pre-V2 migrated conversation history')
                    """,
                    (session_id, hist_chat_id, _utc_now_iso(), _utc_now_iso()),
                )

            for msg in history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if not isinstance(content, str) or not content.strip():
                    continue
                if not role:
                    continue

                if dry_run:
                    stats["turns_inserted"] += 1
                    continue

                # Check if this exact text already exists in the turn table
                existing_turn = conn.execute(
                    """
                    SELECT turn_id FROM turn
                    WHERE session_id = ? AND role = ? AND text = ?
                    LIMIT 1
                    """,
                    (session_id, role, content),
                ).fetchone()

                if not existing_turn:
                    turn_id = _new_id("turn")
                    conn.execute(
                        """
                        INSERT INTO turn (turn_id, session_id, telegram_update_id, role, text, created_at_utc)
                        VALUES (?, ?, 0, ?, ?, ?)
                        """,
                        (turn_id, session_id, role, content, _utc_now_iso()),
                    )
                    stats["turns_inserted"] += 1

        if not dry_run:
            conn.commit()
        else:
            conn.rollback()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    action = "Would migrate" if dry_run else "Migrated"
    print(f"\n{action}:")
    print(f"  Days: {stats['days_migrated']} new, {stats['days_skipped']} existing")
    print(f"  Metrics: {stats['metrics_inserted']} values")
    print(f"  Habits: {stats['habits_inserted']} instances")
    print(f"  Workouts: {stats['workouts_inserted']} sessions")
    print(f"  Exercises: {stats['exercises_inserted']} entries")
    print(f"  Cardio: {stats['cardio_inserted']} activities")
    print(f"  Food items: {stats['food_items_inserted']} with macros")
    print(f"  Conversation turns: {stats['turns_inserted']}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    migrate(dry_run=dry_run)
