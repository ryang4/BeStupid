"""
Health monitoring for BeStupid Telegram bot.

Passive health data provider for the /health command.
No longer sends messages or runs as an asyncio task — the CoachingHeartbeat
handles proactive messaging and heartbeat file updates.
"""

import logging
from datetime import datetime, timedelta

try:
    import psutil
except ImportError:
    psutil = None

from config import PRIVATE_DIR

logger = logging.getLogger(__name__)

HEARTBEAT_FILE = PRIVATE_DIR / "heartbeat.txt"


def _format_duration(delta: timedelta) -> str:
    """Format a timedelta as human-readable string."""
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes}m"
    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"


class HeartbeatMonitor:
    """Passive health data provider. Tracks uptime, memory, activity."""

    def __init__(self, interval_minutes: int = 60):
        self.interval_minutes = interval_minutes
        self.start_time = datetime.now()
        self.last_activity = datetime.now()

    def record_activity(self):
        """Record that activity occurred (call on each message)."""
        self.last_activity = datetime.now()

    def get_uptime(self) -> str:
        """Get formatted uptime string."""
        delta = datetime.now() - self.start_time
        return _format_duration(delta)

    def get_time_since_activity(self) -> str:
        """Get formatted time since last activity."""
        delta = datetime.now() - self.last_activity
        return _format_duration(delta)

    def get_memory_usage(self) -> str:
        """Get current memory usage."""
        if psutil is None:
            return "N/A"
        try:
            process = psutil.Process()
            mem = process.memory_info().rss / (1024 * 1024)  # MB
            return f"{mem:.1f}MB"
        except Exception:
            return "N/A"

    def get_pending_jobs_count(self) -> int:
        """Get count of scheduled jobs."""
        try:
            from scheduler import get_next_runs
            return len(get_next_runs())
        except Exception:
            return 0

    def get_health_status(self) -> str:
        """Get comprehensive health status for /health command."""
        lines = [
            "## Bot Health Status",
            "",
            f"**Uptime:** {self.get_uptime()}",
            f"**Last Activity:** {self.get_time_since_activity()} ago",
            f"**Pending Jobs:** {self.get_pending_jobs_count()}",
            f"**Memory Usage:** {self.get_memory_usage()}",
            f"**Started:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        minutes_since_activity = (datetime.now() - self.last_activity).total_seconds() / 60
        if minutes_since_activity > 30:
            lines.append("")
            lines.append(f"No activity for {self.get_time_since_activity()}")

        return "\n".join(lines)


# Global instance for easy access
_heartbeat_monitor: HeartbeatMonitor | None = None


def get_heartbeat_monitor() -> HeartbeatMonitor | None:
    """Get the global heartbeat monitor instance."""
    return _heartbeat_monitor


def init_heartbeat_monitor(interval_minutes: int = 60) -> HeartbeatMonitor:
    """Initialize the global heartbeat monitor."""
    global _heartbeat_monitor
    _heartbeat_monitor = HeartbeatMonitor(interval_minutes=interval_minutes)
    return _heartbeat_monitor


def get_health_status() -> str:
    """Get health status from global monitor (for /health command)."""
    if _heartbeat_monitor:
        return _heartbeat_monitor.get_health_status()
    return "Heartbeat monitor not initialized"
