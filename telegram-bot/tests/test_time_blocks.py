"""Tests for time_blocks.py — pure function tests."""
from datetime import datetime

from time_blocks import compute_todays_blocks, find_upcoming_transition


class TestComputeTodaysBlocks:
    def test_returns_habit_blocks_for_active_habits(self):
        habits = [
            {"habit_id": "yoga", "name": "10 min yoga"},
            {"habit_id": "writing", "name": "Write for 1 hour"},
        ]
        blocks = compute_todays_blocks("", "Monday", habits)
        labels = [b["label"] for b in blocks]
        assert "Yoga" in labels
        assert "Writing" in labels
        assert "Reading" not in labels  # Not in active habits

    def test_blocks_sorted_by_start_time(self):
        habits = [
            {"habit_id": "reading", "name": "Read"},
            {"habit_id": "yoga", "name": "Yoga"},
            {"habit_id": "writing", "name": "Write"},
        ]
        blocks = compute_todays_blocks("", "Monday", habits)
        times = [(b["start_hour"], b["start_min"]) for b in blocks]
        assert times == sorted(times)

    def test_workout_block_from_protocol(self):
        protocol = "| Monday | Swim | 800m freestyle |\n| Tuesday | Strength | Workout A |"
        blocks = compute_todays_blocks(protocol, "Monday", [])
        assert any("Swim" in b["label"] for b in blocks)

    def test_no_workout_on_rest_day(self):
        protocol = "| Monday | Swim | 800m |\n| Tuesday | Strength | A |"
        blocks = compute_todays_blocks(protocol, "Sunday", [])
        assert not any("Swim" in b["label"] or "Strength" in b["label"] for b in blocks)

    def test_empty_inputs(self):
        blocks = compute_todays_blocks("", "", [])
        assert blocks == []

    def test_all_habits_produce_blocks(self):
        habits = [
            {"habit_id": "meditation", "name": "3 min meditation"},
            {"habit_id": "yoga", "name": "10 min yoga"},
            {"habit_id": "writing", "name": "Write for 1 hour"},
            {"habit_id": "substack", "name": "Post 1 Substack note"},
            {"habit_id": "note_ideas", "name": "Record 5 note ideas"},
            {"habit_id": "reading", "name": "Read for 30 min"},
        ]
        blocks = compute_todays_blocks("", "Monday", habits)
        assert len(blocks) == 6

    def test_workout_label_truncated(self):
        protocol = "| Monday | Very Long Workout Type Name That Exceeds Thirty Characters | details |"
        blocks = compute_todays_blocks(protocol, "Monday", [])
        assert len(blocks) == 1
        assert len(blocks[0]["label"]) <= 30


class TestFindUpcomingTransition:
    def test_detects_transition_within_5_min(self):
        blocks = [
            {"label": "Writing", "start_hour": 10, "start_min": 0, "end_hour": 11, "end_min": 0},
            {"label": "Reading", "start_hour": 14, "start_min": 0, "end_hour": 14, "end_min": 30},
        ]
        now = datetime(2026, 3, 23, 10, 56, 0)
        result = find_upcoming_transition(blocks, now, lookahead_min=5)
        assert result is not None
        assert result["current_block"]["label"] == "Writing"
        assert result["next_block"]["label"] == "Reading"
        assert result["minutes_remaining"] == 4

    def test_no_transition_when_not_near_end(self):
        blocks = [
            {"label": "Writing", "start_hour": 10, "start_min": 0, "end_hour": 11, "end_min": 0},
        ]
        now = datetime(2026, 3, 23, 10, 30, 0)
        result = find_upcoming_transition(blocks, now, lookahead_min=5)
        assert result is None

    def test_last_block_has_no_next(self):
        blocks = [
            {"label": "Reading", "start_hour": 14, "start_min": 0, "end_hour": 14, "end_min": 30},
        ]
        now = datetime(2026, 3, 23, 14, 27, 0)
        result = find_upcoming_transition(blocks, now, lookahead_min=5)
        assert result is not None
        assert result["next_block"] is None

    def test_no_blocks_returns_none(self):
        result = find_upcoming_transition([], datetime.now())
        assert result is None

    def test_past_block_end_returns_none(self):
        blocks = [
            {"label": "Writing", "start_hour": 10, "start_min": 0, "end_hour": 11, "end_min": 0},
        ]
        now = datetime(2026, 3, 23, 11, 5, 0)
        result = find_upcoming_transition(blocks, now, lookahead_min=5)
        assert result is None

    def test_exactly_at_boundary(self):
        blocks = [
            {"label": "Writing", "start_hour": 10, "start_min": 0, "end_hour": 11, "end_min": 0},
        ]
        now = datetime(2026, 3, 23, 11, 0, 0)
        result = find_upcoming_transition(blocks, now, lookahead_min=5)
        assert result is None  # 0 seconds remaining, not > 0

    def test_one_minute_remaining(self):
        blocks = [
            {"label": "Writing", "start_hour": 10, "start_min": 0, "end_hour": 11, "end_min": 0},
        ]
        now = datetime(2026, 3, 23, 10, 59, 0)
        result = find_upcoming_transition(blocks, now, lookahead_min=5)
        assert result is not None
        assert result["minutes_remaining"] == 1
