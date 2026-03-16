"""
Tests for the V2 canonical state, context assembly, and projection path.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_client import _history_for_disk
from v2.app.context_assembler import ContextAssemblerImpl
from v2.app.memory_review import MemoryReviewServiceImpl
from v2.app import projection as projection_module
from v2.app.projection import PrivateProjectionService
from v2.app.timezone_resolver import DefaultTimezoneResolver, parse_timezone_spec
from v2.infra import sqlite_state_store as store_module
from v2.infra.sqlite_state_store import SQLiteStateStore


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
    return store, tmp_private_dir


def test_mark_update_processed_is_idempotent(v2_store):
    store, _ = v2_store
    assert store.mark_update_processed(12345, 999) is True
    assert store.mark_update_processed(12345, 999) is False


def test_ensure_day_open_creates_single_day_and_habit_instances(v2_store):
    store, _ = v2_store
    clock = FixedClock(datetime(2026, 3, 14, 14, 0, tzinfo=timezone.utc))
    resolver = DefaultTimezoneResolver(store, clock=clock)
    resolved = resolver.resolve_now(12345)

    first = store.ensure_day_open(resolved)
    second = store.ensure_day_open(resolved)

    assert first["day_id"] == second["day_id"]
    snapshot = store.get_day_snapshot(12345, resolved.local_date)
    assert snapshot is not None
    assert len(snapshot.habits) == 2


def test_memory_review_requires_approval_and_versions_active_memory(v2_store):
    store, _ = v2_store
    clock = FixedClock(datetime(2026, 3, 14, 14, 0, tzinfo=timezone.utc))
    resolver = DefaultTimezoneResolver(store, clock=clock)
    resolved = resolver.resolve_now(12345)
    store.ensure_day_open(resolved)
    review = MemoryReviewServiceImpl(store)

    session = store.get_or_create_session(12345, clock.now_utc())
    turn_id_1 = store.record_turn(12345, session["session_id"], 1, "user", "I prefer black coffee.")
    created_1 = review.extract_candidates(12345, turn_id_1, "I prefer black coffee.")
    assert created_1
    assert store.get_approved_memories(12345) == []

    approved_1 = review.review_candidate(12345, created_1[0].candidate_id, "approve")
    assert approved_1["status"] == "approved"
    memories_after_first = store.get_approved_memories(12345)
    assert len(memories_after_first) == 1
    assert memories_after_first[0]["version"] == 1

    turn_id_2 = store.record_turn(12345, session["session_id"], 2, "user", "I prefer black coffee.")
    created_2 = review.extract_candidates(12345, turn_id_2, "I prefer black coffee.")
    approved_2 = review.review_candidate(12345, created_2[0].candidate_id, "approve")
    assert approved_2["status"] == "approved"

    memories_after_second = store.get_approved_memories(12345)
    assert len(memories_after_second) == 1
    assert memories_after_second[0]["version"] == 2


def test_context_assembler_includes_corrections_and_recent_messages(v2_store):
    store, _ = v2_store
    clock = FixedClock(datetime(2026, 3, 14, 14, 0, tzinfo=timezone.utc))
    resolver = DefaultTimezoneResolver(store, clock=clock)
    resolved = resolver.set_current_timezone(12345, "UTC-5", source="test")
    day = store.ensure_day_open(resolved)
    store.record_day_correction(12345, resolved.local_date, "User corrected the day reference to Thursday")

    session = store.get_or_create_session(12345, clock.now_utc())
    store.record_turn(12345, session["session_id"], 10, "user", "Today is Thursday.")
    store.record_turn(12345, session["session_id"], 10, "assistant", "I updated the day context.")
    store.refresh_session_summary(session["session_id"])
    store.create_open_loop(12345, "Follow up with Sarah", "followup", priority="high", day_id=day["day_id"])

    assembler = ContextAssemblerImpl(store, resolver)
    envelope = assembler.build(12345, "What's relevant?")

    assert "timezone_and_clock_snapshot" in envelope.selected_blocks
    assert "current_day_snapshot" in envelope.selected_blocks
    assert "recent_corrections" in envelope.selected_blocks
    assert "UTC-05:00" in envelope.dynamic_system_prompt
    assert "User corrected the day reference to Thursday" in envelope.dynamic_system_prompt
    assert envelope.estimated_tokens <= 2500
    assert envelope.recent_messages[-1]["content"] == "I updated the day context."


def test_private_projection_renders_inside_private_dir(v2_store):
    store, tmp_private_dir = v2_store
    clock = FixedClock(datetime(2026, 3, 14, 14, 0, tzinfo=timezone.utc))
    resolver = DefaultTimezoneResolver(store, clock=clock)
    resolved = resolver.resolve_now(12345)
    day = store.ensure_day_open(resolved)
    store.set_day_metric(12345, resolved.local_date, "Weight", "241")
    store.append_food(12345, resolved.local_date, "Chicken bowl")
    projection = PrivateProjectionService(store)

    path = projection.render_private_day_log(day["day_id"])

    assert path.exists()
    assert str(path).startswith(str(tmp_private_dir))
    contents = path.read_text()
    assert "Weight: 241" in contents
    assert "Chicken bowl" in contents


def test_parse_timezone_spec_supports_utc_offsets():
    parsed = parse_timezone_spec("UTC-5")
    assert parsed.canonical_name == "UTC-05:00"
    assert parsed.label == "UTC-05:00"


def test_history_for_disk_strips_tool_blocks():
    history = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Visible"},
                {"type": "tool_use", "name": "dangerous"},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "content": "Hidden tool output"},
                {"type": "text", "text": "Visible result"},
            ],
        },
    ]

    compact = _history_for_disk(history)

    assert compact == [
        {"role": "assistant", "content": "Visible"},
        {"role": "user", "content": "Visible result"},
    ]
