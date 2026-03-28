#!/usr/bin/env python3
"""
Send routine reminders via Telegram.

Reads custom message overrides from .bestupid-private/cron_jobs.json (set via
the manage_cron tool's set_message action). Falls back to hardcoded defaults.
"""
import json
import os
import sys
import requests
from pathlib import Path
from datetime import datetime

# Try to load telegram bot environment
telegram_dir = Path(__file__).parent.parent / "telegram-bot"
env_file = telegram_dir / ".env"

TELEGRAM_TOKEN = ""
OWNER_CHAT_ID = 0

if env_file.exists():
    # Simple .env parsing
    with open(env_file) as f:
        for line in f:
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                TELEGRAM_TOKEN = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("OWNER_CHAT_ID="):
                OWNER_CHAT_ID = int(line.split("=", 1)[1].strip())

# Also check environment variables (Docker)
if not TELEGRAM_TOKEN:
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not OWNER_CHAT_ID:
    OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", "0") or 0)


def send_telegram_message(text: str):
    """Send a message via Telegram with Markdown retry fallback."""
    if not TELEGRAM_TOKEN or not OWNER_CHAT_ID:
        print("ERROR: Telegram credentials not configured")
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(url, json={
            "chat_id": OWNER_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        }, timeout=10)

        if response.status_code != 200:
            # Retry without Markdown — user content may break Telegram parser
            response = requests.post(url, json={
                "chat_id": OWNER_CHAT_ID,
                "text": text,
            }, timeout=10)

        if response.status_code == 200:
            print("Reminder sent successfully")
            return True
        else:
            print(f"Failed to send reminder: {response.status_code}")
            return False

    except requests.RequestException as e:
        print(f"Error sending reminder: {e}")
        return False


# --- Custom message loading from cron_jobs.json ---

# Map reminder types to cron job names
_TYPE_TO_JOB = {
    "morning": "morning_briefing",
    "evening_start": "evening_reminder",
    "evening_screens": "evening_screens",
    "evening_bed": "evening_bed",
}


def _load_custom_message(reminder_type: str) -> str | None:
    """Load custom message override from cron config, or None for default."""
    job_name = _TYPE_TO_JOB.get(reminder_type)
    if not job_name:
        return None
    try:
        # Check HISTORY_DIR env (Docker), then relative path (local)
        history_dir = os.environ.get("HISTORY_DIR")
        if history_dir:
            config_file = Path(history_dir) / "cron_jobs.json"
        else:
            config_file = Path(__file__).parent.parent / ".bestupid-private" / "cron_jobs.json"
        if not config_file.exists():
            return None
        data = json.loads(config_file.read_text())
        msg = data.get(job_name, {}).get("message")
        return msg if isinstance(msg, str) else None
    except (json.JSONDecodeError, OSError):
        return None


# --- Default messages (fallbacks) ---

_DEFAULT_MORNING = """🌅 **MORNING ROUTINE TIME!**

⏰ **Next 30 minutes = Phone-free productivity**

**Your morning sequence:**
1. 💧 Hydrate - drink water
2. 📅 **Review yesterday's reflection** - what did you plan for today?
3. 🎯 **Confirm today's #1 priority** - does it still make sense?
4. 🏃‍♂️ 5-10 min movement/stretch
5. 🍳 Planned breakfast
6. 💪 25-min work block on #1 priority

**Daily habit check:** AI automation + 10 min yoga

**Remember:** Phone stays off until routine complete!"""

_DEFAULT_EVENING_START = """🌙 **EVENING ROUTINE - STARTING NOW**

⏰ **10:00 PM - Time to wind down**

**Next step:**
📱 Put phone on Do Not Disturb

**Coming up:**
- 10:15 PM - Close all screens
- 10:30 PM - Day review + tomorrow's planning
- 11:00 PM - Personal routine
- 11:30 PM - In bed, lights off

Setting you up for success! 💪"""

_DEFAULT_EVENING_SCREENS = """💻 **SCREENS OFF TIME!**

⏰ **10:15 PM - Close all devices**

**Shut down now:**
- Laptop closed
- TV off
- iPad put away

**Next at 10:30 PM - Day Review & Tomorrow Planning:**
📊 **Today's reflection:**
- Did I ship something today?
- Did I complete my daily habits?
- What worked well? What didn't?

📅 **Tomorrow's setup:**
- What's the #1 priority?
- What time blocks do I need?
- Any schedule conflicts to prep for?

Your brain needs this transition time! 🧠"""

_DEFAULT_EVENING_BED = """🛏️ **BEDTIME ROUTINE - FINAL CALL**

⏰ **11:30 PM - In bed, lights off**

Time for lights off!

**Final check:**
- Tomorrow's #1 priority written down?
- Daily habits reminder set?
- Schedule conflicts identified?
- Personal hygiene done?
- Phone charging outside bedroom?

**Lights off now = successful day!** 🌙"""


def get_morning_reminder():
    """Get morning routine reminder (custom or default)."""
    return _load_custom_message("morning") or _DEFAULT_MORNING

def get_evening_start_reminder():
    """Get evening routine start reminder (custom or default)."""
    return _load_custom_message("evening_start") or _DEFAULT_EVENING_START

def get_evening_screens_reminder():
    """Get screens off reminder (custom or default)."""
    return _load_custom_message("evening_screens") or _DEFAULT_EVENING_SCREENS

def get_evening_bed_reminder():
    """Get bedtime reminder (custom or default)."""
    return _load_custom_message("evening_bed") or _DEFAULT_EVENING_BED


def main():
    if len(sys.argv) < 2:
        print("Usage: python send_routine_reminder.py <reminder_type>")
        print("Types: morning, evening_start, evening_screens, evening_bed")
        sys.exit(1)

    reminder_type = sys.argv[1]

    if reminder_type == "morning":
        message = get_morning_reminder()
    elif reminder_type == "evening_start":
        message = get_evening_start_reminder()
    elif reminder_type == "evening_screens":
        message = get_evening_screens_reminder()
    elif reminder_type == "evening_bed":
        message = get_evening_bed_reminder()
    else:
        print(f"Unknown reminder type: {reminder_type}")
        sys.exit(1)

    success = send_telegram_message(message)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
