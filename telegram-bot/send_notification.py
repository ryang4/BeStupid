#!/usr/bin/env python3
"""
Proactive Telegram notification sender.

Sends morning briefings and evening reminders to Ryan's Telegram.

Usage:
    python send_notification.py morning   # Send morning briefing
    python send_notification.py evening   # Send evening reminder
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Load environment
load_dotenv(Path(__file__).parent / ".env")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", 0))


def send_telegram_message(text: str, parse_mode: str = "Markdown") -> bool:
    """
    Send a message to OWNER_CHAT_ID via Telegram Bot API.

    Args:
        text: Message text (supports Markdown)
        parse_mode: Telegram parse mode (default: Markdown)

    Returns:
        True if successful, False otherwise
    """
    try:
        import requests

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": OWNER_CHAT_ID,
            "text": text,
            "parse_mode": parse_mode
        }

        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            print(f"✅ Message sent successfully to chat {OWNER_CHAT_ID}")
            return True
        else:
            print(f"❌ Failed to send message: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False


def send_morning_briefing() -> str:
    """
    Generate and send morning briefing.

    Returns status message.
    """
    try:
        from brain import get_morning_briefing_data

        data = get_morning_briefing_data()

        # Build message
        lines = []
        lines.append("☀️ *Good morning, Ryan!*\n")

        # Recovery section
        recovery = data.get("recovery", {})
        if recovery.get("score"):
            lines.append(f"💪 *Recovery:* {recovery['score']}/100 ({recovery['status']})")
            if recovery.get("sleep_hours"):
                sleep_score = f" (score: {recovery['sleep_score']})" if recovery.get("sleep_score") else ""
                lines.append(f"Sleep: {recovery['sleep_hours']:.1f}h{sleep_score}")
            if recovery.get("hrv"):
                lines.append(f"HRV: {recovery['hrv']} ({recovery.get('hrv_status', 'N/A')})")
            lines.append(f"→ {recovery['recommendation']}")
        else:
            lines.append("💪 *Recovery:* No data synced")

        lines.append("")

        # Schedule section
        schedule = data.get("schedule", {})
        lines.append(f"📅 *Today's Schedule:*")

        events = schedule.get("events_count", 0)
        if events > 0:
            lines.append(f"Events today: {events}")

            if schedule.get("next_event"):
                lines.append(f"Next: {schedule['next_event']}")

            deep_work = schedule.get("deep_work_blocks", [])
            if deep_work:
                lines.append(f"Deep work: {deep_work[0]}")
            else:
                lines.append("⚠️ No deep work blocks available")
        else:
            lines.append("No events scheduled")

        lines.append("")

        # Priorities section
        priorities = data.get("priorities", [])
        if priorities:
            lines.append("⚡ *Top 3 Priorities:*")
            for i, priority in enumerate(priorities, 1):
                lines.append(f"{i}. {priority}")
        else:
            lines.append("⚡ *Top 3 Priorities:*")
            lines.append("1. Fill out today's log")
            lines.append("2. Review your brain dashboard")
            lines.append("3. Check calendar for today")

        lines.append("")

        # Workout section
        workout = data.get("workout", "No workout planned")
        lines.append(f"🏋️ *Workout:* {workout}")

        message = "\n".join(lines)

        success = send_telegram_message(message)

        if success:
            return "Morning briefing sent ✅"
        else:
            return "Failed to send morning briefing ❌"

    except Exception as e:
        error_msg = f"Error generating morning briefing: {e}"
        print(error_msg)
        return error_msg


def send_evening_reminder() -> str:
    """
    Generate and send evening reflection reminder.

    Returns status message.
    """
    try:
        from brain import get_evening_reflection_data

        data = get_evening_reflection_data()

        # Build message
        lines = []
        lines.append("🌙 *Evening Reflection*\n")

        # Progress section
        completion = data.get("completion", {})
        if completion.get("total", 0) > 0:
            completed = completion["completed"]
            total = completion["total"]
            rate = int(completion["rate"] * 100)

            lines.append("📊 *Today's Progress:*")
            lines.append(f"✅ Todos: {completed}/{total} completed ({rate}%)")
        else:
            lines.append("📊 *Today's Progress:*")
            lines.append("No todos tracked today")

        # Metrics section
        filled = data.get("metrics_filled", [])
        missing = data.get("metrics_missing", [])

        if filled:
            lines.append(f"✅ Metrics filled: {', '.join(filled)}")

        if missing:
            lines.append(f"❌ Missing: {', '.join(missing)}")

        lines.append("")

        # Tomorrow preview
        tomorrow = data.get("tomorrow_preview", "Check /brain for tomorrow")
        lines.append("📅 *Tomorrow Preview:*")
        lines.append(tomorrow)

        lines.append("")

        # Reminder
        lines.append("📝 *Before bed:*")
        if missing:
            for metric in missing[:3]:
                lines.append(f"- Fill out {metric}")
        lines.append("- Set tomorrow's top 3 priorities")

        lines.append("\nSleep well! 😴")

        message = "\n".join(lines)

        success = send_telegram_message(message)

        if success:
            return "Evening reminder sent ✅"
        else:
            return "Failed to send evening reminder ❌"

    except Exception as e:
        error_msg = f"Error generating evening reminder: {e}"
        print(error_msg)
        return error_msg


def main():
    """CLI interface."""
    if not TELEGRAM_BOT_TOKEN or not OWNER_CHAT_ID:
        print("❌ Error: TELEGRAM_BOT_TOKEN and OWNER_CHAT_ID must be set in .env")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python send_notification.py <morning|evening>")
        sys.exit(1)

    command = sys.argv[1].lower()

    print(f"📤 Sending {command} notification...")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if command == "morning":
        result = send_morning_briefing()
        print(result)
    elif command == "evening":
        result = send_evening_reminder()
        print(result)
    else:
        print(f"❌ Unknown command: {command}")
        print("Valid commands: morning, evening")
        sys.exit(1)


if __name__ == "__main__":
    main()
