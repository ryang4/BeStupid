#!/usr/bin/env python3
"""
Send routine reminders via Telegram
"""
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

def send_telegram_message(text: str):
    """Send a message via Telegram"""
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
        
        if response.status_code == 200:
            print("✅ Reminder sent successfully")
            return True
        else:
            print(f"❌ Failed to send reminder: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending reminder: {e}")
        return False

def get_morning_reminder():
    """Generate morning routine reminder"""
    return """🌅 **MORNING ROUTINE TIME!**

⏰ **Next 30 minutes = Phone-free productivity**

**Your morning sequence:**
1. 💧 Hydrate - drink water
2. 🎯 Capture today's #1 priority 
3. 🏃‍♂️ 5-10 min movement/stretch
4. 🍳 Planned breakfast
5. 💪 25-min work block on #1 priority

**Remember:** Phone stays off until routine complete!

Type "done" when you've completed your morning routine."""

def get_evening_start_reminder():
    """Generate evening routine start reminder"""
    return """🌙 **EVENING ROUTINE - STARTING NOW**

⏰ **10:00 PM - Time to wind down**

**Next step:**
📱 Put phone on Do Not Disturb

**Coming up:**
• 10:15 PM - Close all screens
• 10:30 PM - Day review 
• 11:00 PM - Personal routine
• 11:30 PM - In bed, lights off

Setting you up for success! 💪"""

def get_evening_screens_reminder():
    """Generate screens off reminder"""
    return """💻 **SCREENS OFF TIME!**

⏰ **10:15 PM - Close all devices**

Laptop closed ✅
TV off ✅  
iPad put away ✅

**Next:** Quick day review at 10:30 PM
- Did I ship something today?
- What's tomorrow's #1 priority?

Your brain needs this transition time! 🧠"""

def get_evening_bed_reminder():
    """Generate bedtime reminder"""
    return """🛏️ **BEDTIME ROUTINE - FINAL CALL**

⏰ **11:30 PM - In bed, lights off**

You're 30 minutes from your midnight sleep goal! 

**Quick check:**
• Personal hygiene done? ✅
• Tomorrow's #1 priority set? ✅
• Phone charging outside bedroom? ✅

**Lights off now = successful day!** 🌙"""

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