#!/usr/bin/env python3
"""
Daily Check-in System - Throughout-the-day automation

Sends periodic check-ins via Telegram to track:
- Energy and focus levels
- Meal logging and nutrition
- Hydration and movement
- Sleep preparation

Usage:
    python daily_checkins.py mid-morning   # 10am energy check
    python daily_checkins.py lunch         # 12pm meal log
    python daily_checkins.py mid-afternoon # 3pm movement reminder
    python daily_checkins.py dinner        # 6pm meal log + daily total
    python daily_checkins.py pre-bed       # 10pm sleep prep
"""

import os
import sys
import re
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


def parse_approx_int(value: str) -> int:
    """Parse values like '~2800', '160g', or '3500-4000' into an int."""
    if value is None:
        return 0

    text = str(value).strip().lower().replace(",", "")
    if text in ("", "none", "null", "n/a", "na", "missed", "-"):
        return 0

    range_match = re.search(r'(-?\d+(?:\.\d+)?)\s*[-–]\s*(-?\d+(?:\.\d+)?)', text)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return int(round((low + high) / 2))

    number_match = re.search(r'-?\d+(?:\.\d+)?', text)
    if not number_match:
        return 0

    return int(round(float(number_match.group(0))))


def read_inline_total(content: str, field_name: str) -> int:
    """Read a single inline total from the log content."""
    match = re.search(rf'^{re.escape(field_name)}::\s*(.+)$', content, flags=re.MULTILINE)
    if not match:
        return 0
    return parse_approx_int(match.group(1))


def read_log_metrics() -> dict:
    """Read current metrics from today's log."""
    log_path = get_today_log_path()

    if not log_path.exists():
        return {}

    content = log_path.read_text()
    metrics = {}

    # Parse fuel totals
    metrics["calories"] = read_inline_total(content, "calories_so_far")
    metrics["protein"] = read_inline_total(content, "protein_so_far")
    metrics["carbs"] = read_inline_total(content, "carbs_so_far")
    metrics["fat"] = read_inline_total(content, "fat_so_far")
    metrics["fiber"] = read_inline_total(content, "fiber_so_far")

    # Parse quick log metrics
    for metric in ["Energy", "Focus", "Mood_PM"]:
        if f"{metric}::" in content:
            try:
                line = [l for l in content.split("\n") if f"{metric}::" in l][0]
                value = line.split("::")[1].strip()
                metrics[metric.lower()] = value if value else None
            except:
                metrics[metric.lower()] = None

    return metrics


def send_mid_morning_checkin() -> str:
    """10am check-in: Energy and focus levels."""
    metrics = read_log_metrics()

    lines = []
    lines.append("☕ *Mid-Morning Check-in*\n")
    lines.append("How's your morning going?")
    lines.append("")
    lines.append("📊 *Quick check:*")

    energy = metrics.get("energy")
    focus = metrics.get("focus")

    if not energy:
        lines.append("⚠️ Energy level not logged yet")
    else:
        lines.append(f"✅ Energy: {energy}/10")

    if not focus:
        lines.append("⚠️ Focus level not logged yet")
    else:
        lines.append(f"✅ Focus: {focus}/10")

    lines.append("")
    lines.append("💧 *Hydration reminder:*")
    lines.append("Had 2+ glasses of water this morning?")
    lines.append("")
    lines.append("Reply to log your current energy/focus if needed!")

    message = "\n".join(lines)
    success = send_telegram_message(message)

    return "Mid-morning check-in sent ✅" if success else "Failed ❌"


def send_lunch_checkin() -> str:
    """12pm check-in: Meal logging."""
    metrics = read_log_metrics()

    lines = []
    lines.append("🍽️ *Lunch Time!*\n")

    calories = metrics.get("calories", 0)
    protein = metrics.get("protein", 0)

    lines.append("📊 *Nutrition so far:*")
    lines.append(f"Calories: {calories}")
    lines.append(f"Protein: {protein}g")
    lines.append("")

    if calories < 500:
        lines.append("⚠️ Low calories - make sure to eat a good lunch!")

    lines.append("📝 *Log your lunch:*")
    lines.append("Reply with what you're eating and approximate:")
    lines.append("- Calories")
    lines.append("- Protein (g)")
    lines.append("")
    lines.append("Example: 'Chicken bowl - 600 cal, 45g protein'")

    message = "\n".join(lines)
    success = send_telegram_message(message)

    return "Lunch check-in sent ✅" if success else "Failed ❌"


def send_mid_afternoon_checkin() -> str:
    """3pm check-in: Energy dip and movement."""
    lines = []
    lines.append("🚶 *Mid-Afternoon Check-in*\n")
    lines.append("Feeling the afternoon dip?")
    lines.append("")
    lines.append("💪 *Movement break:*")
    lines.append("- Stand up and stretch for 2 minutes")
    lines.append("- Walk around for 5 minutes")
    lines.append("- Do 10 squats or push-ups")
    lines.append("")
    lines.append("☕ *Avoid:*")
    lines.append("- Excess caffeine (affects sleep)")
    lines.append("- Heavy snacking (energy crash)")
    lines.append("")
    lines.append("✅ *Better options:*")
    lines.append("- Water or tea")
    lines.append("- Light protein snack")
    lines.append("- Short walk outside")

    message = "\n".join(lines)
    success = send_telegram_message(message)

    return "Mid-afternoon check-in sent ✅" if success else "Failed ❌"


def send_dinner_checkin() -> str:
    """6pm check-in: Dinner meal log and daily nutrition total."""
    metrics = read_log_metrics()

    lines = []
    lines.append("🍽️ *Dinner Time!*\n")

    calories = metrics.get("calories", 0)
    protein = metrics.get("protein", 0)

    lines.append("📊 *Daily nutrition (so far):*")
    lines.append(f"Calories: {calories}")
    lines.append(f"Protein: {protein}g")
    lines.append("")

    # Target: ~2500 cal, ~180g protein for 245lb athlete
    cal_remaining = 2500 - calories
    protein_remaining = 180 - protein

    if cal_remaining > 0:
        lines.append(f"🎯 *Dinner target:*")
        lines.append(f"~{cal_remaining} calories")
        lines.append(f"~{protein_remaining}g protein")
    else:
        lines.append("✅ Daily calorie target met!")

    lines.append("")
    lines.append("📝 *Log your dinner:*")
    lines.append("Reply with what you're eating")
    lines.append("")
    lines.append("⏰ *Evening prep:*")
    lines.append("- Finish eating by 8pm for better sleep")
    lines.append("- Light meal = better recovery")

    message = "\n".join(lines)
    success = send_telegram_message(message)

    return "Dinner check-in sent ✅" if success else "Failed ❌"


def send_pre_bed_checkin() -> str:
    """10pm check-in: Sleep prep and log completion."""
    metrics = read_log_metrics()
    log_path = get_today_log_path()

    lines = []
    lines.append("🌙 *Pre-Bed Check-in*\n")

    # Check what's missing
    missing = []
    if not metrics.get("mood_pm"):
        missing.append("Mood PM")

    calories = metrics.get("calories", 0)
    protein = metrics.get("protein", 0)

    if calories == 0:
        missing.append("Nutrition log")

    if missing:
        lines.append("📝 *Complete your log:*")
        for item in missing:
            lines.append(f"⚠️ Missing: {item}")
        lines.append("")

    lines.append("📊 *Today's nutrition:*")
    lines.append(f"Total calories: {calories}")
    lines.append(f"Total protein: {protein}g")
    lines.append("")

    lines.append("😴 *Sleep prep checklist:*")
    lines.append("- [ ] Phone on Do Not Disturb")
    lines.append("- [ ] Room temperature cool")
    lines.append("- [ ] All screens off in 30min")
    lines.append("- [ ] Journal today's wins")
    lines.append("- [ ] Set tomorrow's top 3")
    lines.append("")
    lines.append("🎯 Target: In bed by 10:30pm for 7+ hours")
    lines.append("")
    lines.append("Sleep well! Tomorrow's going to be great. 💪")

    message = "\n".join(lines)
    success = send_telegram_message(message)

    return "Pre-bed check-in sent ✅" if success else "Failed ❌"


def main():
    """CLI interface."""
    if not TELEGRAM_BOT_TOKEN or not OWNER_CHAT_ID:
        print("❌ Error: TELEGRAM_BOT_TOKEN and OWNER_CHAT_ID must be set in .env")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python daily_checkins.py <mid-morning|lunch|mid-afternoon|dinner|pre-bed>")
        sys.exit(1)

    command = sys.argv[1].lower()

    print(f"📤 Sending {command} check-in...")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    handlers = {
        "mid-morning": send_mid_morning_checkin,
        "lunch": send_lunch_checkin,
        "mid-afternoon": send_mid_afternoon_checkin,
        "dinner": send_dinner_checkin,
        "pre-bed": send_pre_bed_checkin,
    }

    if command in handlers:
        result = handlers[command]()
        print(result)
    else:
        print(f"❌ Unknown command: {command}")
        print(f"Valid commands: {', '.join(handlers.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
