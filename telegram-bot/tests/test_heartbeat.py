"""
Tests for the heartbeat monitoring system.
Verifies health checks, startup notifications, and activity tracking.
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestHeartbeatMonitor:
    """Test HeartbeatMonitor class."""

    @pytest.fixture
    def heartbeat_monitor(self, mock_env):
        """Create a HeartbeatMonitor instance for testing."""
        with patch("heartbeat.OWNER_CHAT_ID", 12345):
            with patch("heartbeat.TELEGRAM_BOT_TOKEN", "test-token"):
                from heartbeat import HeartbeatMonitor
                return HeartbeatMonitor(interval_minutes=60)

    def test_records_activity(self, heartbeat_monitor):
        """Test that record_activity updates last_activity."""
        initial_time = heartbeat_monitor.last_activity

        time.sleep(0.01)  # Small delay
        heartbeat_monitor.record_activity()

        assert heartbeat_monitor.last_activity > initial_time

    def test_calculates_uptime(self, heartbeat_monitor):
        """Test uptime calculation."""
        # Set start time to 1 hour ago
        heartbeat_monitor.start_time = datetime.now() - timedelta(hours=1)

        uptime = heartbeat_monitor.get_uptime()

        assert "1h" in uptime or "59m" in uptime or "60m" in uptime

    def test_calculates_time_since_activity(self, heartbeat_monitor):
        """Test time since last activity calculation."""
        # Set last activity to 5 minutes ago
        heartbeat_monitor.last_activity = datetime.now() - timedelta(minutes=5)

        since = heartbeat_monitor.get_time_since_activity()

        assert "5m" in since or "4m" in since


class TestHealthStatus:
    """Test health status reporting."""

    @pytest.fixture
    def mock_heartbeat(self, mock_env):
        """Create a mocked HeartbeatMonitor."""
        with patch("heartbeat.OWNER_CHAT_ID", 12345):
            with patch("heartbeat.TELEGRAM_BOT_TOKEN", "test-token"):
                from heartbeat import HeartbeatMonitor
                monitor = HeartbeatMonitor(interval_minutes=60)
                monitor.start_time = datetime.now() - timedelta(hours=2)
                monitor.last_activity = datetime.now() - timedelta(minutes=10)
                return monitor

    def test_get_health_status_includes_uptime(self, mock_heartbeat):
        """Test that health status includes uptime."""
        status = mock_heartbeat.get_health_status()

        assert "uptime" in status.lower() or "Uptime" in status

    def test_get_health_status_includes_last_activity(self, mock_heartbeat):
        """Test that health status includes last activity time."""
        status = mock_heartbeat.get_health_status()

        assert "activity" in status.lower() or "Activity" in status

    def test_get_health_status_includes_pending_jobs(self, mock_heartbeat, mock_env):
        """Test that health status includes pending job count."""
        with patch("heartbeat.HeartbeatMonitor.get_pending_jobs_count", return_value=1):
            status = mock_heartbeat.get_health_status()

            # Should mention jobs or pending
            assert "job" in status.lower() or "pending" in status.lower() or "1" in status


class TestHeartbeatMessages:
    """Test heartbeat message sending."""

    @pytest.mark.asyncio
    async def test_send_heartbeat_message(self, mock_env):
        """Test sending heartbeat message to Telegram."""
        with patch("heartbeat.OWNER_CHAT_ID", 12345):
            with patch("heartbeat.TELEGRAM_BOT_TOKEN", "test-token"):
                with patch("heartbeat.requests") as mock_requests:
                    mock_requests.post.return_value = MagicMock(status_code=200)

                    from heartbeat import HeartbeatMonitor
                    monitor = HeartbeatMonitor(interval_minutes=60)

                    result = await monitor.send_heartbeat()

                    assert result is True
                    mock_requests.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_startup_notification(self, mock_env):
        """Test sending startup notification."""
        with patch("heartbeat.OWNER_CHAT_ID", 12345):
            with patch("heartbeat.TELEGRAM_BOT_TOKEN", "test-token"):
                with patch("heartbeat.requests") as mock_requests:
                    mock_requests.post.return_value = MagicMock(status_code=200)

                    from heartbeat import HeartbeatMonitor
                    monitor = HeartbeatMonitor(interval_minutes=60)

                    result = await monitor.send_startup_notification()

                    assert result is True
                    # Check that message contains startup info
                    call_args = mock_requests.post.call_args
                    assert "start" in str(call_args).lower() or "online" in str(call_args).lower()


class TestHeartbeatFile:
    """Test heartbeat file for external monitoring."""

    def test_heartbeat_file_updated(self, mock_env):
        """Test that heartbeat file is updated regularly."""
        heartbeat_file = mock_env["private_dir"] / "heartbeat.txt"

        with patch("heartbeat.HEARTBEAT_FILE", heartbeat_file):
            with patch("heartbeat.OWNER_CHAT_ID", 12345):
                with patch("heartbeat.TELEGRAM_BOT_TOKEN", "test-token"):
                    from heartbeat import HeartbeatMonitor
                    monitor = HeartbeatMonitor(interval_minutes=60)

                    monitor.update_heartbeat_file()

                    assert heartbeat_file.exists()
                    content = heartbeat_file.read_text()
                    # Should contain timestamp
                    assert "202" in content  # Year check

    def test_heartbeat_file_contains_status(self, mock_env):
        """Test that heartbeat file contains health status."""
        heartbeat_file = mock_env["private_dir"] / "heartbeat.txt"

        with patch("heartbeat.HEARTBEAT_FILE", heartbeat_file):
            with patch("heartbeat.OWNER_CHAT_ID", 12345):
                with patch("heartbeat.TELEGRAM_BOT_TOKEN", "test-token"):
                    from heartbeat import HeartbeatMonitor
                    monitor = HeartbeatMonitor(interval_minutes=60)

                    monitor.update_heartbeat_file()

                    content = heartbeat_file.read_text()
                    # Should contain some status info
                    assert len(content) > 10


class TestHeartbeatIntegration:
    """Test heartbeat integration with bot."""

    @pytest.mark.asyncio
    async def test_heartbeat_background_task(self, mock_env):
        """Test that heartbeat runs as background task."""
        with patch("heartbeat.OWNER_CHAT_ID", 12345):
            with patch("heartbeat.TELEGRAM_BOT_TOKEN", "test-token"):
                with patch("heartbeat.requests") as mock_requests:
                    mock_requests.post.return_value = MagicMock(status_code=200)

                    from heartbeat import HeartbeatMonitor
                    monitor = HeartbeatMonitor(interval_minutes=1)  # 1 minute for testing

                    # Start the background task
                    task = asyncio.create_task(monitor.run_once())
                    await asyncio.wait_for(task, timeout=2.0)

                    # Should have sent at least one heartbeat
                    assert mock_requests.post.called
