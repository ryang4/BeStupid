"""Tests for migrate_all_to_sqlite.py — data migration idempotency and integrity."""

import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


def _make_test_data(tmp_path):
    """Create test JSON data and directory structure."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    private_dir = tmp_path / "private"
    private_dir.mkdir(exist_ok=True)
    (tmp_path / "content" / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory").mkdir(exist_ok=True)

    test_entries = {
        "version": "1.0",
        "entries": [
            {
                "date": "2026-01-15",
                "sleep": {"hours": 7.5, "quality": 85},
                "weight_lbs": 245.0,
                "mood": {"morning": 7, "bedtime": 6},
                "training": {
                    "workout_type": "strength",
                    "activities": [{"type": "run", "distance": 3.0, "duration_minutes": 30, "avg_hr": 140}],
                    "strength_exercises": [{"exercise": "bench press", "sets": 3, "reps": 8, "weight_lbs": 135}],
                },
                "nutrition": {
                    "calories": 2500, "protein_g": 150, "carbs_g": 300, "fat_g": 80,
                    "line_items": [
                        {"food": "eggs and toast", "time": "8am", "calories": 400, "protein_g": 25, "carbs_g": 30, "fat_g": 20},
                        {"food": "chicken salad", "time": "12pm", "calories": 600, "protein_g": 45, "carbs_g": 20, "fat_g": 15},
                    ],
                },
                "habits": {"completed": ["yoga", "meditation"], "missed": ["writing"], "completion_rate": 0.67},
            },
        ],
    }
    (data_dir / "daily_metrics.json").write_text(json.dumps(test_entries))

    history = {
        "12345": {
            "history": [
                {"role": "user", "content": "Hello migration test"},
                {"role": "assistant", "content": "Hi from migration test!"},
            ],
        },
    }
    (private_dir / "conversation_history.json").write_text(json.dumps(history))

    return data_dir, private_dir


def _run_migration(data_dir, private_dir, db_path, dry_run=False):
    """Run the migration script against a specific DB path."""
    import migrate_all_to_sqlite as mig
    from v2.infra.sqlite_state_store import SQLiteStateStore

    store = SQLiteStateStore(db_path=db_path)
    store.init_schema()

    mig.METRICS_FILE = data_dir / "daily_metrics.json"
    mig.HISTORY_FILE = private_dir / "conversation_history.json"

    # The migration script internally does SQLiteStateStore() — we need it to
    # use our db_path. Patch DEFAULT_DB_PATH at the module level.
    import v2.infra.sqlite_state_store as store_mod
    orig_default = store_mod.DEFAULT_DB_PATH
    store_mod.DEFAULT_DB_PATH = db_path
    try:
        mig.migrate(dry_run=dry_run)
    finally:
        store_mod.DEFAULT_DB_PATH = orig_default

    return store


class TestMigrationIdempotency:
    def test_first_run_migrates_data(self, tmp_path):
        data_dir, private_dir = _make_test_data(tmp_path)
        db_path = tmp_path / "test_state.db"

        with patch.dict(os.environ, {"OWNER_CHAT_ID": "12345"}):
            store = _run_migration(data_dir, private_dir, db_path)

        conn = store._connect()
        assert conn.execute("SELECT COUNT(*) FROM day_context").fetchone()[0] >= 1
        assert conn.execute("SELECT COUNT(*) FROM workout_session").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM exercise_log").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM cardio_activity").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM food_entry WHERE calories_est IS NOT NULL").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM habit_instance").fetchone()[0] >= 3
        assert conn.execute("SELECT COUNT(*) FROM turn").fetchone()[0] == 2
        conn.close()

    def test_second_run_is_idempotent(self, tmp_path):
        data_dir, private_dir = _make_test_data(tmp_path)
        db_path = tmp_path / "test_state.db"

        with patch.dict(os.environ, {"OWNER_CHAT_ID": "12345"}):
            store = _run_migration(data_dir, private_dir, db_path)
            _run_migration(data_dir, private_dir, db_path)

        conn = store._connect()
        assert conn.execute("SELECT COUNT(*) FROM day_context WHERE local_date = '2026-01-15'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM turn WHERE text = 'Hello migration test'").fetchone()[0] == 1
        conn.close()

    def test_dry_run_changes_nothing(self, tmp_path):
        data_dir, private_dir = _make_test_data(tmp_path)
        db_path = tmp_path / "test_state.db"

        with patch.dict(os.environ, {"OWNER_CHAT_ID": "12345"}):
            store = _run_migration(data_dir, private_dir, db_path, dry_run=True)

        conn = store._connect()
        assert conn.execute("SELECT COUNT(*) FROM day_context").fetchone()[0] == 0
        conn.close()
