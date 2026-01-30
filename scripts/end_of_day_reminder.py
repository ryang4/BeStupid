#!/usr/bin/env python3
"""
End of Day Reminder - Prompts user to fill in daily log data

Sends a Telegram reminder to complete:
- Quick Log (weight, sleep, mood, energy, focus)
- Training Output
- Fuel Log totals
- Top 3 for Tomorrow

Usage:
    python end_of_day_reminder.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent
TELEGRAM_BOT_DIR = PROJECT_ROOT / "telegram-bot"
sys.path.insert(0, str(TELEGRAM_BOT_DIR))

# Load environment
load_dotenv(TELEGRAM_BOT_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", 0))


def send_telegram_message(text: str, parse_mode: str = "Markdown") -> bool:
    """Send a message to OWNER_CHAT_ID via Telegram Bot API."""
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
            print(f"✅ Message sent successfully")
            return True
        else:
            print(f"❌ Failed to send message: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False


def get_today_log_path() -> Path:
    """Get path to today's log file."""
    today = datetime.now().strftime("%Y-%m-%d")
    return PROJECT_ROOT / "content" / "logs" / f"{today}.md"


def check_missing_data() -> dict:
    """Check what data is missing from today's log."""
    log_path = get_today_log_path()

    if not log_path.exists():
        return {"all": True}

    content = log_path.read_text()
    missing = []

    # Check Quick Log fields
    quick_log_fields = ["Weight::", "Sleep::", "Sleep_Quality::", "Mood_AM::", "Mood_PM::", "Energy::", "Focus::"]
    for field in quick_log_fields:
        if field in content:
            # Check if it has a value (not just ::)
            line = [l for l in content.split("\n") if field in l][0]
            value = line.split("::")[1].strip() if "::" in line else ""
            if not value:
                missing.append(field.replace("::", "").replace("_", " "))

    # Check Fuel Log
    if "calories_so_far:: 0" in content or "protein_so_far:: 0" in content:
        missing.append("Fuel Log totals")

    # Check Top 3 for Tomorrow
    top_3_section = content.split("## Top 3 for Tomorrow")
    if len(top_3_section) > 1:
        top_3_content = top_3_section[1]
        # Check if any of the 3 items have content
        if "1.\n" in top_3_content or top_3_content.count("1.") == 0:
            missing.append("Top 3 for Tomorrow")

    return {"missing": missing}


def main():
    """Send end of day reminder."""
    missing_data = check_missing_data()

    if missing_data.get("all"):
        message = "📝 *End of Day Reminder*\n\n"
        message += "Time to fill in your daily log!\n\n"
        message += "Don't forget to log:\n"
        message += "• Quick Log (weight, sleep, mood, energy, focus)\n"
        message += "• Training Output\n"
        message += "• Fuel Log totals\n"
        message += "• Top 3 for Tomorrow\n\n"
        message += "Close the loop on today! 💪"
    elif missing_data.get("missing"):
        message = "📝 *End of Day Reminder*\n\n"
        message += "You're missing some data in today's log:\n\n"
        for item in missing_data["missing"]:
            message += f"• {item}\n"
        message += "\nComplete your log before bed! 💪"
    else:
        message = "✅ *Daily Log Complete!*\n\n"
        message += "Nice work logging everything today. Sleep well! 😴"

    success = send_telegram_message(message)

    if success:
        print("End of day reminder sent!")
    else:
        print("Failed to send reminder")
        sys.exit(1)


if __name__ == "__main__":
    main()
