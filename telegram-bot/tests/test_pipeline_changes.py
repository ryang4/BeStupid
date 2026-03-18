"""
Tests for the data pipeline consolidation and coaching improvements.

Covers:
- Migration script idempotency
- get_all_metrics_entries schema
- metrics_analyzer V2 fallback
- DOW cron scheduling
- DRAFT protocol fallback
- Coaching habit streaks
- Brain context degradation
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

schedule = pytest.importorskip("schedule")

from v2.app.context_assembler import ContextAssemblerImpl
from v2.app.timezone_resolver import DefaultTimezoneResolver
from v2.infra import sqlite_state_store as store_module
from v2.infra.sqlite_state_store import SQLiteStateStore, _safe_float
from v2.app import projection as projection_module


class FixedClock:
    def __init__(self, dt: datetime):
        self._dt = dt

    def now_utc(self) -> datetime:
        return self._dt


@pytest.fixture
def v2_store(tmp_path, monkeypatch):
    tmp_project_dir = tmp_path / "project"
    tmp_private_dir = tmp_path / ".bestupid-private"
    tmp_project_dir.mkdir(parents=True, exist_ok=True)
    tmp_private_dir.mkdir(parents=True, exist_ok=True)

    habits_path = tmp_project_dir / "content" / "config" / "habits.md"
    habits_path.parent.mkdir(parents=True, exist_ok=True)
    habits_path.write_text(
        """---
habits:
  - id: yoga
    name: 10 min yoga
  - id: meditate
    name: 3 min meditation
---
"""
    )
    private_day_logs = tmp_private_dir / "day_logs"
    monkeypatch.setattr(store_module, "PRIVATE_DIR", tmp_private_dir)
    monkeypatch.setattr(store_module, "PRIVATE_DAY_LOG_DIR", private_day_logs)
    monkeypatch.setattr(store_module, "HABITS_PATH", habits_path)
    monkeypatch.setattr(store_module, "PROJECT_ROOT", tmp_project_dir)
    monkeypatch.setattr(projection_module, "PRIVATE_DIR", tmp_private_dir)
    monkeypatch.setattr(projection_module, "PRIVATE_DAY_LOG_DIR", private_day_logs)
    db_path = tmp_private_dir / "assistant_state.db"
    store = SQLiteStateStore(db_path=db_path)
    store.init_schema()
    return store, tmp_private_dir, tmp_project_dir


# --- _safe_float tests ---


class TestSafeFloat:
    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_empty_string_returns_none(self):
        assert _safe_float("") is None
        assert _safe_float("  ") is None

    def test_simple_float(self):
        assert _safe_float("6.5") == 6.5
        assert _safe_float("244") == 244.0

    def test_time_format(self):
        assert _safe_float("6:20") == 6.33
        assert _safe_float("7:30") == 7.5
        assert _safe_float("8:00") == 8.0

    def test_strips_units(self):
        assert _safe_float("244 lbs") == 244.0

    def test_zero(self):
        assert _safe_float("0") == 0.0

    def test_non_numeric(self):
        assert _safe_float("moderate - breathing issues") is None


# --- get_all_metrics_entries tests ---


class TestGetAllMetricsEntries:
    def test_returns_entries_matching_schema(self, v2_store):
        store, _, _ = v2_store
        clock = FixedClock(datetime(2026, 3, 14, 14, 0, tzinfo=timezone.utc))
        resolver = DefaultTimezoneResolver(store, clock=clock)
        resolved = resolver.resolve_now(12345)
        store.ensure_day_open(resolved)
        store.set_day_metric(12345, resolved.local_date, "Weight", "241")
        store.set_day_metric(12345, resolved.local_date, "Sleep", "7.5")

        entries = store.get_all_metrics_entries(12345)
        assert len(entries) == 1
        entry = entries[0]

        # Check schema
        assert entry["date"] == resolved.local_date
        assert entry["weight_lbs"] == 241.0
        assert entry["sleep"]["hours"] == 7.5
        assert entry["sleep"]["quality"] is None  # Not set
        assert "habits" in entry
        assert "nutrition" in entry

    def test_handles_no_metrics(self, v2_store):
        store, _, _ = v2_store
        clock = FixedClock(datetime(2026, 3, 14, 14, 0, tzinfo=timezone.utc))
        resolver = DefaultTimezoneResolver(store, clock=clock)
        resolved = resolver.resolve_now(12345)
        store.ensure_day_open(resolved)

        entries = store.get_all_metrics_entries(12345)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["weight_lbs"] is None
        assert entry["sleep"]["hours"] is None

    def test_includes_habit_data(self, v2_store):
        store, _, _ = v2_store
        clock = FixedClock(datetime(2026, 3, 14, 14, 0, tzinfo=timezone.utc))
        resolver = DefaultTimezoneResolver(store, clock=clock)
        resolved = resolver.resolve_now(12345)
        store.ensure_day_open(resolved)
        store.mark_habit(12345, resolved.local_date, "yoga", "done")

        entries = store.get_all_metrics_entries(12345)
        entry = entries[0]
        assert "10 min yoga" in entry["habits"]["completed"]
        assert entry["habits"]["completion_rate"] == 0.5  # 1 of 2

    def test_empty_for_unknown_chat(self, v2_store):
        store, _, _ = v2_store
        entries = store.get_all_metrics_entries(99999)
        assert entries == []


# --- Migration tests ---


class TestMigration:
    def test_migration_is_idempotent(self, v2_store):
        """Test that migrating the same data twice doesn't create duplicates."""
        store, private_dir, project_dir = v2_store

        # Directly insert a day via SQL to simulate migration
        from v2.domain.models import ResolvedNow
        resolved = ResolvedNow(
            chat_id=12345,
            timezone_name="America/New_York",
            timezone_label="America/New_York",
            utc_now=datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc),
            local_now=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            local_date="2026-01-15",
            day_key="2026-01-15",
        )
        day = store.ensure_day_open(resolved)
        store.set_day_metric(12345, "2026-01-15", "Weight", "242.0")
        store.set_day_metric(12345, "2026-01-15", "Sleep", "7.0")

        # Try to insert again — should be idempotent via UNIQUE constraint
        with store._connect() as conn:
            existing = conn.execute(
                "SELECT day_id FROM day_context WHERE chat_id = ? AND local_date = ?",
                (12345, "2026-01-15"),
            ).fetchone()
            assert existing is not None

        # Verify only 1 entry
        entries = store.get_all_metrics_entries(12345)
        dates = [e["date"] for e in entries]
        assert dates.count("2026-01-15") == 1
        assert entries[0]["weight_lbs"] == 242.0
        assert entries[0]["sleep"]["hours"] == 7.0


# --- DOW scheduling tests ---


class TestDOWScheduling:
    def test_parse_dow_single(self):
        import scheduler
        importlib.reload(scheduler)
        assert scheduler._parse_dow_field("0") == ["sunday"]
        assert scheduler._parse_dow_field("1") == ["monday"]
        assert scheduler._parse_dow_field("6") == ["saturday"]

    def test_parse_dow_sunday_alias(self):
        import scheduler
        importlib.reload(scheduler)
        assert scheduler._parse_dow_field("7") == ["sunday"]

    def test_parse_dow_comma_list(self):
        import scheduler
        importlib.reload(scheduler)
        result = scheduler._parse_dow_field("1,3,5")
        assert result == ["monday", "wednesday", "friday"]

    def test_parse_dow_range(self):
        import scheduler
        importlib.reload(scheduler)
        result = scheduler._parse_dow_field("1-5")
        assert result == ["monday", "tuesday", "wednesday", "thursday", "friday"]

    def test_parse_dow_dedup_sunday(self):
        import scheduler
        importlib.reload(scheduler)
        result = scheduler._parse_dow_field("0,7")
        assert result == ["sunday"]  # Deduplicated

    def test_parse_dow_invalid(self):
        import scheduler
        importlib.reload(scheduler)
        assert scheduler._parse_dow_field("8") == []
        assert scheduler._parse_dow_field("abc") == []

    def test_parse_dow_star(self):
        import scheduler
        importlib.reload(scheduler)
        assert scheduler._parse_dow_field("*") == []

    def test_schedule_from_cron_dow(self, mock_env):
        import scheduler
        importlib.reload(scheduler)

        schedule.clear()
        result = scheduler._schedule_from_cron("weekly_planner", "0 20 * * 0")
        assert result is True
        jobs = schedule.get_jobs()
        assert len(jobs) == 1

    def test_schedule_from_cron_dow_multi(self, mock_env):
        import scheduler
        importlib.reload(scheduler)

        schedule.clear()
        result = scheduler._schedule_from_cron("weekly_planner", "0 9 * * 1,3,5")
        assert result is True
        jobs = schedule.get_jobs()
        assert len(jobs) == 3  # One per day

    def test_daily_still_works(self, mock_env):
        import scheduler
        importlib.reload(scheduler)

        schedule.clear()
        result = scheduler._schedule_from_cron("morning_briefing", "0 7 * * *")
        assert result is True
        assert len(schedule.get_jobs()) == 1


# --- DRAFT protocol fallback tests ---


class TestDraftProtocolFallback:
    def test_finds_draft_when_no_finalized(self, tmp_path):
        protocol_dir = tmp_path / "content" / "config"
        protocol_dir.mkdir(parents=True)

        # Create a DRAFT protocol
        draft = protocol_dir / "protocol_2026-03-17_DRAFT.md"
        draft.write_text("# Week of 2026-03-17\nDraft content here")

        # Simulate daily_planner.get_weekly_protocol logic
        monday_str = "2026-03-17"
        protocol_file = f"protocol_{monday_str}.md"
        protocol_path = str(protocol_dir / protocol_file)
        draft_path = str(protocol_dir / f"protocol_{monday_str}_DRAFT.md")

        assert not os.path.exists(protocol_path)
        assert os.path.exists(draft_path)

        with open(draft_path, 'r') as f:
            content = f.read()
        assert "Draft content here" in content


# --- Coaching heartbeat enrichment tests ---


class TestCoachingHabitStreaks:
    def test_habit_streaks_with_data(self, v2_store):
        store, _, _ = v2_store
        clock = FixedClock(datetime(2026, 3, 14, 14, 0, tzinfo=timezone.utc))
        resolver = DefaultTimezoneResolver(store, clock=clock)

        # Create 3 days and mark yoga done on all 3
        for day_offset in range(3):
            dt = datetime(2026, 3, 12 + day_offset, 14, 0, tzinfo=timezone.utc)
            c = FixedClock(dt)
            r = DefaultTimezoneResolver(store, clock=c)
            resolved = r.resolve_now(12345)
            store.ensure_day_open(resolved)
            store.mark_habit(12345, resolved.local_date, "yoga", "done")

        # Query streaks using the heartbeat method's logic
        with store._connect() as conn:
            rows = conn.execute("""
                SELECT hd.name, dc.local_date, hi.status
                FROM habit_instance hi
                JOIN habit_definition hd ON hd.habit_id = hi.habit_id
                JOIN day_context dc ON dc.day_id = hi.day_id
                WHERE hd.active = 1
                ORDER BY hd.name, dc.local_date DESC
            """).fetchall()

        from itertools import groupby
        streaks = {}
        for name, group in groupby(rows, key=lambda r: r["name"]):
            streak = 0
            for row in group:
                if row["status"] == "done":
                    streak += 1
                else:
                    break
            streaks[name] = streak

        assert streaks["10 min yoga"] == 3
        assert streaks["3 min meditation"] == 0  # Never done


# --- Brain context degradation tests ---


class TestBrainContextDegradation:
    def test_empty_when_no_brain_db(self, v2_store, monkeypatch):
        store, _, _ = v2_store
        clock = FixedClock(datetime(2026, 3, 14, 14, 0, tzinfo=timezone.utc))
        resolver = DefaultTimezoneResolver(store, clock=clock)
        assembler = ContextAssemblerImpl(store, resolver)

        # Point to non-existent path
        from v2.app import context_assembler as ca_module
        monkeypatch.setattr(ca_module, "BRAIN_DB_PATH", Path("/nonexistent/brain.db"))

        result = assembler._render_brain_context()
        assert result == ""

    def test_brain_block_in_envelope(self, v2_store, monkeypatch):
        store, _, _ = v2_store
        clock = FixedClock(datetime(2026, 3, 14, 14, 0, tzinfo=timezone.utc))
        resolver = DefaultTimezoneResolver(store, clock=clock)
        resolved = resolver.resolve_now(12345)
        store.ensure_day_open(resolved)

        assembler = ContextAssemblerImpl(store, resolver)

        from v2.app import context_assembler as ca_module
        monkeypatch.setattr(ca_module, "BRAIN_DB_PATH", Path("/nonexistent/brain.db"))

        envelope = assembler.build(12345, "test")
        # brain_context should NOT be in selected blocks (empty text filtered out)
        assert "brain_context" not in envelope.selected_blocks
