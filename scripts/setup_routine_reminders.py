#!/usr/bin/env python3
"""
Set up routine reminders using the existing cron system
"""
import json
import os
from pathlib import Path

# Path to cron config
PRIVATE_DIR = Path(os.environ.get("HISTORY_DIR", str(Path.home() / ".bestupid-private")))
CRON_CONFIG = PRIVATE_DIR / "cron_jobs.json"

def update_cron_config():
    """Update the cron configuration with routine reminders"""
    
    # Default config structure
    config = {
        "morning_briefing": {
            "schedule": "0 8 * * *",  # 8 AM morning routine
            "enabled": True,
            "description": "Morning routine reminder"
        },
        "evening_reminder": {
            "schedule": "0 22 * * *",  # 10 PM evening routine start
            "enabled": True,
            "description": "Evening routine start"
        },
        "evening_screens": {
            "schedule": "15 22 * * *",  # 10:15 PM screens off
            "enabled": True,
            "description": "Close all screens reminder"
        },
        "evening_bed": {
            "schedule": "30 23 * * *",  # 11:30 PM bedtime
            "enabled": True,
            "description": "Final bedtime reminder"
        },
        "daily_planner": {
            "schedule": "0 23 * * *",  # 11 PM daily planning
            "enabled": True,
            "description": "Generate tomorrow's plan"
        },
        "auto_backup": {
            "schedule": "0 0 * * *",  # Midnight backup
            "enabled": True,
            "description": "Automated git backup"
        }
    }
    
    # Load existing config if it exists
    if CRON_CONFIG.exists():
        try:
            existing = json.loads(CRON_CONFIG.read_text())
            # Merge with defaults, preserving existing enabled states
            for job, settings in existing.items():
                if job in config:
                    config[job]["enabled"] = settings.get("enabled", True)
        except (json.JSONDecodeError, OSError):
            pass
    
    # Ensure directory exists
    CRON_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    
    # Write updated config
    with open(CRON_CONFIG, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ Routine reminders configured:")
    print("  • 8:00 AM  - Morning routine start")
    print("  • 10:00 PM - Evening routine start") 
    print("  • 10:15 PM - Close all screens")
    print("  • 11:30 PM - Bedtime reminder")
    print("  • 11:00 PM - Daily planning")
    print("  • 12:00 AM - Auto backup")
    
    return config

if __name__ == "__main__":
    update_cron_config()
    print("\n🔧 To activate: restart your Telegram bot to reload the scheduler")
    print("📱 You'll receive automated routine reminders at the scheduled times!")