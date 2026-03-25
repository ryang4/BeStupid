from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

import frontmatter

from v2.domain.models import DaySnapshot, MemoryCandidateRecord, ResolvedNow

DEFAULT_TIMEZONE = os.environ.get("TZ", "America/New_York")
PRIVATE_DIR = Path(os.environ.get("HISTORY_DIR", str(Path.home() / ".bestupid-private")))
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", str(Path(__file__).resolve().parents[3])))
DEFAULT_DB_PATH = PRIVATE_DIR / "assistant_state.db"
HABITS_PATH = PROJECT_ROOT / "content" / "config" / "habits.md"
PRIVATE_DAY_LOG_DIR = PRIVATE_DIR / "day_logs"

DAY_METRIC_FIELDS = {
    "Weight",
    "Sleep",
    "Sleep_Quality",
    "Mood_AM",
    "Mood_PM",
    "Energy",
    "Focus",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _json_dumps(value: Any) -> str:
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _normalize_subject_key(kind: str, payload: dict[str, Any]) -> str:
    if kind == "preference":
        subject = str(payload.get("subject", "general")).strip().lower() or "general"
        statement = str(payload.get("statement", "")).strip().lower()
        return f"preference:{subject}:{statement[:80]}"
    if kind == "relationship":
        name = str(payload.get("name", "")).strip().lower()
        role = str(payload.get("role", "")).strip().lower()
        return f"relationship:{name}:{role[:80]}"
    if kind == "fact":
        fact = str(payload.get("fact", "")).strip().lower()
        return f"fact:{fact[:120]}"
    if kind == "commitment":
        title = str(payload.get("title", "")).strip().lower()
        return f"commitment:{title[:120]}"
    return f"{kind}:{uuid4().hex[:8]}"


class SQLiteStateStore:
    """Canonical private state store for the Telegram assistant."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_profile (
                    chat_id INTEGER PRIMARY KEY,
                    home_timezone TEXT NOT NULL,
                    current_timezone TEXT NOT NULL,
                    timezone_source TEXT NOT NULL,
                    location_label TEXT NOT NULL DEFAULT '',
                    coach_style TEXT NOT NULL DEFAULT 'adaptive_firm',
                    quiet_hours_start_local TEXT NOT NULL DEFAULT '22:30',
                    quiet_hours_end_local TEXT NOT NULL DEFAULT '08:00',
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS processed_update (
                    telegram_update_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    processed_at_utc TEXT NOT NULL,
                    PRIMARY KEY (telegram_update_id, chat_id)
                );

                CREATE TABLE IF NOT EXISTS day_context (
                    day_id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    local_date TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    status TEXT NOT NULL,
                    opened_at_utc TEXT NOT NULL,
                    closed_at_utc TEXT NOT NULL DEFAULT '',
                    state_version INTEGER NOT NULL DEFAULT 1,
                    UNIQUE (chat_id, local_date)
                );

                CREATE TABLE IF NOT EXISTS session (
                    session_id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    started_at_utc TEXT NOT NULL,
                    ended_at_utc TEXT NOT NULL DEFAULT '',
                    summary_text TEXT NOT NULL DEFAULT '',
                    active_topics_json TEXT NOT NULL DEFAULT '[]',
                    open_questions_json TEXT NOT NULL DEFAULT '[]',
                    correction_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS turn (
                    turn_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    telegram_update_id INTEGER NOT NULL DEFAULT 0,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES session(session_id)
                );

                CREATE TABLE IF NOT EXISTS tool_event (
                    tool_event_id TEXT PRIMARY KEY,
                    turn_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    validated_args_json TEXT NOT NULL,
                    result_summary TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'completed',
                    FOREIGN KEY (turn_id) REFERENCES turn(turn_id)
                );

                CREATE TABLE IF NOT EXISTS memory_candidate (
                    candidate_id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_turn_id TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS approved_memory (
                    memory_id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    subject_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    active INTEGER NOT NULL,
                    valid_from_utc TEXT NOT NULL,
                    valid_to_utc TEXT NOT NULL DEFAULT '',
                    source_candidate_id TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS open_loop (
                    loop_id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    due_at_utc TEXT NOT NULL DEFAULT '',
                    snoozed_until_utc TEXT NOT NULL DEFAULT '',
                    day_id TEXT NOT NULL DEFAULT '',
                    source_turn_id TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS habit_definition (
                    habit_id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    cadence TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS habit_instance (
                    instance_id TEXT PRIMARY KEY,
                    habit_id TEXT NOT NULL,
                    day_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_changed_at_utc TEXT NOT NULL,
                    UNIQUE (habit_id, day_id),
                    FOREIGN KEY (habit_id) REFERENCES habit_definition(habit_id),
                    FOREIGN KEY (day_id) REFERENCES day_context(day_id)
                );

                CREATE TABLE IF NOT EXISTS reminder_send (
                    send_id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    reminder_kind TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    scheduled_slot_local TEXT NOT NULL,
                    sent_at_utc TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    UNIQUE (chat_id, reminder_kind, target_id, scheduled_slot_local)
                );

                CREATE TABLE IF NOT EXISTS audit_event (
                    event_id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS day_metric (
                    day_id TEXT NOT NULL,
                    field TEXT NOT NULL,
                    value TEXT NOT NULL,
                    PRIMARY KEY (day_id, field),
                    FOREIGN KEY (day_id) REFERENCES day_context(day_id)
                );

                CREATE TABLE IF NOT EXISTS food_entry (
                    food_id TEXT PRIMARY KEY,
                    day_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    logged_at_utc TEXT NOT NULL,
                    FOREIGN KEY (day_id) REFERENCES day_context(day_id)
                );

                CREATE INDEX IF NOT EXISTS idx_open_loop_due
                    ON open_loop(chat_id, status, due_at_utc);
                CREATE INDEX IF NOT EXISTS idx_habit_instance_day
                    ON habit_instance(day_id, habit_id);
                CREATE INDEX IF NOT EXISTS idx_memory_candidate_status
                    ON memory_candidate(chat_id, status, created_at_utc);
                CREATE INDEX IF NOT EXISTS idx_approved_memory_lookup
                    ON approved_memory(chat_id, kind, active, valid_to_utc, version);
                CREATE INDEX IF NOT EXISTS idx_turn_session
                    ON turn(session_id, created_at_utc);
                CREATE INDEX IF NOT EXISTS idx_audit_event_chat
                    ON audit_event(chat_id, created_at_utc);
                CREATE INDEX IF NOT EXISTS idx_food_entry_day
                    ON food_entry(day_id);

                CREATE TABLE IF NOT EXISTS workout_session (
                    session_id TEXT PRIMARY KEY,
                    day_id TEXT NOT NULL,
                    workout_type TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (day_id) REFERENCES day_context(day_id)
                );

                CREATE TABLE IF NOT EXISTS exercise_log (
                    exercise_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    exercise_name TEXT NOT NULL,
                    sets INTEGER,
                    reps INTEGER,
                    weight_lbs REAL,
                    duration_seconds INTEGER,
                    FOREIGN KEY (session_id) REFERENCES workout_session(session_id)
                );

                CREATE TABLE IF NOT EXISTS cardio_activity (
                    activity_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    distance REAL,
                    distance_unit TEXT NOT NULL DEFAULT 'mi',
                    duration_minutes REAL,
                    avg_hr INTEGER,
                    FOREIGN KEY (session_id) REFERENCES workout_session(session_id)
                );

                CREATE TABLE IF NOT EXISTS token_usage (
                    chat_id INTEGER PRIMARY KEY,
                    total_input_tokens INTEGER NOT NULL DEFAULT 0,
                    total_output_tokens INTEGER NOT NULL DEFAULT 0,
                    daily_input_tokens INTEGER NOT NULL DEFAULT 0,
                    daily_output_tokens INTEGER NOT NULL DEFAULT 0,
                    daily_token_date TEXT NOT NULL DEFAULT '',
                    updated_at_utc TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_workout_session_day
                    ON workout_session(day_id);
                CREATE INDEX IF NOT EXISTS idx_exercise_log_session
                    ON exercise_log(session_id);
                CREATE INDEX IF NOT EXISTS idx_cardio_activity_session
                    ON cardio_activity(session_id);
                """
            )
            # ALTER TABLE for food_entry macro columns — safe to fail if columns exist
            for col_def in [
                "calories_est INTEGER",
                "protein_g_est INTEGER",
                "carbs_g_est INTEGER",
                "fat_g_est INTEGER",
                "fiber_g_est INTEGER",
                "meal_type TEXT",
            ]:
                col_name = col_def.split()[0]
                try:
                    conn.execute(f"ALTER TABLE food_entry ADD COLUMN {col_def}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # ALTER TABLE for open_loop zombie detection columns
            for col_def in [
                "created_at_utc TEXT NOT NULL DEFAULT ''",
                "rollover_count INTEGER NOT NULL DEFAULT 0",
            ]:
                try:
                    conn.execute(f"ALTER TABLE open_loop ADD COLUMN {col_def}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # ALTER TABLE for open_loop daily todo columns
            for col_def in [
                "category TEXT NOT NULL DEFAULT ''",
                "source TEXT NOT NULL DEFAULT ''",
                "is_top3 INTEGER NOT NULL DEFAULT 0",
                "notes TEXT NOT NULL DEFAULT ''",
            ]:
                try:
                    conn.execute(f"ALTER TABLE open_loop ADD COLUMN {col_def}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # ALTER TABLE for day_context evening reflection columns
            for col_def in [
                "went_well TEXT NOT NULL DEFAULT ''",
                "went_poorly TEXT NOT NULL DEFAULT ''",
                "lessons TEXT NOT NULL DEFAULT ''",
            ]:
                try:
                    conn.execute(f"ALTER TABLE day_context ADD COLUMN {col_def}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # ALTER TABLE for habit_definition agent management
            try:
                conn.execute("ALTER TABLE habit_definition ADD COLUMN user_managed INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Backfill created_at_utc from source turn
            conn.execute("""
                UPDATE open_loop SET created_at_utc = (
                    SELECT t.created_at_utc FROM turn t WHERE t.turn_id = open_loop.source_turn_id
                ) WHERE created_at_utc = '' AND source_turn_id != ''
            """)
            # Backfill from day context
            conn.execute("""
                UPDATE open_loop SET created_at_utc = (
                    SELECT dc.opened_at_utc FROM day_context dc WHERE dc.day_id = open_loop.day_id
                ) WHERE created_at_utc = '' AND day_id != ''
            """)
            # Remaining blanks: set to now
            conn.execute(
                "UPDATE open_loop SET created_at_utc = ? WHERE created_at_utc = ''",
                (_utc_now_iso(),),
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_open_loop_stale ON open_loop(chat_id, status, created_at_utc)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_open_loop_day_kind ON open_loop(day_id, kind, status)"
            )

            # Intervention table (Phase 5: Strategy evaluation)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intervention (
                    intervention_id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    strategy_text TEXT NOT NULL,
                    target_metric TEXT NOT NULL,
                    baseline_value REAL,
                    baseline_sample_size INTEGER NOT NULL DEFAULT 0,
                    start_date TEXT NOT NULL,
                    evaluation_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    outcome_text TEXT NOT NULL DEFAULT '',
                    outcome_delta REAL,
                    created_at_utc TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_intervention_eval ON intervention(chat_id, status, evaluation_date)"
            )

    @contextmanager
    def begin_write(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def mark_update_processed(self, chat_id: int, update_id: int) -> bool:
        if not update_id:
            return True
        try:
            with self.begin_write() as conn:
                conn.execute(
                    "INSERT INTO processed_update (telegram_update_id, chat_id, processed_at_utc) VALUES (?, ?, ?)",
                    (update_id, chat_id, _utc_now_iso()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user_profile(self, chat_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM user_profile WHERE chat_id = ?", (chat_id,)).fetchone()
        if row:
            return dict(row)
        return {
            "chat_id": chat_id,
            "home_timezone": DEFAULT_TIMEZONE,
            "current_timezone": DEFAULT_TIMEZONE,
            "timezone_source": "default",
            "location_label": "",
            "coach_style": "adaptive_firm",
            "quiet_hours_start_local": "22:30",
            "quiet_hours_end_local": "08:00",
        }

    def ensure_user_profile(self, chat_id: int) -> dict[str, Any]:
        profile = self.get_user_profile(chat_id)
        if profile.get("updated_at_utc"):
            return profile
        with self.begin_write() as conn:
            conn.execute(
                """
                INSERT INTO user_profile
                    (chat_id, home_timezone, current_timezone, timezone_source, location_label,
                     coach_style, quiet_hours_start_local, quiet_hours_end_local, updated_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    current_timezone = excluded.current_timezone,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    chat_id,
                    profile["home_timezone"],
                    profile["current_timezone"],
                    profile["timezone_source"],
                    profile["location_label"],
                    profile["coach_style"],
                    profile["quiet_hours_start_local"],
                    profile["quiet_hours_end_local"],
                    _utc_now_iso(),
                ),
            )
        return self.get_user_profile(chat_id)

    def resolve_timezone_name(self, chat_id: int) -> str:
        return self.ensure_user_profile(chat_id)["current_timezone"]

    def set_current_timezone(
        self,
        chat_id: int,
        timezone_name: str,
        source: str,
        location_label: str = "",
    ) -> dict[str, Any]:
        profile = self.ensure_user_profile(chat_id)
        with self.begin_write() as conn:
            conn.execute(
                """
                INSERT INTO user_profile
                    (chat_id, home_timezone, current_timezone, timezone_source, location_label,
                     coach_style, quiet_hours_start_local, quiet_hours_end_local, updated_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    current_timezone = excluded.current_timezone,
                    timezone_source = excluded.timezone_source,
                    location_label = excluded.location_label,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    chat_id,
                    profile["home_timezone"],
                    timezone_name,
                    source,
                    location_label or "",
                    profile["coach_style"],
                    profile["quiet_hours_start_local"],
                    profile["quiet_hours_end_local"],
                    _utc_now_iso(),
                ),
            )
            self._insert_audit_event(
                conn,
                chat_id,
                "timezone_change",
                f"Timezone set to {timezone_name}",
                {"timezone": timezone_name, "source": source, "location_label": location_label or ""},
            )
        return self.get_user_profile(chat_id)

    def _load_habits(self) -> list[dict[str, str]]:
        if not HABITS_PATH.exists():
            return []
        try:
            post = frontmatter.load(HABITS_PATH)
            habits = post.metadata.get("habits", [])
            loaded = []
            for habit in habits:
                habit_id = str(habit.get("id", "")).strip()
                name = str(habit.get("name", "")).strip()
                if habit_id and name:
                    loaded.append({"habit_id": habit_id, "name": name, "cadence": "daily"})
            return loaded
        except Exception:
            return []

    def ensure_habit_definitions(self, chat_id: int, conn: sqlite3.Connection | None = None) -> None:
        habits = self._load_habits()
        if not habits:
            return
        owns_conn = conn is None
        if conn is None:
            conn = self._connect()
        try:
            for habit in habits:
                conn.execute(
                    """
                    INSERT INTO habit_definition (habit_id, chat_id, name, cadence, active)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(habit_id) DO UPDATE SET
                        name = excluded.name,
                        cadence = excluded.cadence,
                        active = CASE WHEN habit_definition.user_managed = 1
                                      THEN habit_definition.active ELSE 1 END
                    """,
                    (habit["habit_id"], chat_id, habit["name"], habit["cadence"]),
                )
            if owns_conn:
                conn.commit()
        finally:
            if owns_conn:
                conn.close()

    def ensure_day_open(self, resolved_now: ResolvedNow) -> dict[str, Any]:
        with self.begin_write() as conn:
            row = conn.execute(
                "SELECT * FROM day_context WHERE chat_id = ? AND local_date = ?",
                (resolved_now.chat_id, resolved_now.local_date),
            ).fetchone()
            created = False
            if row:
                day_id = row["day_id"]
            else:
                created = True
                day_id = _new_id("day")
                conn.execute(
                    """
                    INSERT INTO day_context (day_id, chat_id, local_date, timezone, status, opened_at_utc)
                    VALUES (?, ?, ?, ?, 'open', ?)
                    """,
                    (day_id, resolved_now.chat_id, resolved_now.local_date, resolved_now.timezone_name, resolved_now.utc_now.isoformat()),
                )
                self._insert_audit_event(
                    conn,
                    resolved_now.chat_id,
                    "day_opened",
                    f"Opened day {resolved_now.local_date}",
                    {"day_id": day_id, "timezone": resolved_now.timezone_name},
                )

            self.ensure_habit_definitions(resolved_now.chat_id, conn=conn)
            habits = conn.execute(
                "SELECT habit_id FROM habit_definition WHERE chat_id = ? AND active = 1",
                (resolved_now.chat_id,),
            ).fetchall()
            for habit in habits:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO habit_instance (instance_id, habit_id, day_id, status, last_changed_at_utc)
                    VALUES (?, ?, ?, 'pending', ?)
                    """,
                    (_new_id("habitinst"), habit["habit_id"], day_id, resolved_now.utc_now.isoformat()),
                )

            day = conn.execute("SELECT * FROM day_context WHERE day_id = ?", (day_id,)).fetchone()
        result = dict(day)
        result["created"] = created
        return result

    def close_day(self, chat_id: int, local_date: str) -> bool:
        with self.begin_write() as conn:
            row = conn.execute(
                "SELECT day_id, status FROM day_context WHERE chat_id = ? AND local_date = ?",
                (chat_id, local_date),
            ).fetchone()
            if not row:
                return False
            if row["status"] != "closed":
                conn.execute(
                    "UPDATE day_context SET status = 'closed', closed_at_utc = ? WHERE day_id = ?",
                    (_utc_now_iso(), row["day_id"]),
                )
                self._insert_audit_event(
                    conn,
                    chat_id,
                    "day_closed",
                    f"Closed day {local_date}",
                    {"day_id": row["day_id"]},
                )
        return True

    def get_day_snapshot(self, chat_id: int, local_date: str | None = None) -> DaySnapshot | None:
        with self._connect() as conn:
            if local_date:
                row = conn.execute(
                    "SELECT * FROM day_context WHERE chat_id = ? AND local_date = ?",
                    (chat_id, local_date),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM day_context WHERE chat_id = ? ORDER BY local_date DESC LIMIT 1",
                    (chat_id,),
                ).fetchone()
            if not row:
                return None
            day_id = row["day_id"]
            metrics = {
                item["field"]: item["value"]
                for item in conn.execute("SELECT field, value FROM day_metric WHERE day_id = ?", (day_id,)).fetchall()
            }
            foods = [dict(item) for item in conn.execute(
                "SELECT description, logged_at_utc FROM food_entry WHERE day_id = ? ORDER BY logged_at_utc",
                (day_id,),
            ).fetchall()]
            habits = [dict(item) for item in conn.execute(
                """
                SELECT d.habit_id, d.name, i.status
                FROM habit_instance i
                JOIN habit_definition d ON d.habit_id = i.habit_id
                WHERE i.day_id = ?
                ORDER BY d.name
                """,
                (day_id,),
            ).fetchall()]
            loops = [dict(item) for item in conn.execute(
                """
                SELECT loop_id, kind, title, status, priority, due_at_utc
                FROM open_loop
                WHERE chat_id = ? AND (day_id = ? OR (day_id = '' AND status = 'open'))
                ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, title
                """,
                (chat_id, day_id),
            ).fetchall()]
            session = conn.execute(
                "SELECT summary_text FROM session WHERE chat_id = ? ORDER BY started_at_utc DESC LIMIT 1",
                (chat_id,),
            ).fetchone()
            todos = [dict(item) for item in conn.execute(
                """
                SELECT loop_id, title, status, category, source, is_top3, notes,
                       rollover_count, created_at_utc
                FROM open_loop
                WHERE day_id = ? AND kind = 'daily_todo'
                ORDER BY CASE category
                    WHEN 'must_win' THEN 0 WHEN 'can_do' THEN 1 WHEN 'not_today' THEN 2 ELSE 3
                END, created_at_utc
                """,
                (day_id,),
            ).fetchall()]

        reflections = {
            "went_well": row["went_well"] if "went_well" in row.keys() else "",
            "went_poorly": row["went_poorly"] if "went_poorly" in row.keys() else "",
            "lessons": row["lessons"] if "lessons" in row.keys() else "",
        }

        return DaySnapshot(
            day_id=day_id,
            chat_id=chat_id,
            local_date=row["local_date"],
            timezone=row["timezone"],
            status=row["status"],
            state_version=row["state_version"],
            metrics=metrics,
            foods=foods,
            habits=habits,
            open_loops=loops,
            todos=todos,
            reflections=reflections,
            summary=session["summary_text"] if session else "",
        )

    def get_or_create_session(self, chat_id: int, now_utc: datetime | None = None) -> dict[str, Any]:
        now_utc = now_utc or _utc_now()
        cutoff = (now_utc - timedelta(hours=6)).isoformat()
        with self.begin_write() as conn:
            row = conn.execute(
                """
                SELECT * FROM session
                WHERE chat_id = ?
                ORDER BY started_at_utc DESC
                LIMIT 1
                """,
                (chat_id,),
            ).fetchone()
            if row and (row["ended_at_utc"] == "" or row["ended_at_utc"] >= cutoff):
                conn.execute(
                    "UPDATE session SET ended_at_utc = ? WHERE session_id = ?",
                    (now_utc.isoformat(), row["session_id"]),
                )
                return dict(row)

            session_id = _new_id("sess")
            conn.execute(
                """
                INSERT INTO session (session_id, chat_id, started_at_utc, ended_at_utc)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, chat_id, now_utc.isoformat(), now_utc.isoformat()),
            )
            return {
                "session_id": session_id,
                "chat_id": chat_id,
                "started_at_utc": now_utc.isoformat(),
                "ended_at_utc": now_utc.isoformat(),
                "summary_text": "",
                "active_topics_json": "[]",
                "open_questions_json": "[]",
                "correction_count": 0,
            }

    def record_turn(
        self,
        chat_id: int,
        session_id: str,
        update_id: int,
        role: str,
        text: str,
    ) -> str:
        turn_id = _new_id("turn")
        with self.begin_write() as conn:
            conn.execute(
                """
                INSERT INTO turn (turn_id, session_id, telegram_update_id, role, text, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (turn_id, session_id, update_id or 0, role, text, _utc_now_iso()),
            )
            conn.execute(
                "UPDATE session SET ended_at_utc = ? WHERE session_id = ?",
                (_utc_now_iso(), session_id),
            )
        return turn_id

    def record_tool_event(
        self,
        turn_id: str,
        tool_name: str,
        validated_args: dict[str, Any],
        result_summary: str,
        status: str = "completed",
    ) -> str:
        tool_event_id = _new_id("tool")
        with self.begin_write() as conn:
            conn.execute(
                """
                INSERT INTO tool_event (tool_event_id, turn_id, tool_name, validated_args_json, result_summary, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (tool_event_id, turn_id, tool_name, _json_dumps(validated_args), result_summary[:500], status),
            )
        return tool_event_id

    def list_recent_messages(self, chat_id: int, max_pairs: int = 4) -> list[dict[str, str]]:
        limit = max_pairs * 2
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT t.role, t.text
                FROM turn t
                JOIN session s ON s.session_id = t.session_id
                WHERE s.chat_id = ?
                ORDER BY t.created_at_utc DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
        messages = [{"role": row["role"], "content": row["text"]} for row in reversed(rows)]
        return messages

    def refresh_session_summary(self, session_id: str) -> None:
        with self.begin_write() as conn:
            turns = conn.execute(
                "SELECT role, text FROM turn WHERE session_id = ? ORDER BY created_at_utc DESC LIMIT 6",
                (session_id,),
            ).fetchall()
            if not turns:
                return
            latest_user = next((row["text"] for row in turns if row["role"] == "user"), "")
            latest_assistant = next((row["text"] for row in turns if row["role"] == "assistant"), "")
            topics = self._infer_topics(latest_user, latest_assistant)
            questions = [line.strip() for line in latest_assistant.splitlines() if line.strip().endswith("?")][:2]
            corrections = 1 if re.search(r"\b(correct|apolog|mistake|contradict)\b", latest_assistant, re.I) else 0
            summary = f"Latest user topic: {latest_user[:140] or 'n/a'}. Latest assistant response: {latest_assistant[:160] or 'n/a'}."
            conn.execute(
                """
                UPDATE session
                SET summary_text = ?, active_topics_json = ?, open_questions_json = ?,
                    correction_count = correction_count + ?
                WHERE session_id = ?
                """,
                (summary, _json_dumps(topics), _json_dumps(questions), corrections, session_id),
            )

    def _infer_topics(self, *texts: str) -> list[str]:
        keywords = {
            "timezone": ("timezone", "utc", "travel"),
            "nutrition": ("calories", "protein", "food", "meal", "lunch", "dinner"),
            "training": ("run", "bike", "swim", "workout", "strength"),
            "habits": ("habit", "yoga", "meditation"),
            "followup": ("follow up", "follow-up", "remind", "deadline"),
        }
        haystack = " ".join(texts).lower()
        found = [topic for topic, needles in keywords.items() if any(needle in haystack for needle in needles)]
        return found[:4]

    def get_latest_session_summary(self, chat_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM session WHERE chat_id = ? ORDER BY started_at_utc DESC LIMIT 1",
                (chat_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_memory_candidates(
        self,
        chat_id: int,
        source_turn_id: str,
        candidates: list[dict[str, Any]],
    ) -> list[MemoryCandidateRecord]:
        created: list[MemoryCandidateRecord] = []
        if not candidates:
            return created
        with self.begin_write() as conn:
            for candidate in candidates:
                candidate_id = _new_id("cand")
                row = MemoryCandidateRecord(
                    candidate_id=candidate_id,
                    chat_id=chat_id,
                    kind=candidate["kind"],
                    payload=candidate["payload"],
                    confidence=float(candidate.get("confidence", 0.5)),
                    reason=str(candidate.get("reason", "")).strip()[:240],
                    status="pending",
                    created_at_utc=_utc_now_iso(),
                )
                conn.execute(
                    """
                    INSERT INTO memory_candidate
                        (candidate_id, chat_id, kind, payload_json, confidence, reason, status, source_turn_id, created_at_utc)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        row.candidate_id,
                        chat_id,
                        row.kind,
                        _json_dumps(row.payload),
                        row.confidence,
                        row.reason,
                        source_turn_id,
                        row.created_at_utc,
                    ),
                )
                created.append(row)
            self._insert_audit_event(
                conn,
                chat_id,
                "memory_candidates_created",
                f"Created {len(created)} pending memory candidates",
                {"source_turn_id": source_turn_id},
            )
        return created

    def list_pending_memory_candidates(self, chat_id: int, limit: int = 20) -> list[MemoryCandidateRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM memory_candidate
                WHERE chat_id = ? AND status = 'pending'
                ORDER BY created_at_utc DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
        return [
            MemoryCandidateRecord(
                candidate_id=row["candidate_id"],
                chat_id=row["chat_id"],
                kind=row["kind"],
                payload=_json_loads(row["payload_json"], {}),
                confidence=row["confidence"],
                reason=row["reason"],
                status=row["status"],
                created_at_utc=row["created_at_utc"],
            )
            for row in rows
        ]

    def review_memory_candidate(
        self,
        chat_id: int,
        candidate_id: str,
        action: str,
        edited_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        allowed = {"approve", "reject"}
        if action not in allowed:
            raise ValueError(f"Unsupported review action: {action}")
        with self.begin_write() as conn:
            row = conn.execute(
                "SELECT * FROM memory_candidate WHERE chat_id = ? AND candidate_id = ?",
                (chat_id, candidate_id),
            ).fetchone()
            if not row:
                return None
            if row["status"] != "pending":
                return {"status": row["status"], "candidate_id": candidate_id}

            payload = edited_payload or _json_loads(row["payload_json"], {})
            if action == "reject":
                conn.execute(
                    "UPDATE memory_candidate SET status = 'rejected' WHERE candidate_id = ?",
                    (candidate_id,),
                )
                self._insert_audit_event(
                    conn,
                    chat_id,
                    "memory_candidate_rejected",
                    f"Rejected memory candidate {candidate_id}",
                    {"candidate_id": candidate_id},
                )
                return {"status": "rejected", "candidate_id": candidate_id}

            subject_key = _normalize_subject_key(row["kind"], payload)
            existing = conn.execute(
                """
                SELECT MAX(version) AS latest_version
                FROM approved_memory
                WHERE chat_id = ? AND kind = ? AND subject_key = ?
                """,
                (chat_id, row["kind"], subject_key),
            ).fetchone()
            next_version = (existing["latest_version"] or 0) + 1
            conn.execute(
                """
                UPDATE approved_memory
                SET active = 0, valid_to_utc = ?
                WHERE chat_id = ? AND kind = ? AND subject_key = ? AND active = 1
                """,
                (_utc_now_iso(), chat_id, row["kind"], subject_key),
            )
            memory_id = _new_id("mem")
            conn.execute(
                """
                INSERT INTO approved_memory
                    (memory_id, chat_id, kind, subject_key, payload_json, version, active,
                     valid_from_utc, source_candidate_id)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    memory_id,
                    chat_id,
                    row["kind"],
                    subject_key,
                    _json_dumps(payload),
                    next_version,
                    _utc_now_iso(),
                    candidate_id,
                ),
            )
            conn.execute(
                "UPDATE memory_candidate SET status = 'approved' WHERE candidate_id = ?",
                (candidate_id,),
            )
            self._insert_audit_event(
                conn,
                chat_id,
                "memory_candidate_approved",
                f"Approved memory candidate {candidate_id}",
                {"candidate_id": candidate_id, "memory_id": memory_id},
            )
            return {"status": "approved", "candidate_id": candidate_id, "memory_id": memory_id}

    def get_approved_memories(self, chat_id: int, limit: int = 6) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT kind, subject_key, payload_json, version
                FROM approved_memory
                WHERE chat_id = ? AND active = 1
                ORDER BY version DESC, valid_from_utc DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
        return [
            {
                "kind": row["kind"],
                "subject_key": row["subject_key"],
                "payload": _json_loads(row["payload_json"], {}),
                "version": row["version"],
            }
            for row in rows
        ]

    def set_day_metric(self, chat_id: int, local_date: str, field: str, value: str) -> dict[str, Any]:
        if field not in DAY_METRIC_FIELDS:
            raise ValueError(f"Unsupported metric field: {field}")
        resolved = ResolvedNow(
            chat_id=chat_id,
            timezone_name=self.resolve_timezone_name(chat_id),
            timezone_label=self.resolve_timezone_name(chat_id),
            utc_now=_utc_now(),
            local_now=_utc_now(),
            local_date=local_date,
            day_key=local_date,
        )
        day = self.ensure_day_open(resolved)
        with self.begin_write() as conn:
            conn.execute(
                """
                INSERT INTO day_metric (day_id, field, value)
                VALUES (?, ?, ?)
                ON CONFLICT(day_id, field) DO UPDATE SET value = excluded.value
                """,
                (day["day_id"], field, str(value).strip()),
            )
        return {"day_id": day["day_id"], "field": field, "value": value}

    def append_food(
        self,
        chat_id: int,
        local_date: str,
        description: str,
        calories_est: int | None = None,
        protein_g_est: int | None = None,
        carbs_g_est: int | None = None,
        fat_g_est: int | None = None,
        fiber_g_est: int | None = None,
        meal_type: str = "",
    ) -> dict[str, Any]:
        resolved = ResolvedNow(
            chat_id=chat_id,
            timezone_name=self.resolve_timezone_name(chat_id),
            timezone_label=self.resolve_timezone_name(chat_id),
            utc_now=_utc_now(),
            local_now=_utc_now(),
            local_date=local_date,
            day_key=local_date,
        )
        day = self.ensure_day_open(resolved)
        food_id = _new_id("food")
        with self.begin_write() as conn:
            conn.execute(
                """
                INSERT INTO food_entry
                    (food_id, day_id, description, logged_at_utc,
                     calories_est, protein_g_est, carbs_g_est, fat_g_est, fiber_g_est, meal_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (food_id, day["day_id"], description.strip(), _utc_now_iso(),
                 calories_est, protein_g_est, carbs_g_est, fat_g_est, fiber_g_est, meal_type),
            )
        return {"food_id": food_id, "day_id": day["day_id"], "description": description.strip()}

    def record_workout(
        self,
        chat_id: int,
        local_date: str,
        workout_type: str,
        exercises: list[dict[str, Any]] | None = None,
        cardio: list[dict[str, Any]] | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        """Record a workout session with exercises and/or cardio activities."""
        resolved = ResolvedNow(
            chat_id=chat_id,
            timezone_name=self.resolve_timezone_name(chat_id),
            timezone_label=self.resolve_timezone_name(chat_id),
            utc_now=_utc_now(),
            local_now=_utc_now(),
            local_date=local_date,
            day_key=local_date,
        )
        day = self.ensure_day_open(resolved)
        ws_id = _new_id("ws")
        with self.begin_write() as conn:
            conn.execute(
                "INSERT INTO workout_session (session_id, day_id, workout_type, notes) VALUES (?, ?, ?, ?)",
                (ws_id, day["day_id"], workout_type, notes),
            )
            ex_count = 0
            for ex in (exercises or []):
                ex_id = _new_id("ex")
                conn.execute(
                    """
                    INSERT INTO exercise_log (exercise_id, session_id, exercise_name, sets, reps, weight_lbs, duration_seconds)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (ex_id, ws_id, ex.get("name", ""), ex.get("sets"), ex.get("reps"),
                     ex.get("weight_lbs"), ex.get("duration_seconds")),
                )
                ex_count += 1
            cardio_count = 0
            for act in (cardio or []):
                act_id = _new_id("cardio")
                conn.execute(
                    """
                    INSERT INTO cardio_activity
                        (activity_id, session_id, activity_type, distance, distance_unit, duration_minutes, avg_hr)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (act_id, ws_id, act.get("type", ""), act.get("distance"),
                     act.get("distance_unit", "mi"), act.get("duration_minutes"), act.get("avg_hr")),
                )
                cardio_count += 1
        return {
            "session_id": ws_id,
            "workout_type": workout_type,
            "exercises": ex_count,
            "cardio_activities": cardio_count,
        }

    def mark_habit(self, chat_id: int, local_date: str, habit_id: str, status: str) -> dict[str, Any]:
        if status not in {"pending", "done", "skipped", "snoozed"}:
            raise ValueError(f"Unsupported habit status: {status}")
        resolved = ResolvedNow(
            chat_id=chat_id,
            timezone_name=self.resolve_timezone_name(chat_id),
            timezone_label=self.resolve_timezone_name(chat_id),
            utc_now=_utc_now(),
            local_now=_utc_now(),
            local_date=local_date,
            day_key=local_date,
        )
        day = self.ensure_day_open(resolved)
        with self.begin_write() as conn:
            row = conn.execute(
                "SELECT habit_id FROM habit_definition WHERE chat_id = ? AND (habit_id = ? OR LOWER(name) = LOWER(?)) LIMIT 1",
                (chat_id, habit_id, habit_id),
            ).fetchone()
            if not row:
                raise ValueError(f"Habit not found: {habit_id}")
            conn.execute(
                """
                UPDATE habit_instance
                SET status = ?, last_changed_at_utc = ?
                WHERE habit_id = ? AND day_id = ?
                """,
                (status, _utc_now_iso(), row["habit_id"], day["day_id"]),
            )
        return {"day_id": day["day_id"], "habit_id": row["habit_id"], "status": status}

    def create_open_loop(
        self,
        chat_id: int,
        title: str,
        kind: str,
        priority: str = "normal",
        due_at_utc: str = "",
        day_id: str = "",
        source_turn_id: str = "",
    ) -> dict[str, Any]:
        loop_id = _new_id("loop")
        created = _utc_now_iso()
        with self.begin_write() as conn:
            conn.execute(
                """
                INSERT INTO open_loop
                    (loop_id, chat_id, kind, title, status, priority, due_at_utc, day_id, source_turn_id, created_at_utc)
                VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
                """,
                (loop_id, chat_id, kind, title.strip(), priority, due_at_utc, day_id, source_turn_id, created),
            )
        return {"loop_id": loop_id, "title": title.strip(), "kind": kind, "priority": priority, "due_at_utc": due_at_utc}

    def complete_open_loop(self, chat_id: int, loop_id_or_title: str) -> dict[str, Any] | None:
        with self.begin_write() as conn:
            row = conn.execute(
                """
                SELECT loop_id, title, status
                FROM open_loop
                WHERE chat_id = ? AND (loop_id = ? OR LOWER(title) = LOWER(?))
                ORDER BY due_at_utc DESC
                LIMIT 1
                """,
                (chat_id, loop_id_or_title, loop_id_or_title),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE open_loop SET status = 'completed', snoozed_until_utc = '' WHERE loop_id = ?",
                (row["loop_id"],),
            )
        return {"loop_id": row["loop_id"], "title": row["title"], "status": "completed"}

    def snooze_open_loop(self, chat_id: int, loop_id_or_title: str, minutes: int) -> dict[str, Any] | None:
        with self.begin_write() as conn:
            row = conn.execute(
                """
                SELECT loop_id, title
                FROM open_loop
                WHERE chat_id = ? AND status = 'open' AND (loop_id = ? OR LOWER(title) = LOWER(?))
                ORDER BY due_at_utc DESC
                LIMIT 1
                """,
                (chat_id, loop_id_or_title, loop_id_or_title),
            ).fetchone()
            if not row:
                return None
            snoozed_until = (_utc_now() + timedelta(minutes=max(1, minutes))).isoformat()
            conn.execute(
                "UPDATE open_loop SET snoozed_until_utc = ? WHERE loop_id = ?",
                (snoozed_until, row["loop_id"]),
            )
        return {"loop_id": row["loop_id"], "title": row["title"], "snoozed_until_utc": snoozed_until}

    def list_due_followups(self, chat_id: int, now_utc: datetime | None = None, limit: int = 10) -> list[dict[str, Any]]:
        now_utc = now_utc or _utc_now()
        now_iso = now_utc.isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT loop_id, kind, title, priority, due_at_utc
                FROM open_loop
                WHERE chat_id = ? AND status = 'open'
                  AND (due_at_utc = '' OR due_at_utc <= ?)
                  AND (snoozed_until_utc = '' OR snoozed_until_utc <= ?)
                ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
                         CASE WHEN due_at_utc = '' THEN '9999-12-31T23:59:59+00:00' ELSE due_at_utc END
                LIMIT ?
                """,
                (chat_id, now_iso, now_iso, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_imminent_loops(
        self,
        chat_id: int,
        now_utc: datetime | None = None,
        lookahead_min: int = 5,
        lookback_min: int = 15,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return open loops with due_at_utc within [now-lookback, now+lookahead]."""
        now_utc = now_utc or _utc_now()
        window_start = (now_utc - timedelta(minutes=lookback_min)).isoformat()
        window_end = (now_utc + timedelta(minutes=lookahead_min)).isoformat()
        now_iso = now_utc.isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT loop_id, kind, title, priority, due_at_utc
                FROM open_loop
                WHERE chat_id = ? AND status = 'open'
                  AND due_at_utc != '' AND due_at_utc >= ? AND due_at_utc <= ?
                  AND (snoozed_until_utc = '' OR snoozed_until_utc <= ?)
                ORDER BY due_at_utc ASC
                LIMIT ?
                """,
                (chat_id, window_start, window_end, now_iso, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_stale_loops(
        self, chat_id: int, age_days: int = 3, limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return open loops older than age_days."""
        cutoff = (_utc_now() - timedelta(days=age_days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT loop_id, kind, title, priority, due_at_utc, created_at_utc, rollover_count,
                       CAST(julianday('now') - julianday(created_at_utc) AS INTEGER) AS age_days
                FROM open_loop
                WHERE chat_id = ? AND status = 'open'
                  AND created_at_utc != '' AND created_at_utc <= ?
                ORDER BY created_at_utc ASC
                LIMIT ?
                """,
                (chat_id, cutoff, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def increment_rollover(self, chat_id: int, loop_id: str) -> dict[str, Any] | None:
        """Increment rollover count for an open loop."""
        with self.begin_write() as conn:
            conn.execute(
                "UPDATE open_loop SET rollover_count = rollover_count + 1 WHERE loop_id = ? AND chat_id = ?",
                (loop_id, chat_id),
            )
            row = conn.execute(
                "SELECT loop_id, title, rollover_count FROM open_loop WHERE loop_id = ?",
                (loop_id,),
            ).fetchone()
        return dict(row) if row else None

    # --- Daily Todo Methods (extend open_loop with kind='daily_todo') ---

    def create_daily_todo(
        self,
        chat_id: int,
        local_date: str,
        title: str,
        category: str = "",
        source: str = "manual",
        is_top3: bool = False,
        notes: str = "",
    ) -> dict[str, Any]:
        loop_id = _new_id("loop")
        created = _utc_now_iso()
        # Resolve day_id from local_date
        with self.begin_write() as conn:
            day_row = conn.execute(
                "SELECT day_id FROM day_context WHERE chat_id = ? AND local_date = ?",
                (chat_id, local_date),
            ).fetchone()
            day_id = day_row["day_id"] if day_row else ""
            conn.execute(
                """
                INSERT INTO open_loop
                    (loop_id, chat_id, kind, title, status, priority, day_id,
                     created_at_utc, category, source, is_top3, notes)
                VALUES (?, ?, 'daily_todo', ?, 'open', 'normal', ?,
                        ?, ?, ?, ?, ?)
                """,
                (loop_id, chat_id, title.strip(), day_id,
                 created, category, source, 1 if is_top3 else 0, notes),
            )
        return {
            "loop_id": loop_id, "title": title.strip(), "kind": "daily_todo",
            "category": category, "source": source, "is_top3": is_top3,
            "day_id": day_id, "local_date": local_date,
        }

    def list_daily_todos(
        self, chat_id: int, local_date: str, status: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            day_row = conn.execute(
                "SELECT day_id FROM day_context WHERE chat_id = ? AND local_date = ?",
                (chat_id, local_date),
            ).fetchone()
            if not day_row:
                return []
            day_id = day_row["day_id"]
            if status:
                rows = conn.execute(
                    """
                    SELECT loop_id, title, status, priority, category, source, is_top3, notes,
                           rollover_count, created_at_utc
                    FROM open_loop
                    WHERE day_id = ? AND kind = 'daily_todo' AND status = ?
                    ORDER BY CASE category
                        WHEN 'must_win' THEN 0 WHEN 'can_do' THEN 1 WHEN 'not_today' THEN 2 ELSE 3
                    END, created_at_utc
                    """,
                    (day_id, status),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT loop_id, title, status, priority, category, source, is_top3, notes,
                           rollover_count, created_at_utc
                    FROM open_loop
                    WHERE day_id = ? AND kind = 'daily_todo'
                    ORDER BY CASE category
                        WHEN 'must_win' THEN 0 WHEN 'can_do' THEN 1 WHEN 'not_today' THEN 2 ELSE 3
                    END, created_at_utc
                    """,
                    (day_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def rollover_daily_todos(self, chat_id: int, from_day_id: str, to_day_id: str) -> int:
        """Atomically roll open daily_todos from one day to another."""
        with self.begin_write() as conn:
            open_todos = conn.execute(
                """
                SELECT loop_id, title, priority, category, notes
                FROM open_loop
                WHERE day_id = ? AND kind = 'daily_todo' AND status = 'open' AND chat_id = ?
                """,
                (from_day_id, chat_id),
            ).fetchall()
            count = 0
            for todo in open_todos:
                new_id = _new_id("loop")
                conn.execute(
                    """
                    INSERT INTO open_loop
                        (loop_id, chat_id, kind, title, status, priority, day_id,
                         created_at_utc, category, source, rollover_count)
                    VALUES (?, ?, 'daily_todo', ?, 'open', ?, ?,
                            ?, ?, 'rollover',
                            (SELECT rollover_count + 1 FROM open_loop WHERE loop_id = ?))
                    """,
                    (new_id, chat_id, todo["title"], todo["priority"], to_day_id,
                     _utc_now_iso(), todo["category"], todo["loop_id"]),
                )
                conn.execute(
                    "UPDATE open_loop SET status = 'rolled' WHERE loop_id = ?",
                    (todo["loop_id"],),
                )
                count += 1
        return count

    # --- Habit Definition CRUD ---

    def create_habit_definition(
        self, chat_id: int, name: str, cadence: str = "daily",
    ) -> dict[str, Any]:
        habit_id = name.lower().replace(" ", "_")
        with self.begin_write() as conn:
            conn.execute(
                """
                INSERT INTO habit_definition (habit_id, chat_id, name, cadence, active, user_managed)
                VALUES (?, ?, ?, ?, 1, 1)
                ON CONFLICT(habit_id) DO UPDATE SET name = excluded.name, cadence = excluded.cadence,
                    active = 1, user_managed = 1
                """,
                (habit_id, chat_id, name, cadence),
            )
        return {"habit_id": habit_id, "name": name, "cadence": cadence, "active": 1, "user_managed": 1}

    def update_habit_definition(
        self, chat_id: int, habit_id_or_name: str,
        active: bool | None = None, name: str | None = None,
    ) -> dict[str, Any] | None:
        with self.begin_write() as conn:
            row = conn.execute(
                """
                SELECT habit_id, name, cadence, active, user_managed
                FROM habit_definition
                WHERE chat_id = ? AND (habit_id = ? OR LOWER(name) = LOWER(?))
                """,
                (chat_id, habit_id_or_name, habit_id_or_name),
            ).fetchone()
            if not row:
                return None
            hid = row["habit_id"]
            updates = []
            params: list[Any] = []
            if active is not None:
                updates.append("active = ?")
                params.append(1 if active else 0)
                updates.append("user_managed = 1")
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if not updates:
                return dict(row)
            params.append(hid)
            conn.execute(f"UPDATE habit_definition SET {', '.join(updates)} WHERE habit_id = ?", params)
            updated = conn.execute("SELECT * FROM habit_definition WHERE habit_id = ?", (hid,)).fetchone()
        return dict(updated) if updated else None

    # --- Reflection Methods ---

    def save_reflection(
        self, chat_id: int, local_date: str,
        went_well: str = "", went_poorly: str = "", lessons: str = "",
    ) -> dict[str, Any] | None:
        with self.begin_write() as conn:
            row = conn.execute(
                "SELECT day_id FROM day_context WHERE chat_id = ? AND local_date = ?",
                (chat_id, local_date),
            ).fetchone()
            if not row:
                return None
            day_id = row["day_id"]
            updates = []
            params: list[Any] = []
            if went_well:
                updates.append("went_well = ?")
                params.append(went_well)
            if went_poorly:
                updates.append("went_poorly = ?")
                params.append(went_poorly)
            if lessons:
                updates.append("lessons = ?")
                params.append(lessons)
            if not updates:
                return None
            params.append(day_id)
            conn.execute(f"UPDATE day_context SET {', '.join(updates)} WHERE day_id = ?", params)
            updated = conn.execute("SELECT * FROM day_context WHERE day_id = ?", (day_id,)).fetchone()
        return dict(updated) if updated else None

    def get_reflection(self, chat_id: int, local_date: str) -> dict[str, str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT went_well, went_poorly, lessons FROM day_context WHERE chat_id = ? AND local_date = ?",
                (chat_id, local_date),
            ).fetchone()
        if not row:
            return {"went_well": "", "went_poorly": "", "lessons": ""}
        return {"went_well": row["went_well"], "went_poorly": row["went_poorly"], "lessons": row["lessons"]}

    # --- Intervention (Strategy Evaluation) Methods ---

    def create_intervention(
        self,
        chat_id: int,
        strategy_text: str,
        target_metric: str,
        duration_days: int = 7,
        baseline_value: float | None = None,
        baseline_sample_size: int = 0,
    ) -> dict[str, Any]:
        """Create a behavioral intervention with baseline capture."""
        if target_metric not in DAY_METRIC_FIELDS:
            raise ValueError(f"Unsupported metric: {target_metric}")

        intervention_id = _new_id("intv")
        today = datetime.now(timezone.utc).date().isoformat()
        eval_date = (datetime.now(timezone.utc).date() + timedelta(days=duration_days)).isoformat()

        with self.begin_write() as conn:
            conn.execute(
                """
                INSERT INTO intervention
                    (intervention_id, chat_id, strategy_text, target_metric,
                     baseline_value, baseline_sample_size,
                     start_date, evaluation_date, status, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
                """,
                (intervention_id, chat_id, strategy_text.strip(), target_metric,
                 baseline_value, baseline_sample_size,
                 today, eval_date, _utc_now_iso()),
            )
        return {
            "intervention_id": intervention_id,
            "strategy_text": strategy_text.strip(),
            "target_metric": target_metric,
            "baseline_value": baseline_value,
            "start_date": today,
            "evaluation_date": eval_date,
            "status": "active",
        }

    def evaluate_intervention(
        self, chat_id: int, intervention_id: str, current_value: float | None = None,
    ) -> dict[str, Any] | None:
        """Evaluate an active intervention by comparing current to baseline."""
        with self.begin_write() as conn:
            row = conn.execute(
                "SELECT * FROM intervention WHERE intervention_id = ? AND chat_id = ?",
                (intervention_id, chat_id),
            ).fetchone()
            if not row or row["status"] != "active":
                return dict(row) if row else None

            baseline = row["baseline_value"]
            delta = (current_value - baseline) if (current_value is not None and baseline is not None) else None

            if delta is not None:
                direction = "improved" if delta > 0 else ("declined" if delta < 0 else "unchanged")
                outcome = (
                    f"{row['target_metric']}: {baseline:.1f} -> {current_value:.1f} "
                    f"({'+' if delta >= 0 else ''}{delta:.1f}, {direction})"
                )
            else:
                outcome = "Insufficient data to evaluate"

            conn.execute(
                """
                UPDATE intervention
                SET status = 'evaluated', outcome_text = ?, outcome_delta = ?
                WHERE intervention_id = ?
                """,
                (outcome, delta, intervention_id),
            )
        return {
            "intervention_id": intervention_id,
            "strategy_text": row["strategy_text"],
            "target_metric": row["target_metric"],
            "baseline_value": baseline,
            "current_value": current_value,
            "outcome_delta": delta,
            "outcome_text": outcome,
            "status": "evaluated",
        }

    def list_due_evaluations(
        self, chat_id: int, as_of_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return active interventions whose evaluation date has passed."""
        if not as_of_date:
            as_of_date = datetime.now(timezone.utc).date().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM intervention
                WHERE chat_id = ? AND status = 'active' AND evaluation_date <= ?
                ORDER BY evaluation_date ASC
                """,
                (chat_id, as_of_date),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_interventions(
        self, chat_id: int, status: str | None = None, limit: int = 10,
    ) -> list[dict[str, Any]]:
        """List interventions, optionally filtered by status."""
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM intervention WHERE chat_id = ? AND status = ? ORDER BY created_at_utc DESC LIMIT ?",
                    (chat_id, status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM intervention WHERE chat_id = ? ORDER BY created_at_utc DESC LIMIT ?",
                    (chat_id, limit),
                ).fetchall()
        return [dict(row) for row in rows]

    def drop_intervention(
        self, chat_id: int, intervention_id: str, reason: str = "",
    ) -> dict[str, Any] | None:
        """Drop an active intervention."""
        with self.begin_write() as conn:
            row = conn.execute(
                "SELECT * FROM intervention WHERE intervention_id = ? AND chat_id = ?",
                (intervention_id, chat_id),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE intervention SET status = 'dropped', outcome_text = ? WHERE intervention_id = ?",
                (reason or "Dropped by user", intervention_id),
            )
        return {"intervention_id": intervention_id, "status": "dropped", "outcome_text": reason or "Dropped by user"}

    def extend_intervention(
        self, chat_id: int, intervention_id: str, extra_days: int = 7,
    ) -> dict[str, Any] | None:
        """Extend an active intervention's evaluation date."""
        with self.begin_write() as conn:
            row = conn.execute(
                "SELECT * FROM intervention WHERE intervention_id = ? AND chat_id = ?",
                (intervention_id, chat_id),
            ).fetchone()
            if not row:
                return None
            from datetime import date as dt_date
            current_eval = dt_date.fromisoformat(row["evaluation_date"])
            new_eval = (current_eval + timedelta(days=extra_days)).isoformat()
            conn.execute(
                "UPDATE intervention SET evaluation_date = ? WHERE intervention_id = ?",
                (new_eval, intervention_id),
            )
        return {"intervention_id": intervention_id, "evaluation_date": new_eval}

    def list_recent_corrections(self, chat_id: int, limit: int = 2) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_type, summary, created_at_utc
                FROM audit_event
                WHERE chat_id = ? AND event_type IN ('timezone_change', 'day_correction', 'memory_candidate_approved')
                ORDER BY created_at_utc DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def _insert_audit_event(
        self,
        conn: sqlite3.Connection,
        chat_id: int,
        event_type: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO audit_event (event_id, chat_id, event_type, summary, metadata_json, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_new_id("evt"), chat_id, event_type, summary[:300], _json_dumps(metadata or {}), _utc_now_iso()),
        )

    def record_day_correction(self, chat_id: int, local_date: str, summary: str) -> None:
        with self.begin_write() as conn:
            row = conn.execute(
                "SELECT day_id, state_version FROM day_context WHERE chat_id = ? AND local_date = ?",
                (chat_id, local_date),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE day_context SET state_version = state_version + 1 WHERE day_id = ?",
                    (row["day_id"],),
                )
                self._insert_audit_event(
                    conn,
                    chat_id,
                    "day_correction",
                    summary,
                    {"day_id": row["day_id"], "local_date": local_date},
                )

    def record_reminder_send(
        self,
        chat_id: int,
        reminder_kind: str,
        target_id: str,
        scheduled_slot_local: str,
        outcome: str,
    ) -> bool:
        try:
            with self.begin_write() as conn:
                conn.execute(
                    """
                    INSERT INTO reminder_send
                        (send_id, chat_id, reminder_kind, target_id, scheduled_slot_local, sent_at_utc, outcome)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (_new_id("send"), chat_id, reminder_kind, target_id, scheduled_slot_local, _utc_now_iso(), outcome),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def render_private_day_log_data(self, day_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM day_context WHERE day_id = ?", (day_id,)).fetchone()
            if not row:
                return None
        snapshot = self.get_day_snapshot(row["chat_id"], row["local_date"])
        return asdict(snapshot) if snapshot else None

    def export_private_metrics(self, chat_id: int) -> Path:
        metrics_path = PRIVATE_DIR / "daily_metrics.private.json"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT d.local_date, d.timezone, d.status, m.field, m.value
                FROM day_context d
                LEFT JOIN day_metric m ON m.day_id = d.day_id
                WHERE d.chat_id = ?
                ORDER BY d.local_date DESC, m.field
                """,
                (chat_id,),
            ).fetchall()
        aggregated: dict[str, dict[str, Any]] = {}
        for row in rows:
            entry = aggregated.setdefault(
                row["local_date"],
                {"timezone": row["timezone"], "status": row["status"], "metrics": {}},
            )
            if row["field"]:
                entry["metrics"][row["field"]] = row["value"]
        metrics_path.write_text(json.dumps({"chat_id": chat_id, "days": aggregated}, indent=2))
        return metrics_path

    def get_all_metrics_entries(self, chat_id: int) -> list[dict[str, Any]]:
        """Return all days as metrics entries matching the daily_metrics.json schema."""
        with self._connect() as conn:
            days = conn.execute(
                "SELECT day_id, local_date FROM day_context WHERE chat_id = ? ORDER BY local_date",
                (chat_id,),
            ).fetchall()

            entries = []
            for day in days:
                day_id = day["day_id"]
                local_date = day["local_date"]

                metrics = {
                    row["field"]: row["value"]
                    for row in conn.execute(
                        "SELECT field, value FROM day_metric WHERE day_id = ?", (day_id,)
                    ).fetchall()
                }

                habits_rows = conn.execute(
                    """
                    SELECT hd.name, hi.status
                    FROM habit_instance hi
                    JOIN habit_definition hd ON hd.habit_id = hi.habit_id
                    WHERE hi.day_id = ?
                    """,
                    (day_id,),
                ).fetchall()
                completed = [r["name"] for r in habits_rows if r["status"] == "done"]
                missed = [r["name"] for r in habits_rows if r["status"] != "done"]
                total = len(habits_rows)

                # Training data from workout tables
                ws_row = conn.execute(
                    "SELECT session_id, workout_type FROM workout_session WHERE day_id = ? LIMIT 1",
                    (day_id,),
                ).fetchone()
                training = {"workout_type": "", "activities": [], "strength_exercises": []}
                if ws_row:
                    training["workout_type"] = ws_row["workout_type"]
                    for ex in conn.execute(
                        "SELECT exercise_name, sets, reps, weight_lbs FROM exercise_log WHERE session_id = ?",
                        (ws_row["session_id"],),
                    ).fetchall():
                        training["strength_exercises"].append({
                            "exercise": ex["exercise_name"],
                            "sets": ex["sets"],
                            "reps": ex["reps"],
                            "weight_lbs": ex["weight_lbs"],
                        })
                    for act in conn.execute(
                        "SELECT activity_type, distance, distance_unit, duration_minutes, avg_hr FROM cardio_activity WHERE session_id = ?",
                        (ws_row["session_id"],),
                    ).fetchall():
                        training["activities"].append({
                            "type": act["activity_type"],
                            "distance": act["distance"],
                            "distance_unit": act["distance_unit"],
                            "duration_minutes": act["duration_minutes"],
                            "avg_hr": act["avg_hr"],
                        })

                # Nutrition totals from food_entry macro columns
                nutr_row = conn.execute(
                    """
                    SELECT COALESCE(SUM(calories_est), 0) AS cal,
                           COALESCE(SUM(protein_g_est), 0) AS prot
                    FROM food_entry WHERE day_id = ? AND calories_est IS NOT NULL
                    """,
                    (day_id,),
                ).fetchone()
                nutrition_cal = nutr_row["cal"] if nutr_row and nutr_row["cal"] else None
                nutrition_prot = nutr_row["prot"] if nutr_row and nutr_row["prot"] else None

                # Todo stats from open_loop daily_todo entries
                todo_rows = conn.execute(
                    "SELECT status FROM open_loop WHERE day_id = ? AND kind = 'daily_todo'",
                    (day_id,),
                ).fetchall()
                todo_total = len(todo_rows)
                todo_completed = sum(1 for r in todo_rows if r["status"] == "completed")

                entries.append({
                    "date": local_date,
                    "sleep": {
                        "hours": _safe_float(metrics.get("Sleep")),
                        "quality": _safe_float(metrics.get("Sleep_Quality")),
                    },
                    "weight_lbs": _safe_float(metrics.get("Weight")),
                    "mood": {
                        "morning": _safe_float(metrics.get("Mood_AM")),
                        "bedtime": _safe_float(metrics.get("Mood_PM")),
                    },
                    "energy": _safe_float(metrics.get("Energy")),
                    "focus": _safe_float(metrics.get("Focus")),
                    "training": training,
                    "todos": {
                        "total": todo_total,
                        "completed": todo_completed,
                        "completion_rate": round(todo_completed / todo_total, 2) if todo_total else 0,
                    },
                    "habits": {
                        "completed": completed,
                        "missed": missed,
                        "completion_rate": round(len(completed) / total, 2) if total else 0,
                    },
                    "nutrition": {"calories": nutrition_cal, "protein_g": nutrition_prot},
                    "extraction_notes": [],
                })
        return entries


    def search_turns(
        self,
        chat_id: int,
        query: str,
        limit: int = 20,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Search turn text for keyword matches within a date window."""
        cutoff = (_utc_now() - timedelta(days=days)).isoformat(timespec="seconds")
        query_lower = f"%{query.lower()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT t.role, t.text, t.created_at_utc, s.session_id
                FROM turn t
                JOIN session s ON s.session_id = t.session_id
                WHERE s.chat_id = ?
                  AND t.created_at_utc >= ?
                  AND LOWER(t.text) LIKE ?
                ORDER BY t.created_at_utc DESC
                LIMIT ?
                """,
                (chat_id, cutoff, query_lower, limit),
            ).fetchall()
        return [dict(row) for row in rows]


def _safe_float(value: str | None) -> float | None:
    """Convert a string metric value to float, handling time formats like '6:20'."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if ":" in text:
        try:
            h, m = text.split(":", 1)
            return round(int(h) + int(m) / 60, 2)
        except (ValueError, TypeError):
            pass
    try:
        return float(re.sub(r'[^\d.\-]', '', text))
    except (ValueError, TypeError):
        return None
