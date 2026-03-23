"""Tests for the intervention (strategy evaluation) system."""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from v2.app import projection as projection_module
from v2.infra import sqlite_state_store as store_module
from v2.infra.sqlite_state_store import SQLiteStateStore


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


class TestInterventions:
    def test_create_intervention(self, v2_store):
        store, _ = v2_store
        result = store.create_intervention(
            12345, "No screens after 9pm", "Sleep", duration_days=7,
            baseline_value=6.5, baseline_sample_size=5,
        )
        assert result["intervention_id"].startswith("intv_")
        assert result["status"] == "active"
        assert result["target_metric"] == "Sleep"
        assert result["baseline_value"] == 6.5

    def test_evaluate_with_improvement(self, v2_store):
        store, _ = v2_store
        intv = store.create_intervention(12345, "Strategy", "Sleep", baseline_value=6.5)
        result = store.evaluate_intervention(12345, intv["intervention_id"], current_value=7.5)
        assert result["status"] == "evaluated"
        assert result["outcome_delta"] == pytest.approx(1.0)
        assert "improved" in result["outcome_text"]

    def test_evaluate_with_decline(self, v2_store):
        store, _ = v2_store
        intv = store.create_intervention(12345, "Strategy", "Sleep", baseline_value=7.0)
        result = store.evaluate_intervention(12345, intv["intervention_id"], current_value=6.0)
        assert result["outcome_delta"] == pytest.approx(-1.0)
        assert "declined" in result["outcome_text"]

    def test_evaluate_with_no_data(self, v2_store):
        store, _ = v2_store
        intv = store.create_intervention(12345, "Strategy", "Sleep", baseline_value=None)
        result = store.evaluate_intervention(12345, intv["intervention_id"], current_value=None)
        assert result["status"] == "evaluated"
        assert "Insufficient" in result["outcome_text"]

    def test_drop_intervention(self, v2_store):
        store, _ = v2_store
        intv = store.create_intervention(12345, "Strategy", "Sleep", baseline_value=7.0)
        result = store.drop_intervention(12345, intv["intervention_id"], "Not working")
        assert result["status"] == "dropped"

    def test_list_due_evaluations(self, v2_store):
        store, _ = v2_store
        intv = store.create_intervention(12345, "Strategy", "Sleep", duration_days=0, baseline_value=7.0)
        due = store.list_due_evaluations(12345)
        assert len(due) == 1
        assert due[0]["intervention_id"] == intv["intervention_id"]

    def test_list_due_excludes_future(self, v2_store):
        store, _ = v2_store
        store.create_intervention(12345, "Strategy", "Sleep", duration_days=30, baseline_value=7.0)
        due = store.list_due_evaluations(12345)
        assert len(due) == 0

    def test_extend_intervention(self, v2_store):
        store, _ = v2_store
        intv = store.create_intervention(12345, "Strategy", "Sleep", duration_days=7, baseline_value=7.0)
        original_eval = intv["evaluation_date"]
        result = store.extend_intervention(12345, intv["intervention_id"], extra_days=7)
        expected = (date.fromisoformat(original_eval) + timedelta(days=7)).isoformat()
        assert result["evaluation_date"] == expected

    def test_invalid_metric_raises(self, v2_store):
        store, _ = v2_store
        with pytest.raises(ValueError, match="Unsupported metric"):
            store.create_intervention(12345, "Strategy", "InvalidMetric")

    def test_list_interventions_by_status(self, v2_store):
        store, _ = v2_store
        store.create_intervention(12345, "Active one", "Sleep", baseline_value=7.0)
        intv2 = store.create_intervention(12345, "To drop", "Weight", baseline_value=220.0)
        store.drop_intervention(12345, intv2["intervention_id"])

        active = store.list_interventions(12345, status="active")
        assert len(active) == 1
        dropped = store.list_interventions(12345, status="dropped")
        assert len(dropped) == 1

    def test_list_all_interventions(self, v2_store):
        store, _ = v2_store
        store.create_intervention(12345, "One", "Sleep", baseline_value=7.0)
        store.create_intervention(12345, "Two", "Weight", baseline_value=220.0)
        all_intvs = store.list_interventions(12345)
        assert len(all_intvs) == 2

    def test_drop_nonexistent_returns_none(self, v2_store):
        store, _ = v2_store
        result = store.drop_intervention(12345, "intv_nonexistent")
        assert result is None

    def test_extend_nonexistent_returns_none(self, v2_store):
        store, _ = v2_store
        result = store.extend_intervention(12345, "intv_nonexistent")
        assert result is None

    def test_evaluate_already_evaluated_returns_as_is(self, v2_store):
        store, _ = v2_store
        intv = store.create_intervention(12345, "Strategy", "Sleep", baseline_value=7.0)
        store.evaluate_intervention(12345, intv["intervention_id"], current_value=8.0)
        # Second evaluation should return current state (not re-evaluate)
        result = store.evaluate_intervention(12345, intv["intervention_id"], current_value=9.0)
        assert result["status"] == "evaluated"
