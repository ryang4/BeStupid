#!/usr/bin/env python3
"""
Notify on backup failure - Send Telegram alert if git commit/push fails

Usage:
    python notify_backup_failure.py "error message"
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
            return True
        else:
            print(f"❌ Failed to send message: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False


def notify_failure(error_message: str):
    """Send backup failure notification."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    message = f"🚨 *BACKUP FAILURE ALERT*\n\n"
    message += f"**Time:** {timestamp}\n"
    message += f"**Error:** {error_message}\n\n"
    message += "⚠️ *Changes may not be saved to remote!*\n\n"
    message += "Action required:\n"
    message += "1. Check git status\n"
    message += "2. Manually commit/push if needed\n"
    message += "3. Verify SSH keys or GitHub token\n\n"
    message += "Run: `git status && git push`"

    success = send_telegram_message(message)

    # Always log to file with proper locking
    log_file = PROJECT_ROOT / "logs" / "backup-failures.log"
    log_file.parent.mkdir(exist_ok=True)
    log_entry = f"[{timestamp}] {'TELEGRAM FAILED - ' if not success else ''}{error_message}\n"

    import fcntl
    with open(log_file, "a") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(log_entry)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    if success:
        print("✅ Failure notification sent to Telegram")
    else:
        print("❌ Could not send Telegram notification - logged to file")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python notify_backup_failure.py 'error message'")
        sys.exit(1)

    error_msg = " ".join(sys.argv[1:])
    notify_failure(error_msg)
