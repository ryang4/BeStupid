"""
Heartbeat monitoring system for BeStupid Telegram bot.

Provides:
- Periodic health check messages to owner (hourly by default)
- Startup notification when bot launches
- Activity tracking (last message time)
- Health status for system status tool
- Heartbeat file for external monitoring
"""

import asyncio
import logging
import os
import psutil
from datetime import datetime, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", 0))
PRIVATE_DIR = Path(os.environ.get("HISTORY_DIR", str(Path.home() / ".bestupid-private")))
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
    """Monitor bot health and send periodic heartbeat messages."""

    def __init__(self, interval_minutes: int = 60):
        self.interval_minutes = interval_minutes
        self.start_time = datetime.now()
        self.last_activity = datetime.now()
        self._running = False

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
        """Get comprehensive health status for system status tool."""
        lines = [
            "## Bot Health Status",
            "",
            f"**Uptime:** {self.get_uptime()}",
            f"**Last Activity:** {self.get_time_since_activity()} ago",
            f"**Pending Jobs:** {self.get_pending_jobs_count()}",
            f"**Memory Usage:** {self.get_memory_usage()}",
            f"**Started:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        # Check if activity is stale (>30 minutes)
        minutes_since_activity = (datetime.now() - self.last_activity).total_seconds() / 60
        if minutes_since_activity > 30:
            lines.append("")
            lines.append(f"⚠️ No activity for {self.get_time_since_activity()}")

        return "\n".join(lines)

    def _build_heartbeat_message(self) -> str:
        """Build the heartbeat message content."""
        return f"""🤖 *BeStupid Heartbeat*

*Uptime:* {self.get_uptime()}
*Last activity:* {self.get_time_since_activity()} ago
*Pending jobs:* {self.get_pending_jobs_count()}
*Memory:* {self.get_memory_usage()}"""

    def _build_startup_message(self) -> str:
        """Build the startup notification message."""
        return f"""✅ *BeStupid Bot Started*

Bot is now online and ready.
*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    def _send_telegram(self, text: str) -> bool:
        """Send message via Telegram API."""
        if not TELEGRAM_BOT_TOKEN or not OWNER_CHAT_ID:
            logger.warning("Telegram credentials not configured for heartbeat")
            return False

        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": OWNER_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            return False

    async def send_heartbeat(self) -> bool:
        """Send a heartbeat message to the owner."""
        message = self._build_heartbeat_message()
        return await asyncio.to_thread(self._send_telegram, message)

    async def send_startup_notification(self) -> bool:
        """Send startup notification to the owner."""
        message = self._build_startup_message()
        return await asyncio.to_thread(self._send_telegram, message)

    def update_heartbeat_file(self):
        """Update heartbeat file for external monitoring."""
        try:
            HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
            content = f"""timestamp: {datetime.now().isoformat()}
uptime: {self.get_uptime()}
last_activity: {self.get_time_since_activity()} ago
pending_jobs: {self.get_pending_jobs_count()}
memory: {self.get_memory_usage()}
"""
            # Atomic write
            tmp = HEARTBEAT_FILE.with_suffix(".tmp")
            tmp.write_text(content)
            tmp.rename(HEARTBEAT_FILE)
        except Exception as e:
            logger.error(f"Failed to update heartbeat file: {e}")

    async def run_once(self):
        """Run a single heartbeat cycle."""
        self.update_heartbeat_file()
        await self.send_heartbeat()

    async def run_forever(self):
        """Run the heartbeat loop indefinitely."""
        self._running = True
        logger.info(f"Heartbeat monitor started (interval: {self.interval_minutes}m)")

        # Send startup notification
        await self.send_startup_notification()

        while self._running:
            try:
                await asyncio.sleep(self.interval_minutes * 60)
                self.update_heartbeat_file()
                await self.send_heartbeat()
            except asyncio.CancelledError:
                logger.info("Heartbeat monitor stopped")
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                # Continue running despite errors

    def stop(self):
        """Stop the heartbeat loop."""
        self._running = False


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
    """Get health status from global monitor (for system status tool)."""
    if _heartbeat_monitor:
        return _heartbeat_monitor.get_health_status()
    return "Heartbeat monitor not initialized"
