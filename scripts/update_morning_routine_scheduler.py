#!/usr/bin/env python3
"""
Update the morning briefing to send the detailed routine reminder
"""
import json
import os
from pathlib import Path

# Path to scheduler config
PRIVATE_DIR = Path(os.environ.get("HISTORY_DIR", str(Path.home() / ".bestupid-private")))
CRON_CONFIG = PRIVATE_DIR / "cron_jobs.json"

# Path to telegram-bot tools.py to update the command mapping
TELEGRAM_BOT_DIR = Path(__file__).parent.parent / "telegram-bot"
TOOLS_FILE = TELEGRAM_BOT_DIR / "tools.py"

def update_scheduler_config():
    """Update the cron config to use the routine reminder"""
    
    if not CRON_CONFIG.exists():
        print("❌ Cron config not found. Run setup_routine_reminders.py first.")
        return False
    
    try:
        with open(CRON_CONFIG) as f:
            config = json.load(f)
        
        # Update morning briefing to use routine reminder
        if "morning_briefing" in config:
            config["morning_briefing"]["description"] = "Morning routine reminder with checklist"
        
        # Write back
        with open(CRON_CONFIG, 'w') as f:
            json.dump(config, f, indent=2)
        
        print("✅ Updated cron config")
        return True
        
    except Exception as e:
        print(f"❌ Failed to update cron config: {e}")
        return False

def update_telegram_scheduler():
    """Update the telegram-bot scheduler to use routine reminders"""
    
    scheduler_file = TELEGRAM_BOT_DIR / "scheduler.py"
    if not scheduler_file.exists():
        print("❌ Telegram scheduler not found")
        return False
    
    try:
        # Read current scheduler
        content = scheduler_file.read_text()
        
        # Check if we need to update the JOB_COMMANDS mapping
        if "send_routine_reminder.py" not in content:
            # Update the JOB_COMMANDS mapping
            new_commands = '''JOB_COMMANDS = {
    "morning_briefing": ["python", "scripts/send_routine_reminder.py", "morning"],
    "evening_reminder": ["python", "scripts/send_routine_reminder.py", "evening_start"],
    "evening_screens": ["python", "scripts/send_routine_reminder.py", "evening_screens"],  
    "evening_bed": ["python", "scripts/send_routine_reminder.py", "evening_bed"],
    "daily_planner": ["python", "scripts/daily_planner.py"],
    "auto_backup": ["python", "scripts/robust_git_backup.py"],
}'''
            
            # Replace the JOB_COMMANDS section
            import re
            pattern = r'JOB_COMMANDS = \{[^}]+\}'
            updated_content = re.sub(pattern, new_commands, content, flags=re.DOTALL)
            
            # Write back
            scheduler_file.write_text(updated_content)
            
            print("✅ Updated telegram scheduler to use routine reminders")
            return True
        else:
            print("✅ Telegram scheduler already using routine reminders")
            return True
            
    except Exception as e:
        print(f"❌ Failed to update telegram scheduler: {e}")
        return False

def main():
    print("🔧 Updating morning routine scheduler...")
    
    success1 = update_scheduler_config()
    success2 = update_telegram_scheduler()
    
    if success1 and success2:
        print("\n✅ Morning routine scheduler updated!")
        print("📱 Your 8 AM reminder will now include the full routine checklist")
        print("🔄 Restart the Telegram bot to activate the changes")
    else:
        print("\n❌ Some updates failed. Check the errors above.")

if __name__ == "__main__":
    main()