"""
Tests for daily todo system built on open_loop with kind='daily_todo'.
Covers: create, list, complete, rollover, habit CRUD, reflections.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from v2.app.projection import PrivateProjectionService
from v2.app import projection as projection_module
from v2.app.timezone_resolver import DefaultTimezoneResolver
from v2.infra import sqlite_state_store as store_module
from v2.infra.sqlite_state_store import SQLiteStateStore


class FixedClock:
    def __init__(self, dt: datetime):
        self._dt = dt

    def now_utc(self) -> datetime:
        return self._dt


@pytest.fixture
def store(tmp_path, monkeypatch):
    tmp_project_dir = tmp_path / "project"
    tmp_private_dir = tmp_path / ".bestupid-private"
    tmp_project_dir.mkdir(parents=True, exist_ok=True)
    tmp_private_dir.mkdir(parents=True, exist_ok=True)

    habits_path = tmp_project_dir / "content" / "config" / "habits.md"
    habits_path.parent.mkdir(parents=True, exist_ok=True)
    habits_path.write_text(
        "---\nhabits:\n  - id: yoga\n    name: 10 min yoga\n---\n"
    )
    private_day_logs = tmp_private_dir / "day_logs"
    monkeypatch.setattr(store_module, "PRIVATE_DIR", tmp_private_dir)
    monkeypatch.setattr(store_module, "PRIVATE_DAY_LOG_DIR", private_day_logs)
    monkeypatch.setattr(store_module, "HABITS_PATH", habits_path)
    monkeypatch.setattr(store_module, "PROJECT_ROOT", tmp_project_dir)
    monkeypatch.setattr(projection_module, "PRIVATE_DIR", tmp_private_dir)
    monkeypatch.setattr(projection_module, "PRIVATE_DAY_LOG_DIR", private_day_logs)
    db_path = tmp_private_dir / "assistant_state.db"
    s = SQLiteStateStore(db_path=db_path)
    s.init_schema()

    clock = FixedClock(datetime(2026, 3, 25, 14, 0, tzinfo=timezone.utc))
    resolver = DefaultTimezoneResolver(s, clock=clock)
    resolved = resolver.resolve_now(12345)
    s.ensure_day_open(resolved)
    return s


CHAT_ID = 12345
TODAY = "2026-03-25"


# --- create_daily_todo ---

class TestCreateDailyTodo:
    def test_creates_todo_with_defaults(self, store):
        result = store.create_daily_todo(CHAT_ID, TODAY, "Write tests")
        assert result["title"] == "Write tests"
        assert result["kind"] == "daily_todo"
        assert result["category"] == ""
        assert result["source"] == "manual"
        assert result["is_top3"] is False

    def test_creates_todo_with_category_and_top3(self, store):
        result = store.create_daily_todo(CHAT_ID, TODAY, "Ship feature", category="must_win", is_top3=True)
        assert result["category"] == "must_win"
        assert result["is_top3"] is True

    def test_creates_todo_with_notes(self, store):
        result = store.create_daily_todo(CHAT_ID, TODAY, "Review PR", notes="deferred from yesterday")
        assert result["loop_id"].startswith("loop_")


# --- list_daily_todos ---

class TestListDailyTodos:
    def test_empty_list(self, store):
        todos = store.list_daily_todos(CHAT_ID, TODAY)
        assert todos == []

    def test_lists_created_todos(self, store):
        store.create_daily_todo(CHAT_ID, TODAY, "Task A", category="must_win")
        store.create_daily_todo(CHAT_ID, TODAY, "Task B", category="can_do")
        todos = store.list_daily_todos(CHAT_ID, TODAY)
        assert len(todos) == 2
        # must_win sorts before can_do
        assert todos[0]["title"] == "Task A"
        assert todos[1]["title"] == "Task B"

    def test_filters_by_status(self, store):
        store.create_daily_todo(CHAT_ID, TODAY, "Open task")
        result = store.create_daily_todo(CHAT_ID, TODAY, "Done task")
        store.complete_open_loop(CHAT_ID, result["loop_id"])
        open_todos = store.list_daily_todos(CHAT_ID, TODAY, status="open")
        assert len(open_todos) == 1
        assert open_todos[0]["title"] == "Open task"

    def test_returns_empty_for_unknown_date(self, store):
        todos = store.list_daily_todos(CHAT_ID, "2099-01-01")
        assert todos == []


# --- complete todo via complete_open_loop ---

class TestCompleteTodo:
    def test_complete_by_id(self, store):
        result = store.create_daily_todo(CHAT_ID, TODAY, "Finish report")
        completed = store.complete_open_loop(CHAT_ID, result["loop_id"])
        assert completed is not None
        assert completed["status"] == "completed"

    def test_complete_by_title(self, store):
        store.create_daily_todo(CHAT_ID, TODAY, "Call dentist")
        completed = store.complete_open_loop(CHAT_ID, "Call dentist")
        assert completed is not None
        assert completed["title"] == "Call dentist"


# --- rollover_daily_todos ---

class TestRolloverDailyTodos:
    def test_rollover_moves_open_todos(self, store):
        store.create_daily_todo(CHAT_ID, TODAY, "Unfinished task")
        done = store.create_daily_todo(CHAT_ID, TODAY, "Completed task")
        store.complete_open_loop(CHAT_ID, done["loop_id"])

        # Create tomorrow's day
        clock2 = FixedClock(datetime(2026, 3, 26, 14, 0, tzinfo=timezone.utc))
        resolver2 = DefaultTimezoneResolver(store, clock=clock2)
        resolved2 = resolver2.resolve_now(CHAT_ID)
        store.ensure_day_open(resolved2)

        # Get day_ids
        with store._connect() as conn:
            today_row = conn.execute("SELECT day_id FROM day_context WHERE local_date = ?", (TODAY,)).fetchone()
            tomorrow_row = conn.execute("SELECT day_id FROM day_context WHERE local_date = ?", ("2026-03-26",)).fetchone()

        count = store.rollover_daily_todos(CHAT_ID, today_row["day_id"], tomorrow_row["day_id"])
        assert count == 1  # only the open one

        # Source todo should be 'rolled'
        today_todos = store.list_daily_todos(CHAT_ID, TODAY)
        rolled = [t for t in today_todos if t["status"] == "rolled"]
        assert len(rolled) == 1

        # Tomorrow should have the rolled-over todo
        tomorrow_todos = store.list_daily_todos(CHAT_ID, "2026-03-26")
        assert len(tomorrow_todos) == 1
        assert tomorrow_todos[0]["title"] == "Unfinished task"
        assert tomorrow_todos[0]["source"] == "rollover"

    def test_rollover_is_idempotent(self, store):
        store.create_daily_todo(CHAT_ID, TODAY, "Task X")

        clock2 = FixedClock(datetime(2026, 3, 26, 14, 0, tzinfo=timezone.utc))
        resolver2 = DefaultTimezoneResolver(store, clock=clock2)
        store.ensure_day_open(resolver2.resolve_now(CHAT_ID))

        with store._connect() as conn:
            today_id = conn.execute("SELECT day_id FROM day_context WHERE local_date = ?", (TODAY,)).fetchone()["day_id"]
            tomorrow_id = conn.execute("SELECT day_id FROM day_context WHERE local_date = ?", ("2026-03-26",)).fetchone()["day_id"]

        count1 = store.rollover_daily_todos(CHAT_ID, today_id, tomorrow_id)
        assert count1 == 1
        # Second rollover should find nothing (source is now 'rolled')
        count2 = store.rollover_daily_todos(CHAT_ID, today_id, tomorrow_id)
        assert count2 == 0


# --- DaySnapshot includes todos ---

class TestDaySnapshotTodos:
    def test_snapshot_includes_todos(self, store):
        store.create_daily_todo(CHAT_ID, TODAY, "Snapshot task", category="must_win")
        snapshot = store.get_day_snapshot(CHAT_ID, TODAY)
        assert snapshot is not None
        assert len(snapshot.todos) == 1
        assert snapshot.todos[0]["title"] == "Snapshot task"
        assert snapshot.todos[0]["category"] == "must_win"

    def test_snapshot_empty_todos_by_default(self, store):
        snapshot = store.get_day_snapshot(CHAT_ID, TODAY)
        assert snapshot is not None
        assert snapshot.todos == []


# --- Habit CRUD ---

class TestHabitCRUD:
    def test_create_habit(self, store):
        result = store.create_habit_definition(CHAT_ID, "Journaling", "daily")
        assert result["name"] == "Journaling"
        assert result["active"] == 1
        assert result["user_managed"] == 1

    def test_disable_habit_persists_across_day_open(self, store):
        store.create_habit_definition(CHAT_ID, "Test habit", "daily")
        store.update_habit_definition(CHAT_ID, "test_habit", active=False)

        # Verify disabled
        with store._connect() as conn:
            row = conn.execute("SELECT active, user_managed FROM habit_definition WHERE habit_id = 'test_habit'").fetchone()
        assert row["active"] == 0
        assert row["user_managed"] == 1

        # Re-open the day (which calls ensure_habit_definitions)
        clock = FixedClock(datetime(2026, 3, 26, 14, 0, tzinfo=timezone.utc))
        resolver = DefaultTimezoneResolver(store, clock=clock)
        store.ensure_day_open(resolver.resolve_now(CHAT_ID))

        # Agent-created habit should stay disabled (user_managed=1)
        with store._connect() as conn:
            row = conn.execute("SELECT active FROM habit_definition WHERE habit_id = 'test_habit'").fetchone()
        assert row["active"] == 0

    def test_rename_habit(self, store):
        store.create_habit_definition(CHAT_ID, "Old name")
        result = store.update_habit_definition(CHAT_ID, "old_name", name="New name")
        assert result is not None
        assert result["name"] == "New name"


# --- Reflections ---

class TestReflections:
    def test_save_and_get_reflection(self, store):
        store.save_reflection(CHAT_ID, TODAY, went_well="Shipped feature", went_poorly="Skipped gym", lessons="Prioritize health")
        ref = store.get_reflection(CHAT_ID, TODAY)
        assert ref["went_well"] == "Shipped feature"
        assert ref["went_poorly"] == "Skipped gym"
        assert ref["lessons"] == "Prioritize health"

    def test_partial_reflection(self, store):
        store.save_reflection(CHAT_ID, TODAY, went_well="Good day")
        ref = store.get_reflection(CHAT_ID, TODAY)
        assert ref["went_well"] == "Good day"
        assert ref["went_poorly"] == ""

    def test_reflection_in_snapshot(self, store):
        store.save_reflection(CHAT_ID, TODAY, went_well="Nailed it")
        snapshot = store.get_day_snapshot(CHAT_ID, TODAY)
        assert snapshot.reflections["went_well"] == "Nailed it"

    def test_empty_reflection_for_unknown_date(self, store):
        ref = store.get_reflection(CHAT_ID, "2099-01-01")
        assert ref == {"went_well": "", "went_poorly": "", "lessons": ""}


# --- Projection includes todos ---

class TestProjectionTodos:
    def test_private_log_includes_todos(self, store, tmp_path):
        monkeypatch_dir = tmp_path / ".bestupid-private" / "day_logs"
        store.create_daily_todo(CHAT_ID, TODAY, "Projection task", category="can_do")

        proj = PrivateProjectionService(store)
        snapshot = store.get_day_snapshot(CHAT_ID, TODAY)
        out_path = proj.render_private_day_log(snapshot.day_id)

        content = out_path.read_text()
        assert "## Todos" in content
        assert "Projection task" in content
        assert "(can_do)" in content
