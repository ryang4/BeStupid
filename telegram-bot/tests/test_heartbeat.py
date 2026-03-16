"""
Tests for the health monitoring system (passive provider for /health).

The HeartbeatMonitor no longer sends messages or runs as an asyncio task.
It tracks uptime, memory, and activity for the /health command.
"""

import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from heartbeat import HeartbeatMonitor, get_health_status, init_heartbeat_monitor


class TestHeartbeatMonitor:
    """Test HeartbeatMonitor passive health tracking."""

    @pytest.fixture
    def monitor(self):
        return HeartbeatMonitor(interval_minutes=60)

    def test_records_activity(self, monitor):
        initial_time = monitor.last_activity
        time.sleep(0.01)
        monitor.record_activity()
        assert monitor.last_activity > initial_time

    def test_calculates_uptime(self, monitor):
        monitor.start_time = datetime.now() - timedelta(hours=1)
        uptime = monitor.get_uptime()
        assert "1h" in uptime or "59m" in uptime or "60m" in uptime

    def test_calculates_time_since_activity(self, monitor):
        monitor.last_activity = datetime.now() - timedelta(minutes=5)
        since = monitor.get_time_since_activity()
        assert "5m" in since or "4m" in since


class TestHealthStatus:
    """Test health status reporting."""

    @pytest.fixture
    def monitor(self):
        m = HeartbeatMonitor(interval_minutes=60)
        m.start_time = datetime.now() - timedelta(hours=2)
        m.last_activity = datetime.now() - timedelta(minutes=10)
        return m

    def test_includes_uptime(self, monitor):
        status = monitor.get_health_status()
        assert "Uptime" in status

    def test_includes_last_activity(self, monitor):
        status = monitor.get_health_status()
        assert "Activity" in status

    def test_includes_pending_jobs(self, monitor):
        with patch.object(monitor, "get_pending_jobs_count", return_value=3):
            status = monitor.get_health_status()
            assert "3" in status

    def test_stale_activity_warning(self, monitor):
        monitor.last_activity = datetime.now() - timedelta(minutes=45)
        status = monitor.get_health_status()
        assert "No activity" in status


class TestGlobalFunctions:
    """Test module-level singleton functions."""

    def test_init_and_get(self):
        monitor = init_heartbeat_monitor(interval_minutes=30)
        assert monitor is not None
        status = get_health_status()
        assert "Uptime" in status
