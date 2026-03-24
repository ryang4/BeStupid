"""Tests for keyboards.py — pure function tests, zero mocking."""
import pytest
from unittest.mock import MagicMock

from keyboards import (
    parse_callback_data,
    build_morning_keyboard,
    build_habit_keyboard,
    build_evening_keyboard,
    build_strategy_eval_keyboard,
    build_timeblock_ack_keyboard,
)


# ───────────────────── parse_callback_data ─────────────────────


class TestParseCallbackData:
    def test_habit_done(self):
        prefix, params = parse_callback_data("h:yoga:done")
        assert prefix == "h"
        assert params == {"habit_id": "yoga", "action": "done"}

    def test_habit_undo(self):
        prefix, params = parse_callback_data("h:yoga:pending")
        assert prefix == "h"
        assert params == {"habit_id": "yoga", "action": "pending"}

    def test_metric_value(self):
        prefix, params = parse_callback_data("m:Weight:219")
        assert prefix == "m"
        assert params == {"field": "Weight", "value": "219"}

    def test_rating(self):
        prefix, params = parse_callback_data("r:Mood_AM:4")
        assert prefix == "r"
        assert params == {"field": "Mood_AM", "value": "4"}

    def test_goal_autopsy(self):
        prefix, params = parse_callback_data("g:loop_abc123def:drop")
        assert prefix == "g"
        assert params == {"loop_id": "loop_abc123def", "action": "drop"}

    def test_strategy(self):
        prefix, params = parse_callback_data("s:intv_abc12:keep")
        assert prefix == "s"
        assert params == {"intervention_id": "intv_abc12", "action": "keep"}

    def test_timeblock_ack(self):
        prefix, params = parse_callback_data("t:writing_0323:ack")
        assert prefix == "t"
        assert params == {"block_key": "writing_0323", "action": "ack"}

    def test_unknown_prefix_raises(self):
        with pytest.raises(ValueError, match="Unknown callback prefix"):
            parse_callback_data("x:unknown:data")

    def test_too_few_parts_raises(self):
        with pytest.raises(ValueError, match="Invalid callback data"):
            parse_callback_data("h:yoga")

    @pytest.mark.parametrize("data", [
        "h:yoga:done", "h:meditation:done", "h:writing:done",
        "m:Weight:219.5", "m:Weight:223", "r:Mood_AM:5",
        "r:Sleep_Quality:3", "r:Energy:4", "r:Focus:2",
        "g:loop_abcdef123456:drop", "g:loop_abcdef123456:break",
        "g:loop_abcdef123456:box",
        "s:intv_abcdef1234:keep", "s:intv_abcdef1234:adjust",
        "s:intv_abcdef1234:drop",
        "t:writing_20260323:ack",
    ])
    def test_all_callback_data_fits_64_bytes(self, data):
        assert len(data.encode("utf-8")) <= 64


# ───────────────────── Helpers ─────────────────────


def _make_snapshot(metrics=None, habits=None, open_loops=None):
    """Helper to create a mock DaySnapshot."""
    snap = MagicMock()
    snap.metrics = metrics or {}
    snap.habits = habits or []
    snap.open_loops = open_loops or []
    return snap


# ───────────────────── build_morning_keyboard ─────────────────────


class TestBuildMorningKeyboard:
    def test_includes_weight_buttons(self):
        snap = _make_snapshot(metrics={}, habits=[])
        kb = build_morning_keyboard(snap, "220")
        assert kb is not None
        weight_row = kb["inline_keyboard"][0]
        assert len(weight_row) == 3
        assert "219" in weight_row[0]["callback_data"]
        assert "220" in weight_row[1]["callback_data"]
        assert "221" in weight_row[2]["callback_data"]

    def test_skips_weight_when_no_history(self):
        snap = _make_snapshot(metrics={}, habits=[])
        kb = build_morning_keyboard(snap, None)
        if kb:
            for row in kb["inline_keyboard"]:
                for btn in row:
                    assert not btn["callback_data"].startswith("m:Weight")

    def test_skips_weight_when_already_logged(self):
        snap = _make_snapshot(metrics={"Weight": "220"}, habits=[])
        kb = build_morning_keyboard(snap, "220")
        if kb:
            for row in kb["inline_keyboard"]:
                for btn in row:
                    assert not btn["callback_data"].startswith("m:Weight")

    def test_skips_logged_metrics(self):
        snap = _make_snapshot(metrics={"Mood_AM": "4", "Sleep_Quality": "3"}, habits=[])
        kb = build_morning_keyboard(snap, "220")
        assert kb is not None
        for row in kb["inline_keyboard"]:
            for btn in row:
                assert "Mood_AM" not in btn["callback_data"]
                assert "Sleep_Quality" not in btn["callback_data"]

    def test_no_habit_buttons(self):
        habits = [
            {"name": "Yoga", "habit_id": "yoga", "status": "pending"},
            {"name": "Write", "habit_id": "writing", "status": "pending"},
        ]
        snap = _make_snapshot(habits=habits)
        kb = build_morning_keyboard(snap, None)
        if kb:
            for row in kb["inline_keyboard"]:
                for btn in row:
                    assert not btn["callback_data"].startswith("h:")

    def test_returns_none_when_all_metrics_logged(self):
        snap = _make_snapshot(
            metrics={"Weight": "220", "Mood_AM": "4", "Sleep_Quality": "3"},
            habits=[],
        )
        kb = build_morning_keyboard(snap, "220")
        assert kb is None

    def test_includes_mood_and_sleep_quality(self):
        snap = _make_snapshot(metrics={}, habits=[])
        kb = build_morning_keyboard(snap, None)
        assert kb is not None
        all_callbacks = [btn["callback_data"] for row in kb["inline_keyboard"] for btn in row]
        assert any("Mood_AM" in cb for cb in all_callbacks)
        assert any("Sleep_Quality" in cb for cb in all_callbacks)


# ───────────────────── build_habit_keyboard ─────────────────────


class TestBuildHabitKeyboard:
    def test_always_returns_none(self):
        """Habits are logged via text, not buttons."""
        habits = [
            {"name": "A", "habit_id": "a", "status": "pending"},
            {"name": "B", "habit_id": "b", "status": "pending"},
        ]
        snap = _make_snapshot(habits=habits)
        assert build_habit_keyboard(snap) is None

    def test_returns_none_when_no_habits(self):
        snap = _make_snapshot(habits=[])
        assert build_habit_keyboard(snap) is None


# ───────────────────── build_evening_keyboard ─────────────────────


class TestBuildEveningKeyboard:
    def test_includes_pm_metrics(self):
        snap = _make_snapshot(metrics={}, habits=[])
        kb = build_evening_keyboard(snap)
        assert kb is not None
        all_callbacks = [btn["callback_data"] for row in kb["inline_keyboard"] for btn in row]
        assert any("Mood_PM" in cb for cb in all_callbacks)
        assert any("Energy" in cb for cb in all_callbacks)
        assert any("Focus" in cb for cb in all_callbacks)

    def test_skips_logged_pm_metrics(self):
        snap = _make_snapshot(metrics={"Mood_PM": "3", "Energy": "4", "Focus": "3"}, habits=[])
        kb = build_evening_keyboard(snap, stale_loops=None)
        # No metrics to show, no habits, no stale loops → None
        assert kb is None

    def test_includes_stale_loops(self):
        snap = _make_snapshot(metrics={"Mood_PM": "3", "Energy": "4", "Focus": "3"}, habits=[])
        stale = [{"loop_id": "loop_abc", "title": "Write AWS post"}]
        kb = build_evening_keyboard(snap, stale)
        assert kb is not None
        autopsy_row = [r for r in kb["inline_keyboard"] if any("g:" in b["callback_data"] for b in r)]
        assert len(autopsy_row) == 1
        assert len(autopsy_row[0]) == 3  # break, box, drop

    def test_no_stale_loops_no_autopsy_buttons(self):
        snap = _make_snapshot(metrics={}, habits=[])
        kb = build_evening_keyboard(snap, stale_loops=None)
        if kb:
            for row in kb["inline_keyboard"]:
                for btn in row:
                    assert not btn["callback_data"].startswith("g:")

    def test_max_3_stale_loops(self):
        snap = _make_snapshot(metrics={"Mood_PM": "3", "Energy": "4", "Focus": "3"}, habits=[])
        stale = [
            {"loop_id": f"loop_{i}", "title": f"Task {i}"} for i in range(5)
        ]
        kb = build_evening_keyboard(snap, stale)
        autopsy_rows = [r for r in kb["inline_keyboard"] if any("g:" in b["callback_data"] for b in r)]
        assert len(autopsy_rows) == 3  # Capped at 3


# ───────────────────── Static keyboard builders ─────────────────────


class TestStaticKeyboards:
    def test_strategy_eval_keyboard(self):
        kb = build_strategy_eval_keyboard("intv_abc")
        assert len(kb["inline_keyboard"]) == 1
        row = kb["inline_keyboard"][0]
        assert len(row) == 3
        actions = [btn["callback_data"] for btn in row]
        assert "s:intv_abc:keep" in actions
        assert "s:intv_abc:adjust" in actions
        assert "s:intv_abc:drop" in actions

    def test_timeblock_ack_keyboard(self):
        kb = build_timeblock_ack_keyboard("writing_0323")
        assert len(kb["inline_keyboard"]) == 1
        assert kb["inline_keyboard"][0][0]["callback_data"] == "t:writing_0323:ack"
