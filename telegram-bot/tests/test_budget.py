"""
Tests for daily token budget tracking and model pricing.
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_client import ConversationState, get_model_pricing


class TestRecordUsage:
    """Test record_usage increments both lifetime and daily counters."""

    def test_increments_both(self):
        state = ConversationState()
        state.record_usage(100, 200)

        assert state.total_input_tokens == 100
        assert state.total_output_tokens == 200
        assert state.daily_input_tokens == 100
        assert state.daily_output_tokens == 200

    def test_accumulates_across_calls(self):
        state = ConversationState()
        state.record_usage(100, 200)
        state.record_usage(50, 75)

        assert state.total_input_tokens == 150
        assert state.total_output_tokens == 275
        assert state.daily_input_tokens == 150
        assert state.daily_output_tokens == 275


class TestCheckDailyBudget:
    """Test check_daily_budget enforcement."""

    def test_under_limit_returns_true(self):
        state = ConversationState()
        state.record_usage(100, 100)
        assert state.check_daily_budget() is True

    @patch("claude_client.DAILY_TOKEN_BUDGET", 500)
    def test_over_limit_returns_false(self):
        state = ConversationState()
        state.record_usage(300, 300)
        assert state.check_daily_budget() is False

    @patch("claude_client.DAILY_TOKEN_BUDGET", 500)
    def test_exactly_at_limit_returns_false(self):
        state = ConversationState()
        state.record_usage(250, 250)
        assert state.check_daily_budget() is False

    @patch("claude_client.DAILY_TOKEN_BUDGET", 0)
    def test_zero_budget_means_unlimited(self):
        state = ConversationState()
        state.record_usage(999_999, 999_999)
        assert state.check_daily_budget() is True


class TestDailyReset:
    """Test daily counter reset on date change."""

    def test_resets_on_new_date(self):
        state = ConversationState()
        state.record_usage(500, 500)

        assert state.daily_input_tokens == 500

        tomorrow = date.today() + timedelta(days=1)
        with patch("claude_client.date") as mock_date:
            mock_date.today.return_value = tomorrow
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

            state._reset_daily_if_needed()

        assert state.daily_input_tokens == 0
        assert state.daily_output_tokens == 0
        assert state.daily_token_date == tomorrow.isoformat()

    def test_no_reset_same_date(self):
        state = ConversationState()
        state.record_usage(500, 500)

        state._reset_daily_if_needed()

        assert state.daily_input_tokens == 500
        assert state.daily_output_tokens == 500


class TestGetModelPricing:
    """Test model pricing lookup."""

    @patch("claude_client.MODEL", "claude-haiku-4-5-20251001")
    def test_haiku_pricing(self):
        assert get_model_pricing() == (0.80, 4.00)

    @patch("claude_client.MODEL", "claude-sonnet-4-20250514")
    def test_sonnet_pricing(self):
        assert get_model_pricing() == (3.00, 15.00)

    @patch("claude_client.MODEL", "claude-opus-4-20250514")
    def test_opus_pricing(self):
        assert get_model_pricing() == (15.00, 75.00)

    @patch("claude_client.MODEL", "claude-unknown-99")
    def test_unknown_model_falls_back_to_sonnet(self):
        assert get_model_pricing() == (3.00, 15.00)
