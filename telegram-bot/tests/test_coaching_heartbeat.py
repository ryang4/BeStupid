"""
Tests for the adaptive coaching heartbeat.

The evaluate_checkin() tests require zero mocking — they test a pure function.
Integration tests mock the Claude CLI subprocess and Telegram sender.
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coaching_heartbeat import CoachingHeartbeat, evaluate_checkin


# ---------------------------------------------------------------------------
# Pure function tests: evaluate_checkin
# ---------------------------------------------------------------------------


class TestEvaluateCheckin:
    """Tests for the pure evaluate_checkin function. No mocking needed."""

    def test_morning_window(self):
        now = datetime(2026, 3, 16, 7, 30)
        assert evaluate_checkin(now, None, None, None, set()) == "morning"

    def test_morning_boundary_start(self):
        now = datetime(2026, 3, 16, 7, 0, 0)
        assert evaluate_checkin(now, None, None, None, set()) == "morning"

    def test_morning_boundary_end(self):
        """8:00 is outside the morning window."""
        now = datetime(2026, 3, 16, 8, 0, 0)
        assert evaluate_checkin(now, None, None, None, set()) is None

    def test_midday_window(self):
        now = datetime(2026, 3, 16, 12, 0)
        assert evaluate_checkin(now, None, None, None, set()) == "midday"

    def test_afternoon_window(self):
        now = datetime(2026, 3, 16, 15, 30)
        assert evaluate_checkin(now, None, None, None, set()) == "afternoon"

    def test_evening_window(self):
        now = datetime(2026, 3, 16, 20, 45)
        assert evaluate_checkin(now, None, None, None, set()) == "evening"

    def test_quiet_hours_before_7am(self):
        now = datetime(2026, 3, 16, 6, 59)
        assert evaluate_checkin(now, None, None, None, set()) is None

    def test_quiet_hours_after_9pm(self):
        now = datetime(2026, 3, 16, 21, 0)
        assert evaluate_checkin(now, None, None, None, set()) is None

    def test_quiet_hours_midnight(self):
        now = datetime(2026, 3, 16, 0, 0)
        assert evaluate_checkin(now, None, None, None, set()) is None

    def test_muted(self):
        now = datetime(2026, 3, 16, 7, 30)
        mute_until = now + timedelta(hours=1)
        assert evaluate_checkin(now, None, None, mute_until, set()) is None

    def test_mute_expired(self):
        now = datetime(2026, 3, 16, 7, 30)
        mute_until = now - timedelta(minutes=1)
        assert evaluate_checkin(now, None, None, mute_until, set()) == "morning"

    def test_rate_limited(self):
        now = datetime(2026, 3, 16, 12, 0)
        last_checkin = now - timedelta(minutes=30)
        assert evaluate_checkin(now, last_checkin, None, None, set()) is None

    def test_rate_limit_expired(self):
        now = datetime(2026, 3, 16, 12, 0)
        last_checkin = now - timedelta(minutes=61)
        assert evaluate_checkin(now, last_checkin, None, None, set()) == "midday"

    def test_window_already_sent(self):
        now = datetime(2026, 3, 16, 7, 30)
        assert evaluate_checkin(now, None, None, None, {"morning"}) is None

    def test_midday_suppressed_by_activity(self):
        now = datetime(2026, 3, 16, 12, 0)
        last_activity = now - timedelta(minutes=20)
        assert evaluate_checkin(now, None, last_activity, None, set()) is None

    def test_afternoon_suppressed_by_activity(self):
        now = datetime(2026, 3, 16, 15, 30)
        last_activity = now - timedelta(minutes=10)
        assert evaluate_checkin(now, None, last_activity, None, set()) is None

    def test_morning_not_suppressed_by_activity(self):
        """Morning window fires even if user was active recently."""
        now = datetime(2026, 3, 16, 7, 30)
        last_activity = now - timedelta(minutes=10)
        assert evaluate_checkin(now, None, last_activity, None, set()) == "morning"

    def test_evening_not_suppressed_by_activity(self):
        """Evening window fires even if user was active recently."""
        now = datetime(2026, 3, 16, 20, 30)
        last_activity = now - timedelta(minutes=10)
        assert evaluate_checkin(now, None, last_activity, None, set()) == "evening"

    def test_midday_fires_after_activity_cooldown(self):
        now = datetime(2026, 3, 16, 12, 0)
        last_activity = now - timedelta(minutes=50)  # > 45 min
        assert evaluate_checkin(now, None, last_activity, None, set()) == "midday"

    def test_between_windows(self):
        """9am is between morning (7-8) and midday (11-13)."""
        now = datetime(2026, 3, 16, 9, 0)
        assert evaluate_checkin(now, None, None, None, set()) is None

    def test_multiple_windows_sent(self):
        """Only returns windows not yet sent."""
        now = datetime(2026, 3, 16, 20, 30)
        sent = {"morning", "midday", "afternoon"}
        assert evaluate_checkin(now, None, None, None, sent) == "evening"

    def test_all_windows_sent(self):
        now = datetime(2026, 3, 16, 20, 30)
        sent = {"morning", "midday", "afternoon", "evening"}
        assert evaluate_checkin(now, None, None, None, sent) is None


# ---------------------------------------------------------------------------
# CoachingHeartbeat unit tests
# ---------------------------------------------------------------------------


@pytest.fixture
def coaching_prompt(tmp_path):
    """Create a temporary coaching prompt file."""
    prompt = tmp_path / "coaching_prompt.md"
    prompt.write_text("You are a test coaching prompt.")
    return prompt


@pytest.fixture
def mock_services():
    """Mock V2 services for coaching heartbeat."""
    services = MagicMock()
    services.store.get_day_snapshot.return_value = MagicMock(
        metrics={"Weight": "185", "Sleep": "7.5"},
        habits=[
            {"name": "yoga", "status": "pending", "habit_id": "1"},
            {"name": "meditation", "status": "done", "habit_id": "2"},
        ],
        foods=[{"calories": "500", "protein_g": "30"}],
        open_loops=[{"title": "Write AWS post", "loop_id": "1"}],
    )
    services.reminder_policy.next_actions.return_value = [
        MagicMock(message="Missing morning check-in fields: Weight"),
    ]
    services.timezone_resolver.resolve_now.return_value = MagicMock(
        timezone_label="America/New_York",
    )
    return services


@pytest.fixture
def heartbeat(coaching_prompt, mock_services):
    """Create a CoachingHeartbeat instance for testing."""
    return CoachingHeartbeat(
        chat_id=12345,
        get_conversation=MagicMock(return_value=MagicMock(history=[], save_to_disk=MagicMock())),
        chat_lock=asyncio.Lock(),
        services=mock_services,
        send_telegram=AsyncMock(return_value=True),
        prompt_path=coaching_prompt,
    )


class TestCoachingHeartbeat:

    def test_init_raises_on_missing_prompt(self, mock_services):
        with pytest.raises(FileNotFoundError):
            CoachingHeartbeat(
                chat_id=12345,
                get_conversation=MagicMock(),
                chat_lock=asyncio.Lock(),
                services=mock_services,
                send_telegram=AsyncMock(),
                prompt_path=Path("/nonexistent/prompt.md"),
            )

    def test_mute_clamps_min(self, heartbeat):
        minutes = heartbeat.mute(0)
        assert minutes == 1
        assert heartbeat.is_muted()

    def test_mute_clamps_max(self, heartbeat):
        minutes = heartbeat.mute(9999)
        assert minutes == 1440
        assert heartbeat.is_muted()

    def test_mute_and_unmute(self, heartbeat):
        heartbeat.mute(60)
        assert heartbeat.is_muted()
        heartbeat.unmute()
        assert not heartbeat.is_muted()

    def test_record_activity(self, heartbeat):
        assert heartbeat._last_activity is None
        heartbeat.record_activity()
        assert heartbeat._last_activity is not None

    def test_daily_reset(self, heartbeat):
        heartbeat._windows_sent = {"morning", "midday"}
        heartbeat._checkin_date = "2026-03-15"
        heartbeat._reset_daily_if_needed()
        assert heartbeat._windows_sent == set()
        assert heartbeat._checkin_date == datetime.now().strftime("%Y-%m-%d")

    def test_daily_no_reset_same_day(self, heartbeat):
        today = datetime.now().strftime("%Y-%m-%d")
        heartbeat._windows_sent = {"morning"}
        heartbeat._checkin_date = today
        heartbeat._reset_daily_if_needed()
        assert heartbeat._windows_sent == {"morning"}


# ---------------------------------------------------------------------------
# Integration tests (mocked CLI + Telegram)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_cli_success():
    """Mock asyncio.create_subprocess_exec for successful claude -p call."""
    proc = AsyncMock()
    proc.communicate.return_value = (
        json.dumps({"type": "result", "result": "Hey, nice morning! Don't forget your run today.", "is_error": False}).encode(),
        b"",
    )
    proc.returncode = 0
    proc.kill = AsyncMock()
    proc.wait = AsyncMock()
    return proc


@pytest.fixture
def mock_cli_failure():
    """Mock asyncio.create_subprocess_exec for failed claude -p call."""
    proc = AsyncMock()
    proc.communicate.return_value = (b"", b"Error: rate limited")
    proc.returncode = 1
    proc.kill = AsyncMock()
    proc.wait = AsyncMock()
    return proc


@pytest.fixture
def mock_cli_error_json():
    """Mock asyncio.create_subprocess_exec for CLI error in JSON."""
    proc = AsyncMock()
    proc.communicate.return_value = (
        json.dumps({"type": "result", "is_error": True, "subtype": "error_max_turns"}).encode(),
        b"",
    )
    proc.returncode = 0
    proc.kill = AsyncMock()
    proc.wait = AsyncMock()
    return proc


class TestCoachingIntegration:

    @pytest.mark.asyncio
    async def test_full_checkin_cycle(self, heartbeat, mock_cli_success):
        with patch("coaching_heartbeat.asyncio.create_subprocess_exec", return_value=mock_cli_success):
            await heartbeat._full_checkin_cycle("morning")

        heartbeat.send_telegram.assert_called_once()
        msg = heartbeat.send_telegram.call_args[0][0]
        assert "morning" in msg.lower() or "run" in msg.lower() or "nice" in msg.lower()
        assert heartbeat._last_checkin_time is not None
        assert "morning" in heartbeat._windows_sent

    @pytest.mark.asyncio
    async def test_cli_failure_falls_back(self, heartbeat, mock_cli_failure):
        with patch("coaching_heartbeat.asyncio.create_subprocess_exec", return_value=mock_cli_failure):
            await heartbeat._full_checkin_cycle("morning")

        # Should have fallen back to SimpleReminderPolicy
        heartbeat.send_telegram.assert_called_once()
        msg = heartbeat.send_telegram.call_args[0][0]
        assert "Missing morning check-in" in msg

    @pytest.mark.asyncio
    async def test_cli_json_error_falls_back(self, heartbeat, mock_cli_error_json):
        with patch("coaching_heartbeat.asyncio.create_subprocess_exec", return_value=mock_cli_error_json):
            await heartbeat._full_checkin_cycle("morning")

        heartbeat.send_telegram.assert_called_once()
        msg = heartbeat.send_telegram.call_args[0][0]
        assert "Missing morning check-in" in msg

    @pytest.mark.asyncio
    async def test_cli_timeout_falls_back(self, heartbeat):
        proc = AsyncMock()
        proc.communicate.side_effect = asyncio.TimeoutError()
        proc.kill = AsyncMock()
        proc.wait = AsyncMock()

        with patch("coaching_heartbeat.asyncio.create_subprocess_exec", return_value=proc):
            await heartbeat._full_checkin_cycle("morning")

        proc.kill.assert_called_once()
        heartbeat.send_telegram.assert_called_once()

    @pytest.mark.asyncio
    async def test_cli_missing_binary_falls_back(self, heartbeat):
        with patch("coaching_heartbeat.asyncio.create_subprocess_exec", side_effect=FileNotFoundError("claude not found")):
            await heartbeat._full_checkin_cycle("morning")

        heartbeat.send_telegram.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_fallback_skips_silently(self, heartbeat, mock_cli_failure):
        heartbeat.services.reminder_policy.next_actions.return_value = []

        with patch("coaching_heartbeat.asyncio.create_subprocess_exec", return_value=mock_cli_failure):
            await heartbeat._full_checkin_cycle("morning")

        heartbeat.send_telegram.assert_not_called()

    @pytest.mark.asyncio
    async def test_history_injection(self, heartbeat, mock_cli_success):
        history = []
        heartbeat.get_conversation.return_value = MagicMock(
            history=history, save_to_disk=MagicMock()
        )

        with patch("coaching_heartbeat.asyncio.create_subprocess_exec", return_value=mock_cli_success):
            await heartbeat._full_checkin_cycle("morning")

        assert len(history) == 1
        assert history[0]["role"] == "assistant"
        heartbeat.get_conversation.return_value.save_to_disk.assert_called_once_with(12345)


class TestHeartbeatFile:

    def test_update_heartbeat_file(self, heartbeat, tmp_path):
        hb_file = tmp_path / "heartbeat.txt"
        with patch("coaching_heartbeat.HEARTBEAT_FILE", hb_file):
            heartbeat._update_heartbeat_file()
        assert hb_file.exists()
        content = hb_file.read_text()
        assert "timestamp:" in content
        assert "status: ok" in content


class TestAssembleContext:

    def test_includes_metrics(self, heartbeat):
        context = heartbeat._assemble_context("morning")
        assert "Weight: 185" in context
        assert "Sleep: 7.5" in context

    def test_includes_habits(self, heartbeat):
        context = heartbeat._assemble_context("morning")
        assert "yoga" in context
        assert "meditation" in context

    def test_includes_food_summary(self, heartbeat):
        context = heartbeat._assemble_context("morning")
        assert "500 cal" in context
        assert "30g protein" in context

    def test_includes_window_name(self, heartbeat):
        context = heartbeat._assemble_context("evening")
        assert "evening" in context
