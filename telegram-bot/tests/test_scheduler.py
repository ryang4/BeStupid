"""
Tests for the background scheduler.
Verifies job loading, scheduling, and crash isolation.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import importlib

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Skip all tests if schedule module not available
schedule = pytest.importorskip("schedule")


class TestCronScheduleParsing:
    """Test cron schedule to time conversion."""

    def test_parses_daily_schedule(self):
        """Test parsing of daily cron schedules."""
        # Import fresh
        import scheduler
        importlib.reload(scheduler)

        assert scheduler._cron_to_schedule_time("0 7 * * *") == "07:00"
        assert scheduler._cron_to_schedule_time("30 14 * * *") == "14:30"
        assert scheduler._cron_to_schedule_time("0 0 * * *") == "00:00"
        assert scheduler._cron_to_schedule_time("59 23 * * *") == "23:59"

    def test_rejects_non_daily_schedules(self):
        """Test that non-daily schedules are rejected."""
        import scheduler
        importlib.reload(scheduler)

        # Day-of-month specific
        assert scheduler._cron_to_schedule_time("0 7 15 * *") is None
        # Month specific
        assert scheduler._cron_to_schedule_time("0 7 * 6 *") is None
        # Day-of-week specific
        assert scheduler._cron_to_schedule_time("0 7 * * 1") is None

    def test_rejects_invalid_schedules(self):
        """Test rejection of invalid cron expressions."""
        import scheduler
        importlib.reload(scheduler)

        assert scheduler._cron_to_schedule_time("invalid") is None
        assert scheduler._cron_to_schedule_time("0 7 *") is None  # Missing fields
        assert scheduler._cron_to_schedule_time("") is None


class TestSchedulerJobLoading:
    """Test loading jobs from cron_jobs.json."""

    def test_loads_enabled_jobs(self, mock_env, sample_cron_config):
        """Test that enabled jobs are loaded and scheduled."""
        import scheduler
        importlib.reload(scheduler)

        # Patch the config path
        scheduler.CRON_CONFIG = sample_cron_config
        scheduler.PROJECT_ROOT = mock_env["project_root"]

        schedule.clear()
        count = scheduler.load_and_schedule_jobs()

        assert count == 2  # morning_briefing and auto_backup
        assert len(schedule.get_jobs()) == 2

    def test_skips_disabled_jobs(self, mock_env):
        """Test that disabled jobs are not scheduled."""
        import scheduler
        importlib.reload(scheduler)

        config_file = mock_env["private_dir"] / "cron_jobs.json"
        config = {
            "morning_briefing": {"schedule": "0 7 * * *", "enabled": False},
            "auto_backup": {"schedule": "0 8 * * *", "enabled": True},
        }
        config_file.write_text(json.dumps(config))

        scheduler.CRON_CONFIG = config_file
        schedule.clear()
        count = scheduler.load_and_schedule_jobs()

        assert count == 1  # Only auto_backup

    def test_handles_missing_config_file(self, mock_env):
        """Test graceful handling of missing config file."""
        import scheduler
        importlib.reload(scheduler)

        missing_config = mock_env["private_dir"] / "nonexistent.json"
        scheduler.CRON_CONFIG = missing_config

        schedule.clear()
        count = scheduler.load_and_schedule_jobs()

        assert count == 0

    def test_handles_corrupted_config(self, mock_env):
        """Test graceful handling of corrupted config file."""
        import scheduler
        importlib.reload(scheduler)

        config_file = mock_env["private_dir"] / "cron_jobs.json"
        config_file.write_text("{ invalid json }")

        scheduler.CRON_CONFIG = config_file
        schedule.clear()
        count = scheduler.load_and_schedule_jobs()

        assert count == 0  # No jobs loaded from corrupted config


class TestJobExecution:
    """Test job execution behavior."""

    def test_job_runs_subprocess(self, mock_subprocess, mock_env):
        """Test that jobs execute via subprocess."""
        import scheduler
        importlib.reload(scheduler)

        scheduler.PROJECT_ROOT = mock_env["project_root"]
        scheduler._run_job("auto_backup")

        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        assert "auto_backup.sh" in str(call_args)

    def test_unknown_job_logged(self, mock_env):
        """Test that unknown jobs are logged as warnings."""
        import scheduler
        importlib.reload(scheduler)

        with patch.object(scheduler, "logger") as mock_logger:
            scheduler._run_job("nonexistent_job")
            mock_logger.warning.assert_called()


class TestJobCrashIsolation:
    """Test that one job crashing doesn't affect others."""

    def test_failing_job_doesnt_crash_scheduler(self, mock_env):
        """Test that a failing job doesn't stop the scheduler."""
        import scheduler
        importlib.reload(scheduler)

        scheduler.PROJECT_ROOT = mock_env["project_root"]
        with patch("subprocess.run", side_effect=Exception("Job failed")):
            # Should not raise
            scheduler._run_job("auto_backup")

    def test_scheduler_loop_continues_after_error(self):
        """Test that scheduler loop continues after job errors."""
        error_count = [0]

        def failing_job():
            error_count[0] += 1
            raise Exception("Job error")

        schedule.clear()
        schedule.every(0.01).seconds.do(failing_job)

        # Run a few iterations
        for _ in range(3):
            try:
                schedule.run_pending()
            except Exception:
                pass  # Scheduler should catch this
            time.sleep(0.02)

        # Job should have been attempted multiple times
        assert error_count[0] >= 2


class TestSchedulerReload:
    """Test hot-reloading of scheduler jobs."""

    def test_reload_clears_and_reschedules(self, mock_env):
        """Test that reload_jobs clears existing jobs."""
        import scheduler
        importlib.reload(scheduler)

        # Add a dummy job
        schedule.clear()
        schedule.every().day.at("12:00").do(lambda: None)

        config_file = mock_env["private_dir"] / "cron_jobs.json"
        config = {"morning_briefing": {"schedule": "0 8 * * *", "enabled": True}}
        config_file.write_text(json.dumps(config))

        scheduler.CRON_CONFIG = config_file
        count = scheduler.reload_jobs()

        # Should have cleared old jobs and added new
        assert count == 1
        assert len(schedule.get_jobs()) == 1


class TestNextRunTimes:
    """Test getting next run times for scheduled jobs."""

    def test_get_next_runs_returns_times(self, mock_env, sample_cron_config):
        """Test that get_next_runs returns formatted times."""
        import scheduler
        importlib.reload(scheduler)

        scheduler.CRON_CONFIG = sample_cron_config
        schedule.clear()

        scheduler.load_and_schedule_jobs()
        next_runs = scheduler.get_next_runs()

        assert "morning_briefing" in next_runs
        assert "auto_backup" in next_runs
        # Should be formatted as datetime string
        for name, time_str in next_runs.items():
            assert "-" in time_str  # Date format check
            assert ":" in time_str  # Time format check
