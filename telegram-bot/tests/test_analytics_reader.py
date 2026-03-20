"""Tests for v2.infra.analytics_reader — analytical query methods."""

import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def analytics_store(tmp_path):
    """Create a SQLiteStateStore with test data for analytics."""
    db_path = tmp_path / "test_state.db"
    with patch.dict(os.environ, {"HISTORY_DIR": str(tmp_path), "PROJECT_ROOT": str(tmp_path)}):
        from v2.infra.sqlite_state_store import SQLiteStateStore
        store = SQLiteStateStore(db_path=db_path)
        store.init_schema()

        conn = store._connect()
        conn.execute("BEGIN IMMEDIATE")

        # Create 10 days of test data
        for i in range(10):
            day_id = f"day_{i:02d}"
            local_date = f"2026-03-{10 + i:02d}"
            conn.execute(
                "INSERT INTO day_context (day_id, chat_id, local_date, timezone, status, opened_at_utc) VALUES (?, 1, ?, 'UTC', 'closed', '2026-03-10T00:00:00+00:00')",
                (day_id, local_date),
            )
            # Weight trending down
            conn.execute(
                "INSERT INTO day_metric (day_id, field, value) VALUES (?, 'Weight', ?)",
                (day_id, str(250 - i)),
            )
            # Sleep between 6 and 8
            conn.execute(
                "INSERT INTO day_metric (day_id, field, value) VALUES (?, 'Sleep', ?)",
                (day_id, str(6 + (i % 3))),
            )
            # Mood_AM between 5 and 8
            conn.execute(
                "INSERT INTO day_metric (day_id, field, value) VALUES (?, 'Mood_AM', ?)",
                (day_id, str(5 + (i % 4))),
            )

        # Add habit data
        conn.execute("INSERT INTO habit_definition (habit_id, chat_id, name, cadence, active) VALUES ('yoga', 1, 'yoga', 'daily', 1)")
        for i in range(10):
            day_id = f"day_{i:02d}"
            status = "done" if i % 2 == 0 else "pending"
            conn.execute(
                "INSERT INTO habit_instance (instance_id, habit_id, day_id, status, last_changed_at_utc) VALUES (?, 'yoga', ?, ?, '2026-03-10T00:00:00+00:00')",
                (f"hi_{i}", day_id, status),
            )

        # Add food entries with macros
        for i in range(5):
            day_id = f"day_{i:02d}"
            conn.execute(
                "INSERT INTO food_entry (food_id, day_id, description, logged_at_utc, calories_est, protein_g_est, carbs_g_est, fat_g_est, fiber_g_est) VALUES (?, ?, 'test food', '2026-03-10T12:00:00', 500, 30, 50, 20, 5)",
                (f"food_{i}", day_id),
            )

        conn.commit()
        conn.close()

        return store


@pytest.fixture
def reader(analytics_store):
    from v2.infra.analytics_reader import AnalyticsReader
    return AnalyticsReader(analytics_store)


class TestRunQuery:
    def test_select_query(self, reader):
        result = reader.run_query("state", "SELECT COUNT(*) AS cnt FROM day_context")
        assert "error" not in result
        assert result["rows"][0]["cnt"] == 10

    def test_write_blocked(self, reader):
        result = reader.run_query("state", "INSERT INTO day_context (day_id) VALUES ('hack')")
        assert "error" in result

    def test_attach_blocked(self, reader):
        result = reader.run_query("state", "ATTACH DATABASE '/tmp/evil.db' AS evil")
        assert "error" in result

    def test_unknown_db(self, reader):
        result = reader.run_query("nonexistent", "SELECT 1")
        assert "error" in result

    def test_pragma_table_info_allowed(self, reader):
        result = reader.run_query("state", "PRAGMA table_info(day_context)")
        assert "error" not in result
        assert len(result["rows"]) > 0

    def test_row_limit(self, reader):
        # Should not exceed 200 rows
        result = reader.run_query("state", "SELECT * FROM day_metric")
        assert len(result["rows"]) <= 200


class TestMetricTrend:
    def test_weight_trend(self, reader):
        result = reader.metric_trend(1, "Weight", days=30)
        assert result["sample_size"] == 10
        assert result["direction"] == "decreasing"  # Weight going down
        assert "provenance" in result

    def test_missing_field(self, reader):
        result = reader.metric_trend(1, "Focus", days=30)
        assert result["sample_size"] == 0

    def test_provenance_included(self, reader):
        result = reader.metric_trend(1, "Weight", days=30)
        prov = result["provenance"]
        assert prov["source_table"] == "day_metric JOIN day_context"
        assert prov["sample_size"] == 10


class TestHabitCompletion:
    def test_yoga_completion(self, reader):
        result = reader.habit_completion(1, "yoga", days=30)
        assert result["completion_rate"] == 0.5  # Every other day
        assert result["total_days"] == 10

    def test_unknown_habit(self, reader):
        result = reader.habit_completion(1, "nonexistent", days=30)
        assert "error" in result


class TestNutritionSummary:
    def test_multi_day_summary(self, reader):
        result = reader.nutrition_summary(1, days=30)
        assert result["days_with_data"] == 5

    def test_single_day(self, reader):
        result = reader.nutrition_summary(1, date="2026-03-10")
        assert len(result["daily"]) == 1
        assert result["daily"][0]["calories"] == 500


class TestCorrelate:
    def test_sleep_mood(self, reader):
        result = reader.correlate(1, "Sleep", "Mood_AM", days=30)
        assert result["paired_data_points"] == 10
        assert result["pearson_r"] is not None
        assert "provenance" in result

    def test_insufficient_data(self, reader):
        result = reader.correlate(1, "Weight", "Focus", days=30)
        assert "error" in result


class TestGetComputedInsights:
    def test_returns_insights(self, reader):
        result = reader.get_computed_insights(1)
        assert "insights" in result
        assert "provenance" in result
        # Should have at least weight_trend and tdee_estimate entries
        types = [i["type"] for i in result["insights"]]
        assert "weight_trend" in types
